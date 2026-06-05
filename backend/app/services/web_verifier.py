"""
Web Verification Service
Visits QR code URLs using a headless browser, analyzes content,
and classifies certificates as VERIFIED, FAILED, or TECHNICAL_ISSUE.

Supports three verification modes:
  1. browser   — Playwright headless Chromium (HTML pages)
  2. file_download — URL returns a TXT/JSON/XML/CSV/PDF file; content is
                     downloaded and compared against the holder's name / ID
  3. httpx     — Lightweight HTTP fallback when Playwright is unavailable
"""
import os
import re
import asyncio
import hashlib
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlparse

import httpx
import tldextract
from loguru import logger

from app.config import settings

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available — web verification disabled")


# ─── Verification keyword lists ────────────────────────────────────────────

VALID_KEYWORDS = [
    # English
    "valid", "verified", "authentic", "cleared", "no criminal record",
    "certificate is valid", "found in registry", "record found",
    "background check passed", "clean record",
    # Spanish
    "válido", "auténtico", "verificado", "sin antecedentes",
    "certificado válido", "registro encontrado", "documento auténtico",
    "sin registros", "apto", "sin antecedentes penales",
    "sin anotaciones", "no registra antecedentes",
    # Portuguese
    "válido", "autêntico", "verificado", "sem antecedentes",
    "certidão válida", "sem registros criminais", "documento válido",
    # French
    "valide", "authentique", "vérifié", "aucun antécédent",
    "certificat valide",
]

INVALID_KEYWORDS = [
    # English
    "invalid", "not found", "does not exist", "expired", "revoked",
    "fake", "fraudulent", "tampered", "not valid", "not authentic",
    "not verified", "not in registry", "certificate not found",
    # Spanish
    "inválido", "no encontrado", "no existe", "expirado", "revocado",
    "falso", "fraudulento", "no válido", "no auténtico",
    "no se encontró", "documento inválido", "no registra",
    "certificado inválido", "no aparece", "sin registro",
    # Portuguese
    "inválido", "não encontrado", "não existe", "expirado", "revogado",
    "falso", "fraudulento", "não válido",
    # French
    "invalide", "non trouvé", "n'existe pas", "expiré", "révoqué",
]

CAPTCHA_KEYWORDS = [
    "captcha", "recaptcha", "robot", "human verification",
    "verificación humana", "not a robot", "prove you are human",
    "security check", "access denied", "cloudflare",
]

OFFICIAL_DOMAIN_PATTERNS = [
    r"\.gov\b", r"\.gob\.\w+", r"\.gov\.\w+", r"\.go\.\w+",
    r"\.mil\b", r"\.mil\.\w+", r"\.edu\.gov",
    r"policianacional", r"policia\.gov", r"pnp\.gov",
    r"nbi\.gov", r"ministerio\w*\.gov", r"registrocivil",
    r"senainfo", r"dijin\.gov", r"fiscalia\.gov",
    r"registraduria", r"judicatura", r"poder-judicial",
    r"judiciary\.\w+\.gov", r"courts\.gov",
    r"acro\.police\.uk", r"homeoffice\.gov\.uk",
    r"police\.gov\.\w+", r"moj\.gov",
    r"antecedentes\.\w+\.gov", r"certijoven",
    r"validacertificado", r"validacion\.\w+\.gov",
]

SUSPICIOUS_DOMAIN_PATTERNS = [
    r"bit\.ly", r"tinyurl", r"goo\.gl", r"t\.co",  # URL shorteners
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",         # IP address
    r"\.xyz$", r"\.tk$", r"\.ml$", r"\.ga$",         # Suspicious TLDs
    r"free", r"cheap", r"verify-now", r"instant-verify",
]

# Content-Types that signal a direct file download rather than an HTML page
DOWNLOADABLE_CONTENT_TYPES = (
    "text/plain",
    "application/json",
    "text/json",
    "text/xml",
    "application/xml",
    "text/csv",
    "application/csv",
    "application/pdf",
)

