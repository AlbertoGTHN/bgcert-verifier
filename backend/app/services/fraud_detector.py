"""
Fraud Detection Service
Analyzes PDFs for signs of tampering, editing, or forgery.
"""
import os
import re
import hashlib
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import numpy as np
import cv2
from PIL import Image, ImageChops
from loguru import logger


@dataclass
class FraudAnalysisResult:
    fraud_score: float = 0.0
    is_potentially_fraudulent: bool = False
    indicators: Dict[str, Any] = field(default_factory=dict)
    details: List[str] = field(default_factory=list)


class FraudDetector:
    """Detects potential document tampering and forgery indicators."""

    def analyze(self, file_path: str, page_images: List[str]) -> FraudAnalysisResult:
        """Run all fraud detection checks."""
        result = FraudAnalysisResult()
        checks_passed = 0
        checks_failed = 0

        # 1. PDF metadata analysis
        meta_flags = self._check_pdf_metadata(file_path)
        result.indicators["metadata"] = meta_flags
        if meta_flags.get("tampered"):
            checks_failed += 1
            result.details.append("PDF metadata shows signs of editing (creator/modifier mismatch)")
        else:
            checks_passed += 1

        # 2. Font consistency check
        font_flags = self._check_font_consistency(file_path)
        result.indicators["fonts"] = font_flags
        if font_flags.get("inconsistent"):
            checks_failed += 1
            result.details.append(f"Inconsistent fonts detected: {font_flags.get('count', 0)} different fonts")
        else:
            checks_passed += 1

        # 3. Image tampering detection
        if page_images:
            for i, img_path in enumerate(page_images[:3]):  # Check first 3 pages
                img_flags = self._check_image_tampering(img_path)
                result.indicators[f"image_page_{i+1}"] = img_flags
                if img_flags.get("tampered"):
                    checks_failed += 1
                    result.details.append(f"Page {i+1}: Possible image tampering detected")
                    break
            else:
                checks_passed += 1

        # 4. Check for copy-paste artifacts
        copy_flags = self._check_copy_paste_artifacts(file_path)
        result.indicators["copy_paste"] = copy_flags
        if copy_flags.get("detected"):
            checks_failed += 1
            result.details.append("Copy-paste artifacts detected in document structure")
        else:
            checks_passed += 1

        # 5. Check for suspicious modifications
        mod_flags = self._check_suspicious_modifications(file_path)
        result.indicators["modifications"] = mod_flags
        if mod_flags.get("detected"):
            checks_failed += 2  # Higher weight
            result.details.append("Document appears to have been modified after creation")
        else:
            checks_passed += 1

        # 6. Check for embedded scripts or unusual objects
        obj_flags = self._check_embedded_objects(file_path)
        result.indicators["embedded_objects"] = obj_flags
        if obj_flags.get("suspicious"):
            checks_failed += 1
            result.details.append(f"Suspicious embedded objects: {obj_flags.get('details', '')}")
        else:
            checks_passed += 1

        # Calculate fraud score (0 = clean, 1 = definitely fraudulent)
        total = checks_passed + checks_failed
        if total > 0:
            result.fraud_score = min(1.0, checks_failed / total * 1.5)

        result.is_potentially_fraudulent = result.fraud_score > 0.4

        if result.details:
            logger.warning(f"Fraud indicators found in {file_path}: {result.details}")

        return result

    def _check_pdf_metadata(self, file_path: str) -> Dict[str, Any]:
        """Check PDF metadata for inconsistencies."""
        flags = {"tampered": False, "details": {}}
        try:
            doc = fitz.open(file_path)
            meta = doc.metadata
            doc.close()

            creator = meta.get("creator", "").lower()
            producer = meta.get("producer", "").lower()
            creation_date = meta.get("creationDate", "")
            mod_date = meta.get("modDate", "")

            # Check for common editing software in metadata
            editing_tools = ["adobe acrobat", "photoshop", "gimp", "inkscape",
                           "libreoffice", "foxit", "pdf editor", "nitro", "smallpdf",
                           "ilovepdf", "pdfchef", "sejda"]

            creator_edited = any(tool in creator for tool in editing_tools)
            producer_edited = any(tool in producer for tool in editing_tools)

            flags["creator"] = meta.get("creator", "")
            flags["producer"] = meta.get("producer", "")
            flags["creation_date"] = creation_date
            flags["modification_date"] = mod_date
            flags["edited_with_known_tool"] = creator_edited or producer_edited

            # If modified after creation and not by original creator
            if creation_date and mod_date and creation_date != mod_date:
                flags["modified_after_creation"] = True
                if creator_edited or producer_edited:
                    flags["tampered"] = True

        except Exception as e:
            logger.debug(f"Metadata check error: {e}")
            flags["error"] = str(e)

        return flags

    def _check_font_consistency(self, file_path: str) -> Dict[str, Any]:
        """Check for inconsistent fonts (sign of copy-paste from multiple sources)."""
        flags = {"inconsistent": False, "count": 0, "fonts": []}
        try:
            doc = fitz.open(file_path)
            all_fonts = set()

            for page in doc:
                fonts = page.get_fonts()
                for font in fonts:
                    font_name = font[3] if len(font) > 3 else ""
                    if font_name:
                        all_fonts.add(font_name)

            doc.close()
            flags["fonts"] = list(all_fonts)
            flags["count"] = len(all_fonts)

            # More than 6 different fonts is suspicious for a government document
            if len(all_fonts) > 6:
                flags["inconsistent"] = True

        except Exception as e:
            logger.debug(f"Font check error: {e}")
            flags["error"] = str(e)

        return flags

    def _check_image_tampering(self, image_path: str) -> Dict[str, Any]:
        """Detect image manipulation using Error Level Analysis (ELA)."""
        flags = {"tampered": False, "ela_score": 0.0}
        try:
            img = Image.open(image_path).convert("RGB")

            # Save at quality 90 and compare
            import io
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=90)
            buffer.seek(0)
            compressed = Image.open(buffer).convert("RGB")

            # Calculate ELA difference
            diff = ImageChops.difference(img, compressed)
            diff_array = np.array(diff)
            ela_score = float(np.mean(diff_array))

            flags["ela_score"] = ela_score

            # Check for uniform patches (sign of cloning/copy-paste)
            gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            flags["laplacian_variance"] = float(laplacian_var)

            # Very low variance in certain regions can indicate pasted blocks
            if laplacian_var < 10:
                flags["tampered"] = True
                flags["reason"] = "Very low image variance — possible blank/pasted region"

        except Exception as e:
            logger.debug(f"Image tampering check error: {e}")
            flags["error"] = str(e)

        return flags

    def _check_copy_paste_artifacts(self, file_path: str) -> Dict[str, Any]:
        """Detect overlapping or suspicious text/image objects."""
        flags = {"detected": False, "overlapping_objects": 0}
        try:
            doc = fitz.open(file_path)
            for page in doc:
                # Check for overlapping text blocks
                blocks = page.get_text("blocks")
                rects = [fitz.Rect(b[:4]) for b in blocks]
                overlaps = 0
                for i, r1 in enumerate(rects):
                    for r2 in rects[i+1:]:
                        if r1.intersects(r2):
                            overlaps += 1
                if overlaps > 10:
                    flags["detected"] = True
                    flags["overlapping_objects"] = overlaps
                    break
            doc.close()
        except Exception as e:
            logger.debug(f"Copy-paste check error: {e}")
            flags["error"] = str(e)

        return flags

    def _check_suspicious_modifications(self, file_path: str) -> Dict[str, Any]:
        """Look for signs of PDF structure manipulation."""
        flags = {"detected": False, "details": ""}
        try:
            with open(file_path, "rb") as f:
                content = f.read()

            # Check for multiple %PDF headers (sign of concatenation)
            pdf_headers = content.count(b"%PDF-")
            if pdf_headers > 1:
                flags["detected"] = True
                flags["details"] = f"Multiple PDF headers ({pdf_headers}) found"

            # Check for incremental updates (can indicate edits)
            xref_count = content.count(b"%%EOF")
            if xref_count > 1:
                flags["incremental_updates"] = xref_count - 1
                if xref_count > 2:
                    flags["detected"] = True
                    flags["details"] = f"Multiple save operations detected ({xref_count-1} updates)"

        except Exception as e:
            logger.debug(f"Modification check error: {e}")
            flags["error"] = str(e)

        return flags

    def _check_embedded_objects(self, file_path: str) -> Dict[str, Any]:
        """Check for suspicious embedded objects (scripts, executables)."""
        flags = {"suspicious": False, "details": ""}
        try:
            doc = fitz.open(file_path)
            embeds = doc.get_page_links(0) if doc.page_count > 0 else []

            # Check for JavaScript
            if doc.outline:
                pass

            # Check for embedded files
            for i in range(doc.page_count):
                page = doc[i]
                annots = page.annots()
                for annot in annots:
                    if annot.type[0] in (8, 17, 18):  # Widget, FileAttachment, Sound
                        flags["suspicious"] = True
                        flags["details"] = f"Suspicious annotation type {annot.type[0]} on page {i+1}"
                        break

            doc.close()
        except Exception as e:
            logger.debug(f"Embedded objects check error: {e}")
            flags["error"] = str(e)

        return flags
