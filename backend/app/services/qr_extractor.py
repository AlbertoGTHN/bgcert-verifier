"""
QR Code Extraction Service
Detects and decodes QR codes from document images using multiple methods.
"""
import os
from typing import List, Optional, Tuple
from dataclasses import dataclass

import numpy as np
import cv2
from PIL import Image
from loguru import logger

try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
    logger.warning("pyzbar not available")

try:
    import zxingcpp
    ZXING_AVAILABLE = True
except ImportError:
    ZXING_AVAILABLE = False
    logger.warning("zxingcpp not available")


@dataclass
class QRResult:
    data: str
    url: str
    page_num: int
    method: str
    confidence: float
    bbox: Optional[Tuple[int, int, int, int]] = None


class QRExtractor:
    """Multi-method QR code extractor with fallback strategies."""

    def extract_from_images(self, image_paths: List[str]) -> Optional[QRResult]:
        """
        Try to extract a QR code from a list of page images.
        Returns the first successful result.
        """
        for page_num, image_path in enumerate(image_paths, 1):
            result = self._extract_from_single_image(image_path, page_num)
            if result:
                logger.info(f"QR found on page {page_num} via {result.method}: {result.url[:80]}")
                return result

        logger.info("No QR code found in document")
        return None

    def _extract_from_single_image(self, image_path: str, page_num: int) -> Optional[QRResult]:
        """Try all extraction methods on a single image."""
        try:
            img_pil = Image.open(image_path)
            img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(f"Failed to load image {image_path}: {e}")
            return None

        # Strategy 1: pyzbar on original image
        result = self._try_pyzbar(img_cv, page_num, "pyzbar_original")
        if result:
            return result

        # Strategy 2: pyzbar on preprocessed image
        preprocessed = self._preprocess_for_qr(img_cv)
        result = self._try_pyzbar(preprocessed, page_num, "pyzbar_preprocessed")
        if result:
            return result

        # Strategy 3: OpenCV built-in QR detector
        result = self._try_opencv_qr(img_cv, page_num)
        if result:
            return result

        # Strategy 4: ZXing (more robust for rotated/damaged QRs)
        if ZXING_AVAILABLE:
            result = self._try_zxing(img_pil, page_num)
            if result:
                return result

        # Strategy 5: Try on image regions / cropped sections
        result = self._try_regions(img_cv, page_num)
        if result:
            return result

        # Strategy 6: Try with rotations
        result = self._try_rotations(img_cv, page_num)
        if result:
            return result

        return None

    def _try_pyzbar(self, img: np.ndarray, page_num: int, method: str) -> Optional[QRResult]:
        """Attempt QR decode using pyzbar."""
        if not PYZBAR_AVAILABLE:
            return None
        try:
            # Convert to grayscale for pyzbar
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img

            decoded_objects = pyzbar.decode(gray)
            for obj in decoded_objects:
                if obj.type in ("QRCODE", "QR_CODE"):
                    data = obj.data.decode("utf-8", errors="replace").strip()
                    if data and len(data) > 5:
                        rect = obj.rect
                        return QRResult(
                            data=data,
                            url=self._normalize_url(data),
                            page_num=page_num,
                            method=method,
                            confidence=0.95,
                            bbox=(rect.left, rect.top, rect.left + rect.width, rect.top + rect.height),
                        )
        except Exception as e:
            logger.debug(f"pyzbar failed ({method}): {e}")
        return None

    def _try_opencv_qr(self, img: np.ndarray, page_num: int) -> Optional[QRResult]:
        """Attempt QR decode using OpenCV's built-in QR detector."""
        try:
            detector = cv2.QRCodeDetector()
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            data, bbox, _ = detector.detectAndDecode(gray)
            if data and len(data) > 5:
                return QRResult(
                    data=data,
                    url=self._normalize_url(data),
                    page_num=page_num,
                    method="opencv",
                    confidence=0.85,
                )
        except Exception as e:
            logger.debug(f"OpenCV QR failed: {e}")
        return None

    def _try_zxing(self, img_pil: Image.Image, page_num: int) -> Optional[QRResult]:
        """Attempt QR decode using ZXing (handles rotated/damaged QRs)."""
        try:
            results = zxingcpp.read_barcodes(img_pil)
            for result in results:
                if "QR" in str(result.format).upper():
                    data = result.text.strip()
                    if data and len(data) > 5:
                        return QRResult(
                            data=data,
                            url=self._normalize_url(data),
                            page_num=page_num,
                            method="zxing",
                            confidence=0.90,
                        )
        except Exception as e:
            logger.debug(f"ZXing failed: {e}")
        return None

    def _try_regions(self, img: np.ndarray, page_num: int) -> Optional[QRResult]:
        """Try to detect QR codes in different regions of the image (corners)."""
        h, w = img.shape[:2]
        regions = [
            img[0:h//2, w//2:w],         # top-right
            img[h//2:h, w//2:w],          # bottom-right
            img[0:h//2, 0:w//2],          # top-left
            img[h//2:h, 0:w//2],          # bottom-left
            img[h//3:2*h//3, w//3:2*w//3], # center
        ]
        for region in regions:
            if region.size == 0:
                continue
            result = self._try_pyzbar(region, page_num, "pyzbar_region")
            if result:
                return result
            result = self._try_opencv_qr(region, page_num)
            if result:
                return result
        return None

    def _try_rotations(self, img: np.ndarray, page_num: int) -> Optional[QRResult]:
        """Try rotated versions of the image."""
        for angle in [90, 180, 270]:
            rotated = self._rotate_image(img, angle)
            result = self._try_pyzbar(rotated, page_num, f"pyzbar_rot{angle}")
            if result:
                return result
            result = self._try_opencv_qr(rotated, page_num)
            if result:
                return result
        return None

    def _preprocess_for_qr(self, img: np.ndarray) -> np.ndarray:
        """Enhance image for better QR detection."""
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Sharpen
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharpened = cv2.filter2D(gray, -1, kernel)

        # Increase contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(sharpened)

        # Threshold
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return binary

    def _rotate_image(self, img: np.ndarray, angle: int) -> np.ndarray:
        """Rotate image by given angle."""
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h))
        return rotated

    def _normalize_url(self, data: str) -> str:
        """Ensure the QR data has a proper URL scheme."""
        data = data.strip()
        if data.startswith(("http://", "https://", "ftp://")):
            return data
        if data.startswith("www."):
            return f"https://{data}"
        # Check if it looks like a URL
        if "." in data and " " not in data and len(data) < 2000:
            return f"https://{data}"
        return data