# URL path extensions that signal a direct file
DOWNLOADABLE_EXTENSIONS = (".txt", ".json", ".xml", ".csv", ".pdf")


@dataclass
class VerificationResult:
    url: str
    status: str  # VERIFIED_AUTHENTIC | FAILED_FRAUDULENT | TECHNICAL_ISSUE
    confidence: float = 0.0
    is_official_domain: bool = False
    domain: str = ""
    page_title: str = ""
    page_text: str = ""
    screenshot_path: Optional[str] = None
    screenshot_url: Optional[str] = None
    valid_keywords_found: List[str] = field(default_factory=list)
    invalid_keywords_found: List[str] = field(default_factory=list)
    has_captcha: bool = False
    error: Optional[str] = None
    error_code: Optional[str] = None
    http_status: Optional[int] = None
    final_url: Optional[str] = None
    validation_summary: str = ""
    # File-download verification extras
    verification_method: str = "browser"   # "browser" | "file_download" | "httpx"
    identity_match: Optional[bool] = None  # True/False/None(not attempted)
    downloaded_content_preview: Optional[str] = None  # first 300 chars for UI


class WebVerifier:
    """Headless browser-based certificate verification."""

    def __init__(self):
        self.screenshot_dir = settings.SCREENSHOT_DIR
        os.makedirs(self.screenshot_dir, exist_ok=True)

    async def verify(
        self,
        url: str,
        cert_id: str,
        holder_name: Optional[str] = None,
        holder_id: Optional[str] = None,
    ) -> VerificationResult:
        """Main verification entry point.

        Steps:
        1. Probe the URL with a HEAD request to detect Content-Type.
        2. If the server returns a file (TXT/JSON/XML/CSV/PDF), download it
           and verify by checking whether the holder's name / ID appear in
           the file content.
        3. Otherwise fall through to the Playwright (or httpx) browser path.
        """
        if not url or len(url.strip()) < 8:
            return VerificationResult(
                url=url,
                status="FAILED_FRAUDULENT",
                confidence=0.0,
                error="Invalid or empty URL",
                error_code="INVALID_URL",
                validation_summary="QR code contains no valid URL",
            )

        # ── Step 1: probe for file response ─────────────────────────────────
        is_file, content_type = await self._probe_url_type(url)
        if is_file:
            logger.info(f"[{cert_id}] File response detected ({content_type}), using file-download path")
            result = await self._download_and_verify_file(
                url, cert_id, content_type, holder_name, holder_id
            )
            self._analyze_result(result, url)
            return result

        # ── Step 2: browser / httpx path ─────────────────────────────────────
        if not PLAYWRIGHT_AVAILABLE:
            return self._verify_with_httpx(url, cert_id)

        return await self._verify_with_playwright(url, cert_id)

    # ── File-download helpers ──────────────────────────────────────────────

    async def _probe_url_type(self, url: str) -> tuple[bool, str]:
        """Return (is_downloadable_file, content_type).

        Uses a HEAD request; falls back to URL extension analysis if HEAD
        fails or returns no Content-Type.
        """
        # Extension check first (fastest, no network)
        path = urlparse(url).path.lower()
        if any(path.endswith(ext) for ext in DOWNLOADABLE_EXTENSIONS):
            ext = next(e for e in DOWNLOADABLE_EXTENSIONS if path.endswith(e))
            ct_map = {
                ".txt": "text/plain",
                ".json": "application/json",
                ".xml": "text/xml",
                ".csv": "text/csv",
                ".pdf": "application/pdf",
            }
            return True, ct_map[ext]

        try:
            async with httpx.AsyncClient(
                timeout=10,
                follow_redirects=True,
                verify=False,
            ) as client:
                resp = await client.head(url)
                ct = resp.headers.get("content-type", "").lower().split(";")[0].strip()
                if any(ct.startswith(dc) for dc in DOWNLOADABLE_CONTENT_TYPES):
                    # Treat HTML as a normal browser page, not a download
                    if "text/html" not in ct:
                        return True, ct
        except Exception as e:
            logger.debug(f"HEAD probe failed for {url}: {e}")

        return False, ""

    async def _download_and_verify_file(
        self,
        url: str,
        cert_id: str,
        content_type: str,
        holder_name: Optional[str],
        holder_id: Optional[str],
    ) -> VerificationResult:
        """Download the file at *url* and verify identity against holder info."""
        result = VerificationResult(
            url=url,
            status="TECHNICAL_ISSUE",
            verification_method="file_download",
        )

        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                verify=False,
            ) as client:
                resp = await client.get(url)
                result.http_status = resp.status_code
                result.final_url = str(resp.url)

                if resp.status_code >= 400:
                    result.status = "FAILED_FRAUDULENT"
                    result.confidence = 0.75
                    result.validation_summary = (
                        f"Verification file endpoint returned HTTP {resp.status_code}"
                    )
                    return result

                # Extract text from the file
                file_text = self._extract_text_from_response(resp, content_type)
                result.page_text = file_text
                result.downloaded_content_preview = file_text[:300] if file_text else None

        except httpx.TimeoutException:
            result.error = "File download timed out"
            result.error_code = "TIMEOUT"
            result.validation_summary = "Could not download verification file (timeout)"
            return result
        except Exception as e:
            result.error = f"File download error: {e}"
            result.error_code = "DOWNLOAD_ERROR"
            result.validation_summary = f"Could not download verification file: {e}"
            return result

        if not file_text:
            result.status = "TECHNICAL_ISSUE"
            result.validation_summary = "Downloaded file was empty or unreadable"
            return result

        # ── Identity matching ────────────────────────────────────────────────
        if holder_name or holder_id:
            matched, match_detail = self._check_identity_match(
                file_text, holder_name, holder_id
            )
            result.identity_match = matched

            if matched:
                result.status = "VERIFIED_AUTHENTIC"
                result.confidence = 0.92
                result.validation_summary = (
                    f"Identity CONFIRMED in verification file. {match_detail}"
                )
                # Also scan for explicit invalid keywords as a safety check
                text_lower = file_text.lower()
                if any(kw in text_lower for kw in INVALID_KEYWORDS):
                    result.status = "FAILED_FRAUDULENT"
                    result.confidence = 0.90
                    result.validation_summary = (
                        f"Verification file contains INVALID markers "
                        f"despite name match. Manual review required."
                    )
            else:
                # Name/ID not found — check for generic valid/invalid keywords
                text_lower = file_text.lower()
                invalid_hits = [kw for kw in INVALID_KEYWORDS if kw in text_lower]
                valid_hits = [kw for kw in VALID_KEYWORDS if kw in text_lower]

                if invalid_hits:
                    result.status = "FAILED_FRAUDULENT"
                    result.confidence = 0.85
                    result.validation_summary = (
                        f"Identity NOT found in file and file contains "
                        f"invalid markers: {', '.join(invalid_hits[:3])}"
                    )
                elif valid_hits:
                    # File says something is valid but doesn't match our holder
                    result.status = "TECHNICAL_ISSUE"
                    result.confidence = 0.3
                    result.validation_summary = (
                        f"File appears valid but holder identity "
                        f"({holder_name or holder_id}) was NOT found in content. "
                        f"Manual review required."
                    )
                else:
                    result.status = "TECHNICAL_ISSUE"
                    result.confidence = 0.0
                    result.validation_summary = (
                        f"Holder identity not found in verification file. "
                        f"File may use a different format. Manual review required."
                    )
        else:
            # No holder info — fall back to keyword matching on file content
            text_lower = file_text.lower()
            valid_hits = [kw for kw in VALID_KEYWORDS if kw in text_lower]
            invalid_hits = [kw for kw in INVALID_KEYWORDS if kw in text_lower]
            result.valid_keywords_found = valid_hits
            result.invalid_keywords_found = invalid_hits

            if invalid_hits:
                result.status = "FAILED_FRAUDULENT"
                result.confidence = 0.80
                result.validation_summary = (
                    f"Verification file contains invalid markers: "
                    f"{', '.join(invalid_hits[:3])}"
                )
            elif valid_hits:
                result.status = "VERIFIED_AUTHENTIC"
                result.confidence = 0.70
                result.validation_summary = (
                    f"Verification file contains valid markers: "
                    f"{', '.join(valid_hits[:3])}"
                )
            else:
                result.status = "TECHNICAL_ISSUE"
                result.confidence = 0.0
                result.validation_summary = (
                    "Downloaded file content does not conclusively "
                    "confirm or deny validity. Manual review required."
                )

        return result

    def _extract_text_from_response(self, resp: httpx.Response, content_type: str) -> str:
        """Extract readable text from an HTTP response based on its Content-Type."""
        ct = content_type.lower()

        if "application/pdf" in ct:
            try:
                import fitz  # PyMuPDF
                import io
                doc = fitz.open(stream=resp.content, filetype="pdf")
                pages_text = [page.get_text() for page in doc]
                doc.close()
                return "\n".join(pages_text)
            except Exception as e:
                logger.warning(f"PDF text extraction from download failed: {e}")
                return ""

        if "application/json" in ct or "text/json" in ct:
            try:
                import json
                data = resp.json()
                # Flatten JSON to string for identity matching
                return json.dumps(data, ensure_ascii=False, indent=1)
            except Exception:
                pass  # fall through to raw text

        if "text/xml" in ct or "application/xml" in ct:
            try:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(resp.text)
                texts = [elem.text for elem in root.iter() if elem.text and elem.text.strip()]
                return " ".join(texts)
            except Exception:
                pass  # fall through to raw text

        # text/plain, text/csv, or fallback
        try:
            return resp.text
        except Exception:
            try:
                return resp.content.decode("utf-8", errors="replace")
            except Exception:
                return ""

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase, remove accents, collapse whitespace."""
        nfkd = unicodedata.normalize("NFKD", text)
        ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
        return re.sub(r"\s+", " ", ascii_text).strip().lower()

    def _check_identity_match(
        self,
        file_text: str,
        holder_name: Optional[str],
        holder_id: Optional[str],
    ) -> tuple[bool, str]:
        """Return (matched: bool, detail: str).

        Strategy:
        - ID match: exact normalized substring search (highest confidence)
        - Name match: at least 2 consecutive words of the name appear
          as a substring in the file (handles middle-name omissions)
        """
        norm_file = self._normalize(file_text)

        # 1. ID / document number match (strongest signal)
        if holder_id:
            norm_id = self._normalize(holder_id)
            if norm_id and len(norm_id) >= 4 and norm_id in norm_file:
                return True, f"Document ID '{holder_id}' found in file."

        # 2. Name match: require at least 2 consecutive words
        if holder_name:
            words = [w for w in self._normalize(holder_name).split() if len(w) >= 2]
            if len(words) >= 2:
                # Try consecutive pairs and triples
                for window in range(min(len(words), 4), 1, -1):
                    for start in range(len(words) - window + 1):
                        phrase = " ".join(words[start: start + window])
                        if len(phrase) >= 5 and phrase in norm_file:
                            return True, f"Name '{phrase}' found in file."
            elif len(words) == 1 and len(words[0]) >= 5:
                if words[0] in norm_file:
                    return True, f"Name '{words[0]}' found in file."

        return False, ""

    async def _verify_with_playwright(self, url: str, cert_id: str) -> VerificationResult:
        """Full verification using Playwright headless browser."""
        result = VerificationResult(url=url, status="TECHNICAL_ISSUE")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=settings.PLAYWRIGHT_HEADLESS,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-extensions",
                    ],
                )

                context = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    locale="en-US,es;q=0.9",
                    ignore_https_errors=True,
                )

                page = await context.new_page()

                try:
                    response = await page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=settings.PLAYWRIGHT_TIMEOUT_MS,
                    )

                    result.http_status = response.status if response else None
                    result.final_url = page.url

                    # Wait a bit for JS to render
                    await asyncio.sleep(2)

                    # Extract page content
                    result.page_title = await page.title()
                    result.page_text = await page.evaluate("() => document.body ? document.body.innerText : ''")

                    # Take screenshot
                    screenshot_filename = f"screenshot_{cert_id}_{int(time.time())}.png"
                    screenshot_path = os.path.join(self.screenshot_dir, screenshot_filename)
                    await page.screenshot(
                        path=screenshot_path,
                        full_page=True,
                        timeout=settings.SCREENSHOT_TIMEOUT_MS,
                    )
                    result.screenshot_path = screenshot_path
                    result.screenshot_url = f"/screenshots/{screenshot_filename}"

                except PlaywrightTimeout:
                    result.error = "Page load timeout"
                    result.error_code = "TIMEOUT"
                    # Still try screenshot
                    try:
                        screenshot_filename = f"screenshot_{cert_id}_timeout.png"
                        screenshot_path = os.path.join(self.screenshot_dir, screenshot_filename)
                        await page.screenshot(path=screenshot_path, timeout=5000)
                        result.screenshot_path = screenshot_path
                        result.screenshot_url = f"/screenshots/{screenshot_filename}"
                    except Exception:
                        pass

                except Exception as e:
                    error_str = str(e).lower()
                    if "ssl" in error_str or "cert" in error_str:
                        result.error = f"SSL/TLS error: {e}"
                        result.error_code = "SSL_ERROR"
                    elif "dns" in error_str or "name not resolved" in error_str:
                        result.error = f"DNS error: {e}"
                        result.error_code = "DNS_ERROR"
                    elif "connection refused" in error_str or "connection reset" in error_str:
                        result.error = f"Connection error: {e}"
                        result.error_code = "CONNECTION_ERROR"
                    else:
                        result.error = f"Navigation error: {e}"
                        result.error_code = "NAVIGATION_ERROR"

                await context.close()
                await browser.close()

        except Exception as e:
            result.error = f"Browser error: {e}"
            result.error_code = "BROWSER_ERROR"
            logger.error(f"Playwright error for {url}: {e}", exc_info=True)

        # Analyze results
        self._analyze_result(result, url)
        return result

    def _verify_with_httpx(self, url: str, cert_id: str) -> VerificationResult:
        """Fallback: simple HTTP request without headless browser."""
        import httpx

        result = VerificationResult(url=url, status="TECHNICAL_ISSUE")
        try:
            with httpx.Client(
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
                follow_redirects=True,
                verify=False,
            ) as client:
                response = client.get(url)
                result.http_status = response.status_code
                result.final_url = str(response.url)
                result.page_text = response.text[:50000]
                result.page_title = self._extract_title(response.text)

        except httpx.TimeoutException:
            result.error = "Request timeout"
            result.error_code = "TIMEOUT"
        except httpx.ConnectError as e:
            result.error = f"Connection error: {e}"
            result.error_code = "CONNECTION_ERROR"
        except Exception as e:
            result.error = f"HTTP error: {e}"
            result.error_code = "HTTP_ERROR"

        self._analyze_result(result, url)
        return result

    def _analyze_result(self, result: VerificationResult, original_url: str):
        """Classify the verification result based on page content and domain."""
        # Domain analysis
        try:
            parsed = urlparse(result.final_url or original_url)
            result.domain = parsed.netloc.lower()
        except Exception:
            result.domain = ""

        result.is_official_domain = self._is_official_domain(result.domain)
        is_suspicious = self._is_suspicious_domain(result.domain)

        # If we have an error, determine if it's technical or fraudulent
        if result.error_code:
            if result.error_code in ("DNS_ERROR", "TIMEOUT", "CONNECTION_ERROR",
                                      "SSL_ERROR", "BROWSER_ERROR", "NAVIGATION_ERROR"):
                result.status = "TECHNICAL_ISSUE"
                result.confidence = 0.0
                result.validation_summary = f"Could not verify: {result.error}"
                return
            elif result.error_code in ("INVALID_URL",):
                result.status = "FAILED_FRAUDULENT"
                result.confidence = 0.8
                result.validation_summary = result.error
                return

        # Check for CAPTCHA
        if result.page_text:
            for kw in CAPTCHA_KEYWORDS:
                if kw.lower() in result.page_text.lower():
                    result.has_captcha = True
                    result.status = "TECHNICAL_ISSUE"
                    result.confidence = 0.0
                    result.validation_summary = "Verification blocked by CAPTCHA"
                    return

        # No content at all
        if not result.page_text and not result.page_title:
            if is_suspicious:
                result.status = "FAILED_FRAUDULENT"
                result.confidence = 0.7
                result.validation_summary = "QR leads to suspicious/empty domain"
            else:
                result.status = "TECHNICAL_ISSUE"
                result.confidence = 0.0
                result.validation_summary = "Empty page — could not verify"
            return

        # HTTP error codes
        if result.http_status and result.http_status >= 400:
            result.status = "FAILED_FRAUDULENT"
            result.confidence = 0.75
            result.validation_summary = f"Verification page returned HTTP {result.http_status}"
            return

        # Keyword matching
        text_lower = (result.page_text + " " + result.page_title).lower()

        valid_found = [kw for kw in VALID_KEYWORDS if kw.lower() in text_lower]
        invalid_found = [kw for kw in INVALID_KEYWORDS if kw.lower() in text_lower]

        result.valid_keywords_found = valid_found
        result.invalid_keywords_found = invalid_found

        valid_score = len(valid_found)
        invalid_score = len(invalid_found)

        # Scoring
        domain_bonus = 0.2 if result.is_official_domain else -0.1
        domain_penalty = -0.3 if is_suspicious else 0.0

        if invalid_score > 0 and invalid_score >= valid_score:
            # Explicitly marked invalid
            result.status = "FAILED_FRAUDULENT"
            result.confidence = min(0.95, 0.5 + (invalid_score * 0.1) - domain_penalty)
            result.validation_summary = (
                f"Verification page indicates certificate is INVALID. "
                f"Keywords: {', '.join(invalid_found[:3])}"
            )

        elif valid_score > 0:
            # Verified
            result.status = "VERIFIED_AUTHENTIC"
            base_conf = 0.6 + (valid_score * 0.05) + domain_bonus
            result.confidence = min(0.99, max(0.5, base_conf))
            result.validation_summary = (
                f"Certificate appears AUTHENTIC. "
                f"Official domain: {result.is_official_domain}. "
                f"Keywords: {', '.join(valid_found[:3])}"
            )

        elif result.is_official_domain and result.http_status == 200:
            # Official domain but no clear keywords — inconclusive, lean toward technical
            result.status = "TECHNICAL_ISSUE"
            result.confidence = 0.3
            result.validation_summary = (
                "Reached official domain but no clear validation confirmation found. "
                "Manual review recommended."
            )

        else:
            # Suspicious or no useful content
            if is_suspicious:
                result.status = "FAILED_FRAUDULENT"
                result.confidence = 0.65
                result.validation_summary = "QR redirects to suspicious domain — possible fraud"
            else:
                result.status = "TECHNICAL_ISSUE"
                result.confidence = 0.0
                result.validation_summary = "Unable to determine certificate validity from page content"

    def _is_official_domain(self, domain: str) -> bool:
        if not domain:
            return False
        for pattern in OFFICIAL_DOMAIN_PATTERNS:
            if re.search(pattern, domain, re.IGNORECASE):
                return True
        # Check via tldextract
        try:
            ext = tldextract.extract(domain)
            if ext.suffix in ("gov", "mil", "edu"):
                return True
            if "gov" in ext.domain or "police" in ext.domain or "ministry" in ext.domain:
                return True
        except Exception:
            pass
        return False

    def _is_suspicious_domain(self, domain: str) -> bool:
        if not domain:
            return True
        for pattern in SUSPICIOUS_DOMAIN_PATTERNS:
            if re.search(pattern, domain, re.IGNORECASE):
                return True
        return False

    def _extract_title(self, html: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""
