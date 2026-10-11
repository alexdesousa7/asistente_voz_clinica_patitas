"""Run Spanish OCR once and save recognized demo-document text as JSON."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re

import pytesseract
from PIL import Image, ImageOps
from pytesseract import TesseractError, TesseractNotFoundError

BASE_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = BASE_DIR / "documentos"
OUTPUT_FILE = DOCUMENTS_DIR / "documentos_ocr.json"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
LOGGER = logging.getLogger(__name__)
OCR_FIELD_PATTERNS = {
    "horas": r"\b\d{1,2}:\d{2}\b",
    "fechas": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    "importes": r"\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s?(?:€|EUR|euros?)\b",
}


def configure_tesseract() -> None:
    executable = os.getenv("TESSERACT_CMD", "").strip()
    if executable:
        pytesseract.pytesseract.tesseract_cmd = executable


def read_image(path: Path) -> str:
    """Read an image with light grayscale/contrast preprocessing."""
    with Image.open(path) as source:
        image = ImageOps.autocontrast(ImageOps.grayscale(source))
        return pytesseract.image_to_string(
            image,
            lang="spa",
            config="--psm 6",
        ).strip()


def extract_fields(text: str) -> dict[str, list[str]]:
    """Extract and validate useful structured fields from OCR-recognized text."""
    return {
        field: re.findall(pattern, text, re.IGNORECASE)
        for field, pattern in OCR_FIELD_PATTERNS.items()
    }


def extract_documents(
    directory: Path = DOCUMENTS_DIR,
) -> dict[str, str]:
    configure_tesseract()
    if not directory.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de documentos: {directory}")

    paths = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not 3 <= len(paths) <= 5:
        raise ValueError(
            f"Se requieren entre 3 y 5 imágenes para OCR; se encontraron {len(paths)}."
        )

    documents: dict[str, str] = {}
    for path in paths:
        try:
            text = read_image(path)
        except (OSError, TesseractError, TesseractNotFoundError) as exc:
            LOGGER.error("No se pudo procesar %s: %s", path.name, exc)
            raise RuntimeError(f"Error de OCR en {path.name}") from exc
        if not text:
            raise RuntimeError(f"El OCR no reconoció texto en {path.name}.")
        extracted_fields = {
            field: values
            for field, values in extract_fields(text).items()
            if values
        }
        if extracted_fields:
            text += (
                "\n\nCampos extraídos y validados mediante regex: "
                + json.dumps(extracted_fields, ensure_ascii=False)
            )
        documents[path.name] = text
        LOGGER.info("OCR correcto: %s (%d caracteres)", path.name, len(text))
    return documents


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    documents = extract_documents()
    OUTPUT_FILE.write_text(
        json.dumps(documents, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    LOGGER.info("Texto OCR guardado en %s", OUTPUT_FILE)


if __name__ == "__main__":
    main()
