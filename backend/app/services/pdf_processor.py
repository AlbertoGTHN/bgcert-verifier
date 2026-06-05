"""
PDF Processing Service
Converts PDFs to images, runs OCR, and extracts text metadata.
"""
import os
import re
import time
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import tldextract
from PIL import Image
from loguru import logger

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("pytesseract not available — OCR disabled")

try:
    from langdetect import detect as detect_language
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

from app.config import settings


@dataclass
class PageResult:
    page_num: int
    image_path: str
    text: str
    confidence: float
    width: int
    height: int


@dataclass
class PDFProcessResult:
    file_path: str
    page_count: int
    pages: List[PageResult] = field(default_factory=list)
    full_text: str = ""
    language: str = "eng"
    country: Optional[str] = None
    cert_type: str = "unknown"

    # Extracted person info
    holder_name: Optional[str] = None
    holder_id: Optional[str] = None
    cert_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    issuing_authority: Optional[str] = None

    # PDF metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    has_embedded_images: bool = False
    avg_ocr_confidence: float = 0.0

    error: Optional[str] = None


class PDFProcessor:
    """Converts PDFs to images and extracts text via OCR."""

    # ── Country detection: OCR text patterns ─────────────────────────────────
    # Each entry lists regex patterns found in genuine documents from that country.
    # Matching threshold: ≥2 hits, or 1 hit when the country has ≤3 patterns.
    COUNTRY_PATTERNS = {
        # ── Latin America ──────────────────────────────────────────────────
        "Colombia": [
            r"rep[uú]blica de colombia", r"polic[ií]a nacional de colombia",
            r"sij[ií]n", r"dij[ií]n", r"antecedentes judiciales",
            r"certificado judicial", r"\bc\.c\.\s*\d", r"\bnit:\s*\d",
            r"fiscalía general", r"registradur[ií]a",
        ],
        "Peru": [
            r"rep[uú]blica del per[uú]", r"ministerio del interior.*per[uú]",
            r"\bpnp\b", r"polic[ií]a nacional del per[uú]",
            r"certificado de antecedentes.*pnp", r"\bdni:\s*\d",
            r"reniec", r"poder judicial del per[uú]",
        ],
        "Mexico": [
            r"estados unidos mexicanos", r"secretar[ií]a de seguridad.*m[eé]xico",
            r"\brenapo\b", r"\bcurp:\s*[A-Z]", r"carta de antecedentes no penales",
            r"gobierno.*m[eé]xico", r"constancia de antecedentes",
            r"registro nacional de poblaci[oó]n",
        ],
        "Chile": [
            r"rep[uú]blica de chile", r"registro civil.*chile",
            r"\bcarabineros\b", r"certificado de antecedentes para fines generales",
            r"\brut:\s*\d", r"servicio de registro civil",
            r"ministerio de justicia.*chile",
        ],
        "Brazil": [
            r"rep[uú]blica federativa do brasil", r"pol[ií]cia federal.*brasil",
            r"certi[dḑ][aã]o.*antecedentes", r"\bcpf:\s*\d",
            r"minist[eé]rio da justi[cç]a", r"certid[aã]o criminal",
            r"tribunal de justi[cç]a", r"distribuidor.*criminal",
        ],
        "Argentina": [
            r"rep[uú]blica argentina", r"ministerio de seguridad.*argentina",
            r"registro nacional de reincidencia", r"antecedentes penales.*argentina",
            r"\bdni:\s*\d.*argentina|\bargentina.*\bdni:\s*\d",
            r"\bcuil:\s*\d", r"\bcuit:\s*\d",
            r"poder judicial.*argentina",
        ],
        "Ecuador": [
            r"rep[uú]blica del ecuador", r"ministerio del interior.*ecuador",
            r"polic[ií]a nacional del ecuador", r"funci[oó]n judicial.*ecuador",
            r"c[eé]dula.*ecuador|ecuador.*c[eé]dula",
            r"registro civil.*ecuador", r"senescyt",
        ],
        "Venezuela": [
            r"rep[uú]blica bolivariana de venezuela",
            r"ministerio del poder popular.*venezuela",
            r"cuerpo de investigaciones.*cic[pc]",
            r"c[eé]dula de identidad.*venezuela|venezuela.*c[eé]dula",
            r"tribunal supremo de justicia.*venezuela",
        ],
        "Bolivia": [
            r"estado plurinacional de bolivia",
            r"polic[ií]a boliviana|fuerza especial de lucha",
            r"c[eé]dula de identidad.*bolivia|bolivia.*c[eé]dula",
            r"ministerio de gobierno.*bolivia",
            r"servicio general de identificaci[oó]n.*bolivia",
        ],
        "Paraguay": [
            r"rep[uú]blica del paraguay",
            r"polic[ií]a nacional del paraguay",
            r"ministerio del interior.*paraguay",
            r"c[eé]dula de identidad.*paraguay|paraguay.*c[eé]dula",
            r"poder judicial.*paraguay",
        ],
        "Uruguay": [
            r"rep[uú]blica oriental del uruguay",
            r"ministerio del interior.*uruguay",
            r"polic[ií]a nacional.*uruguay",
            r"c[eé]dula de identidad.*uruguay|uruguay.*c[eé]dula",
            r"poder judicial.*uruguay",
        ],
        "Costa Rica": [
            r"rep[uú]blica de costa rica",
            r"tribunal supremo de elecciones.*costa rica",
            r"c[eé]dula.*costarricense|costa rica.*c[eé]dula",
            r"organismo de investigaci[oó]n judicial",
            r"ministerio de seguridad.*costa rica",
        ],
        "Panama": [
            r"rep[uú]blica de panam[aá]",
            r"tribunal electoral.*panam[aá]",
            r"c[eé]dula.*paname[nñ]a|panam[aá].*c[eé]dula",
            r"ministerio de seguridad.*panam[aá]",
            r"polic[ií]a nacional.*panam[aá]",
        ],
        "El Salvador": [
            r"rep[uú]blica de el salvador",
            r"polic[ií]a nacional civil.*salvador",
            r"registro nacional de personas.*salvador",
            r"dui.*salvador|salvador.*dui\b",
            r"corte suprema de justicia.*salvador",
        ],
        "Honduras": [
            r"rep[uú]blica de honduras",
            r"direcci[oó]n nacional de investigaci[oó]n criminal",
            r"secretar[ií]a de seguridad.*honduras",
            r"\bdni.*honduras|honduras.*\bdni\b",
        ],
        "Guatemala": [
            r"rep[uú]blica de guatemala",
            r"ministerio de gobernaci[oó]n.*guatemala",
            r"polic[ií]a nacional civil.*guatemala",
            r"registro nacional de las personas.*guatemala",
            r"\bdpi.*guatemala|guatemala.*\bdpi\b",
        ],
        "Dominican Republic": [
            r"rep[uú]blica dominicana",
            r"junta central electoral",
            r"polic[ií]a nacional.*dominicana",
            r"c[eé]dula.*dominicana|dominicana.*c[eé]dula",
            r"procuradur[ií]a.*dominicana",
        ],
        "Jamaica": [
            r"jamaica constabulary force",
            r"government of jamaica",
            r"police certificate.*jamaica|jamaica.*police certificate",
            r"trn.*jamaica|jamaica.*trn\b",
        ],
        "Trinidad and Tobago": [
            r"trinidad and tobago",
            r"ttps\b|trinidad.*tobago.*police",
            r"certificate of character.*trinidad",
        ],
        "Belize": [
            r"government of belize", r"belize police department",
            r"belize national identification",
        ],

        # ── North America ──────────────────────────────────────────────────
        "United States": [
            r"united states of america", r"federal bureau of investigation",
            r"\bfbi\b.*background", r"social security.*number",
            r"department of justice.*usa|u\.s\. department of justice",
            r"criminal history record",
        ],
        "Canada": [
            r"government of canada|gouvernement du canada",
            r"royal canadian mounted police|gendarmerie royale",
            r"\brcmp\b", r"criminal record check.*canada",
            r"vulnerable sector.*check", r"social insurance number",
        ],

        # ── Europe ────────────────────────────────────────────────────────
        "United Kingdom": [
            r"united kingdom", r"disclosure and barring service",
            r"\bdbs\s+check\b", r"acro criminal records",
            r"certificate of good conduct.*uk|uk.*certificate of good conduct",
            r"national police.*check.*uk",
        ],
        "Spain": [
            r"reino de espa[nñ]a", r"ministerio de justicia.*espa[nñ]a",
            r"registro central de penados", r"antecedentes penales.*espa[nñ]a",
            r"dni.*espa[nñ]ol|nie\s*\d",
        ],
        "France": [
            r"r[eé]publique fran[cç]aise",
            r"casier judiciaire national",
            r"minist[eè]re de la justice.*france",
            r"bulletin.*casier judiciaire",
        ],
        "Germany": [
            r"bundesrepublik deutschland",
            r"f[uü]hrungszeugnis",
            r"bundeszentralregister",
            r"polizeiliches f[uü]hrungszeugnis",
        ],
        "Netherlands": [
            r"koninkrijk der nederlanden",
            r"verklaring omtrent het gedrag",
            r"\bvog\b.*nederland",
            r"justis.*nederland|dienst justis",
        ],
        "Portugal": [
            r"rep[uú]blica portuguesa",
            r"registo criminal.*portugal",
            r"certid[aã]o.*registo criminal",
            r"minist[eé]rio da justi[cç]a.*portugal",
        ],
        "Italy": [
            r"repubblica italiana",
            r"casellario giudiziale",
            r"ministero della giustizia.*italia",
            r"certificato del casellario",
        ],

        # ── Asia-Pacific ───────────────────────────────────────────────────
        "Philippines": [
            r"republic of the philippines",
            r"philippine national police",
            r"\bnbi\b.*philippines|philippines.*\bnbi\b",
            r"national bureau of investigation.*philippine",
            r"\bnbi clearance\b", r"\bpnp clearance\b",
        ],
        "India": [
            r"government of india",
            r"police verification.*india|india.*police verification",
            r"character certificate.*india",
            r"\baadhar\b|\baadhaar\b",
            r"national crime records bureau",
            r"\bpan\s+card\b",
        ],
        "Indonesia": [
            r"republik indonesia",
            r"kepolisian.*negara.*republik indonesia",
            r"\bpolri\b",
            r"\bskck\b",  # Surat Keterangan Catatan Kepolisian
            r"\bktp.*indonesia|indonesia.*\bktp\b",
        ],
        "Malaysia": [
            r"kerajaan malaysia|government of malaysia",
            r"polis diraja malaysia",
            r"\bpdrm\b",
            r"\bmykad\b|\bic.*malaysia|malaysia.*\bic\b",
            r"jabatan pendaftaran negara",
        ],
        "Singapore": [
            r"republic of singapore",
            r"singapore police force",
            r"\bspf\b.*singapore",
            r"\bnric\b.*singapore|singapore.*\bnric\b",
            r"ministry of home affairs.*singapore",
        ],
        "Thailand": [
            r"kingdom of thailand|ราชอาณาจักรไทย",
            r"royal thai police",
            r"criminal record.*thailand|thailand.*criminal record",
            r"national id.*thailand",
        ],
        "Vietnam": [
            r"c[oộ]ng hòa x[aã] h[oộ]i ch[uủ] ngh[iĩ]a vi[eệ]t nam",
            r"c[oô]ng an nhân dân",
            r"lý lịch tư pháp",
            r"căn cước công dân",
        ],
        "Bangladesh": [
            r"government of bangladesh|people.*republic.*bangladesh",
            r"bangladesh police", r"\bnid.*bangladesh|bangladesh.*\bnid\b",
        ],
        "Sri Lanka": [
            r"democratic socialist republic of sri lanka",
            r"sri lanka police", r"criminal record.*sri lanka",
        ],
        "Nepal": [
            r"government of nepal|nepal police",
            r"police clearance.*nepal|nepal.*police clearance",
        ],
        "Pakistan": [
            r"islamic republic of pakistan",
            r"federal investigation agency", r"\bfia\b.*pakistan",
            r"\bcnic\b.*pakistan|pakistan.*\bcnic\b",
        ],

        # ── Africa ────────────────────────────────────────────────────────
        "South Africa": [
            r"republic of south africa",
            r"south africa police service|\bsaps\b",
            r"department of home affairs.*south africa",
            r"\bid.*south africa|south africa.*\bid\b",
            r"criminal record.*south africa",
        ],
        "Nigeria": [
            r"federal republic of nigeria",
            r"nigeria police force",
            r"national identity management commission|\bnimc\b",
            r"\bnin.*nigeria|nigeria.*\bnin\b",
        ],
        "Kenya": [
            r"republic of kenya",
            r"national police service.*kenya",
            r"directorate of criminal investigations.*kenya",
            r"\bdci\b.*kenya",
        ],
        "Ghana": [
            r"republic of ghana",
            r"ghana police service",
            r"criminal record.*ghana",
        ],

        # ── Oceania ───────────────────────────────────────────────────────
        "Australia": [
            r"commonwealth of australia|government of australia",
            r"australian federal police|\bafp\b",
            r"national police check.*australia",
            r"\btfn\b|\babn\b.*australia",
        ],
        "New Zealand": [
            r"new zealand police",
            r"police certificate.*new zealand|new zealand.*police certificate",
            r"\bnzp\b.*clearance",
        ],
    }

    # ── Country detection: domain TLD / hostname patterns ─────────────────
    # Used as a fallback when OCR-based detection doesn't produce a result.
    DOMAIN_COUNTRY_MAP: Dict[str, str] = {
        # ccTLDs
        ".co": "Colombia",
        ".pe": "Peru",
        ".mx": "Mexico",
        ".cl": "Chile",
        ".br": "Brazil",
        ".ar": "Argentina",
        ".ec": "Ecuador",
        ".ve": "Venezuela",
        ".bo": "Bolivia",
        ".py": "Paraguay",
        ".uy": "Uruguay",
        ".cr": "Costa Rica",
        ".pa": "Panama",
        ".sv": "El Salvador",
        ".hn": "Honduras",
        ".gt": "Guatemala",
        ".do": "Dominican Republic",
        ".jm": "Jamaica",
        ".tt": "Trinidad and Tobago",
        ".bz": "Belize",
        ".ca": "Canada",
        ".uk": "United Kingdom",
        ".es": "Spain",
        ".fr": "France",
        ".de": "Germany",
        ".nl": "Netherlands",
        ".pt": "Portugal",
        ".it": "Italy",
        ".ph": "Philippines",
        ".in": "India",
        ".id": "Indonesia",
        ".my": "Malaysia",
        ".sg": "Singapore",
        ".th": "Thailand",
        ".vn": "Vietnam",
        ".bd": "Bangladesh",
        ".lk": "Sri Lanka",
        ".np": "Nepal",
        ".pk": "Pakistan",
        ".za": "South Africa",
        ".ng": "Nigeria",
        ".ke": "Kenya",
        ".gh": "Ghana",
        ".au": "Australia",
        ".nz": "New Zealand",
    }

    # Keyword hints in the domain hostname (beyond TLD)
    DOMAIN_KEYWORD_COUNTRY: Dict[str, str] = {
        "colombia": "Colombia",
        "policia.gov.co": "Colombia",
        "registraduria": "Colombia",
        "peru": "Peru",
        "pnp.gob.pe": "Peru",
        "mexico": "Mexico",
        "gob.mx": "Mexico",
        "chile": "Chile",
        "registrocivil.cl": "Chile",
        "brasil": "Brazil",
        "brazil": "Brazil",
        "gov.br": "Brazil",
        "argentina": "Argentina",
        "ecuador": "Ecuador",
        "venezuela": "Venezuela",
        "bolivia": "Bolivia",
        "paraguay": "Paraguay",
        "uruguay": "Uruguay",
        "costarica": "Costa Rica",
        "panama": "Panama",
        "elsalvador": "El Salvador",
        "honduras": "Honduras",
        "guatemala": "Guatemala",
        "dominican": "Dominican Republic",
        "jamaica": "Jamaica",
        "trinidad": "Trinidad and Tobago",
        "philippines": "Philippines",
        "nbi.gov.ph": "Philippines",
        "pnp.gov.ph": "Philippines",
        "india": "India",
        "ncrb.gov.in": "India",
        "indonesia": "Indonesia",
        "malaysia": "Malaysia",
        "singapore": "Singapore",
        "thailand": "Thailand",
        "vietnam": "Vietnam",
        "southafrica": "South Africa",
        "saps.gov.za": "South Africa",
        "nigeria": "Nigeria",
        "kenya": "Kenya",
        "australia": "Australia",
        "afp.gov.au": "Australia",
        "newzealand": "New Zealand",
    }

    # Certificate type patterns
    CERT_TYPE_PATTERNS = {
        "criminal_background": [
            r"antecedentes (judiciales|penales|criminales)", r"criminal background",
            r"criminal record", r"antecedentes", r"background check"
        ],
        "police_clearance": [
            r"police clearance", r"certificado policial", r"clearance certificate",
            r"nbi clearance", r"pnp clearance"
        ],
        "government_clearance": [
            r"government clearance", r"security clearance", r"habilitación",
            r"certificado de buena conducta"
        ],
    }

    # Person info extraction patterns
    NAME_PATTERNS = [
        r"(?:nombre|name|titular|holder)[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]{3,50})",
        r"(?:señor|señora|sr\.|sra\.)[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]{3,50})",
        r"(?:apellidos y nombres|full name)[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]{3,80})",
    ]

    CERT_NUMBER_PATTERNS = [
        r"(?:n[°º]?|número|number|cert\.?\s*no\.?|folio)[:\s#]+([A-Z0-9\-]{4,30})",
        r"(?:serial|código|code)[:\s]+([A-Z0-9\-]{4,30})",
    ]

    DATE_PATTERNS = [
        r"(?:fecha\s+de\s+expedición|issue\s+date|fecha)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        r"(?:issued\s+on|expedido\s+el)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        r"(\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+\d{4})",
    ]

    def __init__(self):
        if OCR_AVAILABLE and settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    def process(self, file_path: str, temp_dir: str) -> PDFProcessResult:
        """Main entry point: process a PDF file."""
        result = PDFProcessResult(file_path=file_path, page_count=0)
        start_time = time.time()

        try:
            doc = fitz.open(file_path)
            result.page_count = len(doc)
            result.metadata = self._extract_metadata(doc)
            result.has_embedded_images = self._has_embedded_images(doc)

            pages_dir = os.path.join(temp_dir, "pages")
            os.makedirs(pages_dir, exist_ok=True)

            page_results = []
            for page_num in range(len(doc)):
                page_result = self._process_page(doc[page_num], page_num, pages_dir)
                page_results.append(page_result)

            doc.close()
            result.pages = page_results
            result.full_text = "\n\n".join(p.text for p in page_results if p.text)

            if page_results:
                result.avg_ocr_confidence = sum(p.confidence for p in page_results) / len(page_results)

            # Detect language
            if result.full_text.strip():
                result.language = self._detect_language(result.full_text)

            # Detect country
            result.country = self._detect_country(result.full_text)

            # Detect certificate type
            result.cert_type = self._detect_cert_type(result.full_text)

            # Extract person info
            self._extract_person_info(result)

            logger.info(
                f"PDF processed in {time.time()-start_time:.2f}s: "
                f"{result.page_count} pages, country={result.country}, lang={result.language}"
            )

        except Exception as e:
            logger.error(f"PDF processing error for {file_path}: {e}", exc_info=True)
            result.error = str(e)

        return result

    def _process_page(self, page: fitz.Page, page_num: int, pages_dir: str) -> PageResult:
        """Convert a single page to image and run OCR."""
        # Render at high DPI for better OCR
        mat = fitz.Matrix(settings.OCR_DPI / 72, settings.OCR_DPI / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        image_path = os.path.join(pages_dir, f"page_{page_num + 1:04d}.png")
        pix.save(image_path)

        text = ""
        confidence = 0.0

        if OCR_AVAILABLE:
            try:
                img = Image.open(image_path)
                # Improve image quality for OCR
                img = self._preprocess_image(img)

                ocr_data = pytesseract.image_to_data(
                    img,
                    lang=settings.OCR_LANGUAGES,
                    config="--oem 3 --psm 1",
                    output_type=pytesseract.Output.DICT,
                )

                # Extract text and confidence
                words = []
                confidences = []
                for i, word in enumerate(ocr_data["text"]):
                    conf = int(ocr_data["conf"][i])
                    if conf > 0 and word.strip():
                        words.append(word)
                        confidences.append(conf)

                text = " ".join(words)
                confidence = sum(confidences) / len(confidences) if confidences else 0.0

            except Exception as e:
                logger.warning(f"OCR failed on page {page_num + 1}: {e}")
                # Fallback: try to extract embedded text
                try:
                    text = page.get_text()
                    confidence = 50.0 if text.strip() else 0.0
                except Exception:
                    pass

        else:
            # No OCR, try embedded text extraction
            try:
                text = page.get_text()
                confidence = 50.0 if text.strip() else 0.0
            except Exception:
                pass

        return PageResult(
            page_num=page_num + 1,
            image_path=image_path,
            text=text,
            confidence=confidence / 100.0,
            width=pix.width,
            height=pix.height,
        )

    def _preprocess_image(self, img: Image.Image) -> Image.Image:
        """Enhance image quality for better OCR results."""
        import numpy as np
        import cv2

        img_array = np.array(img)

        # Convert to grayscale if needed
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # Adaptive thresholding for better text extraction
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        return Image.fromarray(binary)

    def _extract_metadata(self, doc: fitz.Document) -> Dict[str, Any]:
        """Extract PDF metadata."""
        try:
            meta = doc.metadata
            return {
                "author": meta.get("author", ""),
                "creator": meta.get("creator", ""),
                "producer": meta.get("producer", ""),
                "title": meta.get("title", ""),
                "subject": meta.get("subject", ""),
                "creation_date": meta.get("creationDate", ""),
                "modification_date": meta.get("modDate", ""),
                "encrypted": doc.is_encrypted,
            }
        except Exception:
            return {}

    def _has_embedded_images(self, doc: fitz.Document) -> bool:
        """Check if any page contains embedded raster images."""
        for page in doc:
            if page.get_images():
                return True
        return False

    def _detect_language(self, text: str) -> str:
        """Detect primary language of text."""
        if not LANGDETECT_AVAILABLE or not text.strip():
            return "eng"
        try:
            lang = detect_language(text[:2000])
            lang_map = {"es": "spa", "pt": "por", "fr": "fra", "en": "eng"}
            return lang_map.get(lang, lang)
        except Exception:
            return "eng"

    def _detect_country(self, text: str) -> Optional[str]:
        """Detect country from document text using weighted pattern matching."""
        text_lower = text.lower()
        scores: Dict[str, int] = {}
        for country, patterns in self.COUNTRY_PATTERNS.items():
            hits = sum(1 for p in patterns if re.search(p, text_lower))
            if hits > 0:
                scores[country] = hits

        if not scores:
            return None

        best_country = max(scores, key=lambda c: scores[c])
        best_hits = scores[best_country]

        # Accept single-hit match only if the pattern list is short (≤4) —
        # short lists mean each pattern is highly distinctive.
        if best_hits >= 2:
            return best_country
        if best_hits == 1 and len(self.COUNTRY_PATTERNS[best_country]) <= 4:
            return best_country
        return None

    def detect_country_from_domain(self, domain: str) -> Optional[str]:
        """Infer country from a verification URL domain (fallback).

        Checks:
        1. Known hostname keywords (e.g. 'nbi.gov.ph' → Philippines)
        2. ccTLD suffix (e.g. '.co' → Colombia, '.ph' → Philippines)
        """
        if not domain:
            return None
        domain_lower = domain.lower().strip(".")

        # 1. Keyword match in full hostname
        for keyword, country in self.DOMAIN_KEYWORD_COUNTRY.items():
            if keyword in domain_lower:
                return country

        # 2. ccTLD match — look for last two-char segment preceded by a dot
        try:
            ext = tldextract.extract(domain_lower)
            suffix_parts = ext.suffix.split(".")
            # Use the rightmost part of the suffix
            for part in reversed(suffix_parts):
                tld = f".{part}"
                if tld in self.DOMAIN_COUNTRY_MAP:
                    return self.DOMAIN_COUNTRY_MAP[tld]
        except Exception:
            pass

        return None

    def _detect_cert_type(self, text: str) -> str:
        """Detect certificate type from text."""
        text_lower = text.lower()
        for cert_type, patterns in self.CERT_TYPE_PATTERNS.items():
            for p in patterns:
                if re.search(p, text_lower):
                    return cert_type
        return "unknown"

    def _extract_person_info(self, result: PDFProcessResult):
        """Extract person information from OCR text."""
        text = result.full_text

        # Name
        for pattern in self.NAME_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if 3 <= len(name) <= 80:
                    result.holder_name = name.title()
                    break

        # Certificate number
        for pattern in self.CERT_NUMBER_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result.cert_number = match.group(1).strip()
                break

        # Issue date
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result.issue_date = match.group(1).strip()
                break

        # Issuing authority (first line that looks like an authority name)
        auth_patterns = [
            r"^(.{10,100}(?:ministerio|policía|police|bureau|registro|gobierno|government).{0,50})$",
        ]
        for line in text.split("\n")[:20]:
            for pat in auth_patterns:
                match = re.search(pat, line.strip(), re.IGNORECASE | re.MULTILINE)
                if match:
                    result.issuing_authority = match.group(1).strip()
                    break
            if result.issuing_authority:
                break
