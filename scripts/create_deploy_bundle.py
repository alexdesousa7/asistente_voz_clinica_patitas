"""Create a credential-free source bundle for deployment via Cloud Shell."""

from __future__ import annotations

import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT = BASE_DIR / "clinica_patitas_cloud_run.zip"
INCLUDED_FILES = (
    "Dockerfile",
    "requirements.txt",
    "main.py",
    "business.py",
    "ocr.py",
    "documentos/documentos_ocr.json",
)


def create_bundle() -> None:
    missing = [filename for filename in INCLUDED_FILES if not (BASE_DIR / filename).is_file()]
    if missing:
        raise FileNotFoundError(
            "No se puede crear el paquete; faltan: " + ", ".join(missing)
        )
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for filename in INCLUDED_FILES:
            bundle.write(BASE_DIR / filename, arcname=filename)
    print(f"Paquete listo para Cloud Shell: {OUTPUT}")
    print(f"Contenido: {', '.join(INCLUDED_FILES)}")


if __name__ == "__main__":
    create_bundle()
