"""Business rules for the veterinary clinic demo assistant."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time
from typing import Any

PHONE_PATTERN = re.compile(r"(?:\+34\s?)?[67]\d{8}\Z")
YES_WORDS = {"si", "confirmo", "correcto", "vale", "adelante"}
YES_PHRASES = {"si confirmo", "de acuerdo adelante"}
NO_WORDS = {"no", "cancelar", "cancela", "mejor no", "no cancela"}

APPOINTMENT_FIELDS = (
    "tipo_mascota",
    "nombre_mascota",
    "motivo",
    "fecha",
    "hora",
    "telefono",
)


DAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
SCHEDULE = {
    **{day: ((9 * 60, 14 * 60), (17 * 60, 20 * 60)) for day in range(5)},
    5: ((9 * 60, 13 * 60),),
    6: (),
}
NAME_PREFIX = re.compile(
    r"^(?:mi\s+(?:mascota|perro|perra|gato|gata)\s+)?"
    r"(?:se\s+llama|se\s+llamaba|es|llamada|llamado)\s+",
    re.IGNORECASE,
)


REASON_PREFIX = re.compile(
    r"^(?:(?:hola[, ]+)?(?:quiero|queremos|necesito|necesitamos|busco|vengo|es|"
    r"seria|sería|para|por)\s+)+(?:(?:una|un|la|el|lo|las|los)\s+)?",
    re.IGNORECASE,
)


def clean_reason(value: str) -> str:
    reason = REASON_PREFIX.sub("", value.strip()).strip(" .,!")
    return reason.lower() if reason else value.strip()


def spell_phone(phone: str) -> str:
    """Spaced digits so the TTS reads them one by one."""
    digits = re.sub(r"\D", "", phone)[-9:]
    return ", ".join(" ".join(digits[i : i + 3]) for i in range(0, len(digits), 3))


GOODBYE_WORDS = {
    "adios", "hasta luego", "hasta pronto", "chao", "chau", "nada mas",
    "eso es todo", "gracias adios", "no gracias", "salir",
}


def is_goodbye(query: str) -> bool:
    normalized = unicodedata.normalize("NFD", query.lower())
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = " ".join(re.sub(r"[.,!?¿¡]+", " ", normalized).split())
    return normalized in GOODBYE_WORDS


def clean_pet_name(value: str) -> str:
    name = NAME_PREFIX.sub("", value.strip()).strip(" .,!")
    return name.title() if name else value.strip()


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass
    try:
        return datetime.combine(date.today(), time.fromisoformat(value))
    except ValueError:
        return None


def format_date(value: str) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return value
    return f"{DAYS[parsed.weekday()]} {parsed.day} de {MONTHS[parsed.month - 1]}"


def format_time(value: str) -> str:
    parsed = _parse_datetime(value)
    return parsed.strftime("%H:%M") if parsed else value


def validate_slot(date_value: str, time_value: str) -> None:
    day = _parse_datetime(date_value)
    hour = _parse_datetime(time_value)
    if day is None or hour is None:
        return
    ranges = SCHEDULE[day.weekday()]
    if not ranges:
        raise ValueError("Los domingos la clínica está cerrada.")
    minutes = hour.hour * 60 + hour.minute
    if not any(start <= minutes < end for start, end in ranges):
        raise ValueError(
            "Esa hora está fuera del horario: de lunes a viernes de 9 a 14 "
            "y de 17 a 20, y los sábados de 9 a 13."
        )


def parameter_text(value: Any) -> str:
    """Convert a Dialogflow parameter value to a readable scalar."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("date", "time", "value", "name"):
            nested = value.get(key)
            if nested is not None:
                return parameter_text(nested)
    return ""


def normalize_phone(value: Any) -> str:
    """Remove harmless phone formatting before validating a Spanish number."""
    phone = parameter_text(value)
    return re.sub(r"[\s().-]", "", phone)


def is_valid_phone(value: Any) -> bool:
    return bool(PHONE_PATTERN.fullmatch(normalize_phone(value)))


def normalize_confirmation(query: str) -> str | None:
    """Return yes/no only for an unambiguous short confirmation."""
    normalized = unicodedata.normalize("NFD", query.lower())
    normalized = "".join(
        character for character in normalized
        if unicodedata.category(character) != "Mn"
    )
    normalized = re.sub(r"[.,!?¿¡]+", " ", normalized)
    normalized = " ".join(normalized.split())
    if normalized in YES_WORDS or normalized in YES_PHRASES:
        return "yes"
    if normalized in NO_WORDS:
        return "no"
    return None


def complete_appointment(parameters: dict[str, Any]) -> dict[str, str]:
    """Extract and validate the required fields from a Dialogflow request."""
    appointment = {
        field: parameter_text(parameters.get(field))
        for field in APPOINTMENT_FIELDS
    }
    missing = [field for field, value in appointment.items() if not value]
    if missing:
        raise ValueError(f"Faltan datos obligatorios: {', '.join(missing)}")
    if not is_valid_phone(appointment["telefono"]):
        raise ValueError("El teléfono debe ser un número español válido de 9 cifras.")
    validate_slot(appointment["fecha"], appointment["hora"])
    appointment["telefono"] = normalize_phone(appointment["telefono"])
    appointment["motivo"] = clean_reason(appointment["motivo"])
    appointment["nombre_mascota"] = clean_pet_name(appointment["nombre_mascota"])
    appointment["fecha"] = format_date(appointment["fecha"])
    appointment["hora"] = format_time(appointment["hora"])
    return appointment
