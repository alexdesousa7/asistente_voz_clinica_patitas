"""Generate three clearly fictional clinic information sheets as OCR images."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "documentos"
SHEETS = {
    "horarios_clinica.png": (
        "CLINICA PATITAS - DEMOSTRACION",
        [
            "Horario de atencion (dato ficticio):",
            "Lunes a viernes: 09:00 a 14:00 y 17:00 a 20:00.",
            "Sabados: 09:00 a 13:00.",
            "Domingos: cerrado.",
            "Las citas deben confirmarse directamente con la clinica.",
            "Telefono de ejemplo: 612345678.",
        ],
    ),
    "servicios_clinica.png": (
        "SERVICIOS - CLINICA PATITAS (DEMO)",
        [
            "Informacion ficticia para probar el asistente.",
            "Consulta veterinaria general con cita previa.",
            "Vacunacion: el veterinario valora cada caso.",
            "Identificacion con microchip.",
            "La disponibilidad y el precio se confirman en la clinica.",
            "Este documento no ofrece diagnosticos ni tratamientos.",
        ],
    ),
    "preparar_visita.png": (
        "COMO PREPARAR UNA VISITA (DEMO)",
        [
            "Informacion general de demostracion.",
            "Perros: traer correa y cartilla, si se dispone de ella.",
            "Gatos: utilizar un transportin seguro.",
            "Anotar preguntas y cambios observados en la mascota.",
            "No cambies medicacion ni hagas ayunar a tu mascota",
            "salvo que el equipo veterinario lo indique.",
            "En una urgencia, contacta directamente con un veterinario.",
        ],
    ),
}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype("DejaVuSans.ttf", 32)
    title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    for filename, (title, lines) in SHEETS.items():
        height = 150 + len(lines) * 66
        image = Image.new("RGB", (1800, height), "white")
        draw = ImageDraw.Draw(image)
        draw.text((64, 48), title, fill="black", font=title_font)
        y = 130
        for line in lines:
            draw.text((64, y), line, fill="black", font=font)
            y += 66
        image.save(OUTPUT_DIR / filename)
        print(f"Creado: {OUTPUT_DIR / filename}")


if __name__ == "__main__":
    main()
