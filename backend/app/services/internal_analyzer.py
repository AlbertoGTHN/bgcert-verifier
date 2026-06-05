"""
Internal Document Analyzer
===========================
Activated as a *second-pass* when external web verification is unreachable
(DNS failure, timeout, SSL error, connection refused).

Instead of leaving the certificate as TECHNICAL_ISSUE the analyzer reads the
document itself and checks for:

  1. Completeness  – required fields are present
  2. Date validity – dates parse, issue date is in the past, expiry > issue
  3. Authority     – issuing authority contains official government keywords
                     and is consistent with the detected country
  4. OCR quality   – confidence score suggests a real, readable document
  5. Fraud check   – fraud_score from the fraud detector is low
  6. URL legitimacy– the unreachable QR URL at least *looks* official

Outcome
-------
  weighted_score >= 0.60  →  VERIFIED_INTERNAL   (confidence = weighted_score)
  weighted_score <  0.60  →  TECHNICAL_ISSUE      (unchanged, needs manual review)
  fraud_score > 0.60      →  FAILED_FRAUDULENT   (regardless of other checks)

The result always includes a human-readable summary listing every check that
passed or failed so analysts can audit the decision.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List

from loguru import logger


# ── Known official authority keywords (language-agnostic) ─────────────────────
# At least 2 must appear in the issuing_authority field to score positively.
AUTHORITY_KEYWORDS = [
    "police", "policia", "policía", "ministerio", "ministry",
    "gobierno", "government", "registro", "judicial", "bureau",
    "national", "nacional", "federal", "republic", "república",
    "justice", "justicia", "investigation", "investigación",
    "civil", "criminal", "nbi", "pnp", "rcmp", "afp", "fbi",
    "investigaciones", "seguridad", "interior", "gobernación",
    "corte", "court", "tribunal", "juzgado", "poder",
    "attorney", "fiscal", "procuraduría", "procuraduria",
    "department", "departamento", "secretaría", "secretaria",
    "dirección", "direccion", "division", "central",
]

# Expected language code per country (ISO 639-3 as stored by langdetect mapping)
COUNTRY_EXPECTED_LANG = {
    "Colombia": "spa", "Peru": "spa", "Mexico": "spa",
    "Chile": "spa", "Argentina": "spa", "Ecuador": "spa",
    "Venezuela": "spa", "Bolivia": "spa", "Paraguay": "spa",
    "Uruguay": "spa", "Costa Rica": "spa", "Panama": "spa",
    "El Salvador": "spa", "Honduras": "spa", "Guatemala": "spa",
    "Dominican Republic": "spa", "Spain": "spa",
    "Brazil": "por", "Portugal": "por",
    "France": "fra",
    "Philippines": "eng", "India": "eng", "Singapore": "eng",
    "United States": "eng", "United Kingdom": "eng",
    "Canada": "eng", "Australia": "eng", "New Zealand": "eng",
    "Malaysia": "eng",
    "Indonesia": "ind", "Vietnam": "vie",
}

# Official domain patterns (copied from web_verifier for standalone use)
OFFICIAL_DOMAIN_RE = re.compile(
    r"\.gov\b|\.gob\.\w+|\.gov\.\w+|\.go\.\w+|\.mil\b|"
    r"policianacional|policia\.gov|pnp\.gov|nbi\.gov|"
    r"registraduria|poder-judicial|judiciary|courts\.gov|"
    r"senainfo|dijin\.gov|fiscalia|antecedentes|certijoven",
    re.IGNORECASE,
)

# Date string formats to attempt parsing
DATE_FORMATS = [
    "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y",
    "%d.%m.%Y", "%Y/%m/%d", "%d %B %Y", "%B %d, %Y",
    "%d de %B de %Y",       # Spanish long form
]

SPANISH_MONTHS = {
    "enero": "january", "febrero": "february", "marzo": "march",
    "abril": "april", "mayo": "may", "junio": "june",
    "julio": "july", "agosto": "august", "septiembre": "september",
    "octubre": "october", "noviembre": "november", "diciembre": "december",
}


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class InternalAnalysisResult:
    status: str              # "VERIFIED_INTERNAL" | "TECHNICAL_ISSUE" | "FAILED_FRAUDULENT"
    confidence: float = 0.0
    summary: str = ""
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)
    weighted_score: float = 0.0


# ── Analyzer ──────────────────────────────────────────────────────────────────

class InternalAnalyzer:
    """Performs offline document analysis as a fallback verification step."""

    # Check weights (must sum to 1.0)
    WEIGHTS = {
        "completeness":  0.25,
        "date_validity": 0.20,
        "authority":     0.20,
        "ocr_quality":   0.15,
        "fraud_clear":   0.15,
        "url_legit":     0.05,
    }

    def analyze(
        self,
        *,
        holder_name: Optional[str],
        holder_id: Optional[str],
        cert_number: Optional[str],
        issue_date: Optional[str],
        expiry_date: Optional[str],
        issuing_authority: Optional[str],
        country: Optional[str],
        language_detected: Optional[str],
        ocr_confidence: Optional[float],
        ocr_text: Optional[str],
        fraud_score: float,
        qr_url: Optional[str],
        error_code: Optional[str],
    ) -> InternalAnalysisResult:

        result = InternalAnalysisResult(status="TECHNICAL_ISSUE")

        # ── Hard block: high fraud score overrides everything ─────────────
        if fraud_score > 0.60:
            result.status = "FAILED_FRAUDULENT"
            result.confidence = fraud_score
            result.summary = (
                f"Document FAILED internal analysis: fraud score {fraud_score:.0%} exceeds "
                f"threshold. Tampering indicators detected. Manual review required."
            )
            result.checks_failed.append(
                f"Fraud score {fraud_score:.0%} > 60% threshold"
            )
            return result

        scores: dict[str, float] = {}

        # ── 1. Completeness ───────────────────────────────────────────────
        scores["completeness"] = self._check_completeness(
            result, holder_name, holder_id, cert_number,
            issue_date, issuing_authority, country,
        )

        # ── 2. Date validity ──────────────────────────────────────────────
        scores["date_validity"] = self._check_dates(result, issue_date, expiry_date)

        # ── 3. Authority match ────────────────────────────────────────────
        scores["authority"] = self._check_authority(
            result, issuing_authority, country, language_detected,
        )

        # ── 4. OCR quality ────────────────────────────────────────────────
        scores["ocr_quality"] = self._check_ocr_quality(result, ocr_confidence, ocr_text)

        # ── 5. Fraud score ────────────────────────────────────────────────
        scores["fraud_clear"] = self._check_fraud(result, fraud_score)

        # ── 6. URL legitimacy ─────────────────────────────────────────────
        scores["url_legit"] = self._check_url(result, qr_url)

        # ── Weighted total ────────────────────────────────────────────────
        weighted = sum(scores[k] * self.WEIGHTS[k] for k in scores)
        result.weighted_score = round(weighted, 4)

        logger.info(
            f"Internal analysis scores: {scores} → weighted={weighted:.3f} "
            f"(fraud={fraud_score:.2f})"
        )

        # ── Decision ──────────────────────────────────────────────────────
        if weighted >= 0.60:
            result.status = "VERIFIED_INTERNAL"
            result.confidence = round(min(0.92, weighted), 4)
            passed_list = "; ".join(result.checks_passed[:5])
            result.summary = (
                f"✓ APPROVED BY INTERNAL ANALYSIS (score {weighted:.0%}). "
                f"Web verification was unavailable ({error_code or 'unreachable'}). "
                f"Document passed offline consistency checks: {passed_list}."
            )
        else:
            result.status = "TECHNICAL_ISSUE"
            result.confidence = 0.0
            failed_list = "; ".join(result.checks_failed[:5]) or "Insufficient data to approve"
            result.summary = (
                f"Internal analysis inconclusive (score {weighted:.0%} < 60% threshold). "
                f"Web verification was unavailable ({error_code or 'unreachable'}). "
                f"Issues: {failed_list}. Manual review required."
            )

        return result

    # ── Individual check methods ───────────────────────────────────────────

    def _check_completeness(
        self, result: InternalAnalysisResult,
        holder_name, holder_id, cert_number,
        issue_date, issuing_authority, country,
    ) -> float:
        score = 0.0

        if holder_name and len(holder_name.strip()) >= 3:
            score += 0.25
            result.checks_passed.append(f"Holder name present: {holder_name}")
        else:
            result.checks_failed.append("Holder name missing or too short")

        if holder_id or cert_number:
            score += 0.25
            val = holder_id or cert_number
            result.checks_passed.append(f"Document/cert number present: {val}")
        else:
            result.checks_failed.append("No ID or certificate number extracted")

        if issue_date:
            score += 0.20
            result.checks_passed.append(f"Issue date present: {issue_date}")
        else:
            result.checks_failed.append("Issue date missing")

        if issuing_authority and len(issuing_authority.strip()) >= 5:
            score += 0.20
            result.checks_passed.append(f"Issuing authority present: {issuing_authority[:60]}")
        else:
            result.checks_failed.append("Issuing authority missing or too short")

        if country:
            score += 0.10
            result.checks_passed.append(f"Country detected: {country}")
        else:
            result.checks_failed.append("Country not detected")

        return round(score, 4)

    def _check_dates(
        self, result: InternalAnalysisResult,
        issue_date_str: Optional[str],
        expiry_date_str: Optional[str],
    ) -> float:
        if not issue_date_str:
            result.checks_failed.append("Cannot validate dates — issue date not extracted")
            return 0.0

        issue_dt = self._parse_date(issue_date_str)
        if issue_dt is None:
            result.checks_failed.append(f"Issue date not parseable: '{issue_date_str}'")
            return 0.10  # partial credit: at least a date string was found

        score = 0.30  # parseable = 30%
        today = date.today()

        if issue_dt.date() < today:
            score += 0.30
            result.checks_passed.append(f"Issue date {issue_dt.date()} is in the past ✓")
        else:
            result.checks_failed.append(f"Issue date {issue_dt.date()} is in the future ✗")
            return score  # future-dated → stop here

        years_ago = (today - issue_dt.date()).days / 365
        if years_ago <= 15:
            score += 0.20
            result.checks_passed.append(f"Issue date within last 15 years ✓")
        else:
            result.checks_failed.append(f"Issue date is {years_ago:.0f} years ago — unusually old")

        if expiry_date_str:
            expiry_dt = self._parse_date(expiry_date_str)
            if expiry_dt and expiry_dt > issue_dt:
                score += 0.20
                result.checks_passed.append(f"Expiry date {expiry_dt.date()} is after issue date ✓")
            elif expiry_dt:
                result.checks_failed.append(
                    f"Expiry {expiry_dt.date()} is before or equal to issue date ✗"
                )
        else:
            score += 0.10  # no expiry is common for clearance letters

        return round(min(score, 1.0), 4)

    def _check_authority(
        self, result: InternalAnalysisResult,
        issuing_authority: Optional[str],
        country: Optional[str],
        language_detected: Optional[str],
    ) -> float:
        score = 0.0

        # Authority keyword check
        if issuing_authority:
            auth_lower = issuing_authority.lower()
            hits = [kw for kw in AUTHORITY_KEYWORDS if kw in auth_lower]
            unique_hits = list(set(hits))
            if len(unique_hits) >= 2:
                score += 0.50
                result.checks_passed.append(
                    f"Authority contains official keywords: {', '.join(unique_hits[:4])}"
                )
            elif len(unique_hits) == 1:
                score += 0.20
                result.checks_failed.append(
                    f"Authority has only 1 official keyword ({unique_hits[0]}) — weak signal"
                )
            else:
                result.checks_failed.append(
                    f"Authority '{issuing_authority[:50]}' has no recognized official keywords"
                )
        else:
            result.checks_failed.append("Issuing authority absent — cannot assess")

        # Country–language consistency
        if country and language_detected:
            expected_lang = COUNTRY_EXPECTED_LANG.get(country)
            if expected_lang and language_detected == expected_lang:
                score += 0.30
                result.checks_passed.append(
                    f"Document language '{language_detected}' matches {country} ✓"
                )
            elif expected_lang:
                # Not necessarily wrong (bilingual countries, etc.) — partial deduction
                score += 0.10
                result.checks_failed.append(
                    f"Language '{language_detected}' differs from expected "
                    f"'{expected_lang}' for {country} — verify manually"
                )
            else:
                score += 0.20  # country without expected-lang mapping → neutral
                result.checks_passed.append(f"Country {country} present (language check skipped)")
        elif country:
            score += 0.20
            result.checks_passed.append(f"Country '{country}' detected")
        else:
            result.checks_failed.append("Country unknown — authority match limited")

        return round(min(score, 1.0), 4)

    def _check_ocr_quality(
        self, result: InternalAnalysisResult,
        ocr_confidence: Optional[float],
        ocr_text: Optional[str],
    ) -> float:
        score = 0.0

        if ocr_confidence is not None:
            if ocr_confidence >= 0.80:
                score = 1.0
                result.checks_passed.append(f"OCR confidence {ocr_confidence:.0%} — excellent ✓")
            elif ocr_confidence >= 0.60:
                score = 0.70
                result.checks_passed.append(f"OCR confidence {ocr_confidence:.0%} — good ✓")
            elif ocr_confidence >= 0.40:
                score = 0.40
                result.checks_failed.append(
                    f"OCR confidence {ocr_confidence:.0%} — acceptable but low"
                )
            else:
                score = 0.10
                result.checks_failed.append(
                    f"OCR confidence {ocr_confidence:.0%} — very low, document may be unclear"
                )
        else:
            result.checks_failed.append("OCR confidence not available")

        # Bonus: extracted text has meaningful length
        if ocr_text and len(ocr_text.strip()) >= 200:
            score = min(score + 0.10, 1.0)
            result.checks_passed.append(
                f"OCR extracted {len(ocr_text)} characters of text ✓"
            )
        elif ocr_text:
            result.checks_failed.append(
                f"OCR text very short ({len(ocr_text)} chars) — limited data"
            )

        return round(score, 4)

    def _check_fraud(
        self, result: InternalAnalysisResult, fraud_score: float
    ) -> float:
        if fraud_score < 0.20:
            result.checks_passed.append(f"Fraud score {fraud_score:.0%} — clean ✓")
            return 1.0
        elif fraud_score < 0.40:
            result.checks_passed.append(f"Fraud score {fraud_score:.0%} — low risk ✓")
            return 0.70
        elif fraud_score < 0.60:
            result.checks_failed.append(
                f"Fraud score {fraud_score:.0%} — moderate risk, manual review advised"
            )
            return 0.30
        else:
            result.checks_failed.append(
                f"Fraud score {fraud_score:.0%} — high risk"
            )
            return 0.0

    def _check_url(
        self, result: InternalAnalysisResult, qr_url: Optional[str]
    ) -> float:
        if not qr_url:
            result.checks_failed.append("No QR URL to assess")
            return 0.0

        if OFFICIAL_DOMAIN_RE.search(qr_url):
            result.checks_passed.append(
                f"QR URL appears to be an official government domain ✓"
            )
            return 1.0

        # Check for IP address or known-bad patterns
        if re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", qr_url):
            result.checks_failed.append("QR URL is an IP address — suspicious")
            return 0.0

        if re.search(r"bit\.ly|tinyurl|goo\.gl", qr_url, re.IGNORECASE):
            result.checks_failed.append("QR URL uses a link shortener — suspicious")
            return 0.0

        # Neutral — domain doesn't match known patterns but isn't flagged
        result.checks_passed.append("QR URL has no obvious suspicious patterns")
        return 0.50

    # ── Date parsing helper ────────────────────────────────────────────────

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Try multiple date formats including Spanish month names."""
        if not date_str:
            return None

        # Normalize Spanish month names to English
        normalized = date_str.lower()
        for es, en in SPANISH_MONTHS.items():
            normalized = normalized.replace(es, en)

        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(normalized.strip(), fmt)
            except ValueError:
                continue

        # Try extracting a 4-digit year and guess
        year_match = re.search(r"\b(19|20)\d{2}\b", date_str)
        if year_match:
            year = int(year_match.group())
            if 2000 <= year <= date.today().year:
                try:
                    return datetime(year, 1, 1)  # approximate — year only
                except ValueError:
                    pass

        return None
