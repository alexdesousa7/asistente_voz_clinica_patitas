from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ocr


class OcrTests(unittest.TestCase):
    def test_regex_extracts_structured_fields_from_ocr_text(self) -> None:
        result = ocr.extract_fields(
            "Lunes 09:00. Sábados 13:30. Vence 14/03/2026. Precio 300 euros."
        )
        self.assertEqual(result["horas"], ["09:00", "13:30"])
        self.assertEqual(result["fechas"], ["14/03/2026"])
        self.assertEqual(result["importes"], ["300 euros"])

    def test_rejects_directories_with_fewer_than_three_images(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("one.png", "two.jpg"):
                (root / name).touch()
            with self.assertRaisesRegex(ValueError, "entre 3 y 5"):
                ocr.extract_documents(root)

    def test_extract_documents_persists_regex_results_next_to_ocr_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = [root / f"sheet-{index}.png" for index in range(3)]
            for path in paths:
                path.touch()
            with patch.object(ocr, "read_image", return_value="Abierto de 09:00 a 17:00."):
                result = ocr.extract_documents(root)
        self.assertIn("Campos extraídos y validados mediante regex", result["sheet-0.png"])
        self.assertIn("09:00", result["sheet-0.png"])


if __name__ == "__main__":
    unittest.main()
