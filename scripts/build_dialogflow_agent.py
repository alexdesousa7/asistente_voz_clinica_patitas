"""Generate the Dialogflow ES agent export ZIP for import into GCP."""

from __future__ import annotations

import json
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
EXPORT_DIR = BASE_DIR / "dialogflow_agent"
ZIP_FILE = BASE_DIR / "dialogflow_agent.zip"
SPANISH = "es"


def make_parameter(name: str, entity: str, prompt: str) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "required": True,
        "dataType": entity,
        "value": f"${name}",
        "defaultValue": "",
        "isList": False,
        "prompts": [{"lang": SPANISH, "value": prompt}],
        "promptMessages": [],
        "noMatchPromptMessages": [],
        "noInputPromptMessages": [],
        "outputDialogContexts": [],
    }


def make_intent(
    name: str,
    *,
    phrases: list[str] | None = None,
    input_contexts: list[str] | None = None,
    output_contexts: list[tuple[str, int]] | None = None,
    parameters: list[dict[str, Any]] | None = None,
    webhook: bool = False,
    slot_filling_webhook: bool = False,
    fallback: bool = False,
    welcome_event: bool = False,
    priority: int = 500000,
    messages: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    intent_id = str(uuid.uuid4())
    response_parameters = parameters or []
    response_contexts = [
        {"name": context, "lifespan": lifespan}
        for context, lifespan in (output_contexts or [])
    ]
    speech = messages or []
    intent = {
        "id": intent_id,
        "name": name,
        "auto": True,
        "contexts": input_contexts or [],
        "responses": [
            {
                "resetContexts": False,
                "action": "input.welcome" if welcome_event else "",
                "affectedContexts": response_contexts,
                "parameters": response_parameters,
                "messages": [
                    {
                        "type": "0",
                        "title": "",
                        "textToSpeech": "",
                        "lang": SPANISH,
                        "speech": speech,
                        "condition": "",
                    }
                ],
                "speech": [],
            }
        ],
        "priority": priority,
        "webhookUsed": webhook,
        "webhookForSlotFilling": slot_filling_webhook,
        "fallbackIntent": fallback,
        "events": [{"name": "WELCOME"}] if welcome_event else [],
        "conditionalResponses": [],
        "condition": "",
        "conditionalFollowupEvents": [],
    }
    user_says = [
        {
            "id": str(uuid.uuid4()),
            "data": annotate_phrase(phrase),
            "isTemplate": False,
            "count": 0,
            "lang": SPANISH,
            "updated": 0,
        }
        for phrase in (phrases or [])
    ]
    return intent, user_says


def annotate_phrase(phrase: str) -> list[dict[str, Any]]:
    """Convierte 'tengo un [gato](tipo_mascota)' en segmentos anotados."""
    segments: list[dict[str, Any]] = []
    position = 0
    for match in re.finditer(r"\[([^\]]+)\]\((\w+)\)", phrase):
        if match.start() > position:
            segments.append(
                {"text": phrase[position : match.start()], "userDefined": False}
            )
        segments.append(
            {
                "text": match.group(1),
                "alias": match.group(2),
                "meta": f"@{match.group(2)}",
                "userDefined": True,
            }
        )
        position = match.end()
    if position < len(phrase):
        segments.append({"text": phrase[position:], "userDefined": False})
    return segments


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def generate_export() -> None:
    if EXPORT_DIR.exists():
        for path in sorted(EXPORT_DIR.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    write_json(
        EXPORT_DIR / "agent.json",
        {
            "description": "Asistente de voz de una clínica veterinaria ficticia.",
            "language": SPANISH,
            "displayName": "Clinica-Patitas-Blandas",
            "defaultTimezone": "Europe/Madrid",
            "webhook": {
                "url": "",
                "username": "",
                "headers": {},
                "available": False,
                "useForDomains": False,
                "cloudFunctionsEnabled": False,
                "cloudFunctionsInitialized": False,
            },
            "mlMinConfidence": 0.3,
            "supportedLanguages": [],
            "enableOnePlatformApi": True,
            "onePlatformApiVersion": "v2beta1",
            "analyzeQueryTextSentiment": False,
            "enabledKnowledgeBaseNames": [],
            "knowledgeServiceConfidenceAdjustment": 0.0,
            "dialogBuilderMode": False,
            "enableSpellCorrection": False,
        },
    )
    write_json(EXPORT_DIR / "package.json", {"version": "1.0.0"})

    entities = {
        "tipo_mascota": {
            "id": str(uuid.uuid4()),
            "name": "tipo_mascota",
            "isOverridable": True,
            "isEnum": False,
            "isRegexp": False,
            "automatedExpansion": False,
            "allowFuzzyExtraction": False,
        },
        "telefono": {
            "id": str(uuid.uuid4()),
            "name": "telefono",
            "isOverridable": True,
            "isEnum": False,
            "isRegexp": True,
            "automatedExpansion": False,
            "allowFuzzyExtraction": False,
        },
    }
    for name, data in entities.items():
        write_json(EXPORT_DIR / "entities" / f"{name}.json", data)
    write_json(
        EXPORT_DIR / "entities" / "tipo_mascota_entries_es.json",
        [
            {
                "value": "perro",
                "synonyms": ["perro", "perra", "perrito", "perrita", "canino"],
            },
            {
                "value": "gato",
                "synonyms": ["gato", "gata", "gatito", "gatita", "felino"],
            },
            {
                "value": "otro",
                "synonyms": ["otro", "otra", "conejo", "ave", "roedor", "reptil"],
            },
        ],
    )
    phone_pattern = r"(?:\+34[ -]?)?[67](?:[ .-]?\d){8}"
    write_json(
        EXPORT_DIR / "entities" / "telefono_entries_es.json",
        [{"value": phone_pattern, "synonyms": [phone_pattern]}],
    )

    appointment_parameters = [
        make_parameter(
            "tipo_mascota",
            "@tipo_mascota",
            "¿Es un perro, un gato u otro tipo de mascota?",
        ),
        make_parameter("nombre_mascota", "@sys.any", "¿Cómo se llama tu mascota?"),
        make_parameter("motivo", "@sys.any", "¿Cuál es el motivo de la visita? Por ejemplo: vacunación, revisión general o una molestia."),
        make_parameter("fecha", "@sys.date", "¿Qué día te viene bien? Atendemos de lunes a viernes de 9 a 14 y de 17 a 20, y los sábados de 9 a 13. Dime la fecha, por ejemplo: el próximo martes."),
        make_parameter("hora", "@sys.time", "¿A qué hora prefieres la cita? Por la mañana tengo a las 9, 11 o 13 horas y por la tarde a las 17 o 19 horas (los sábados, solo por la mañana)."),
        make_parameter(
            "telefono",
            "@telefono",
            "¿Cuál es tu teléfono móvil? Dime las nueve cifras despacio, de tres en tres.",
        ),
    ]
    intent_specs = [
        (
            "Default Welcome Intent",
            dict(
                welcome_event=True,
                phrases=[
                    "Hola",
                    "Buenos días",
                    "Buenas tardes",
                    "Buenas noches",
                    "Buenas",
                    "Hey",
                    "Qué tal",
                ],
                output_contexts=[("ctx_cita_en_curso", 10)],
                messages=[
                    "Hola, bienvenido a Clínica Patitas. ¿Tienes perro, gato u otra mascota? "
                    "Puedo ayudarte a pedir una cita o consultar información de la clínica."
                ],
            ),
        ),
        (
            "solicitar_cita",
            dict(
                phrases=[
                    "Quiero pedir una cita",
                    "Necesito una cita para mi [perro](tipo_mascota)",
                    "Quiero llevar a mi [gato](tipo_mascota) al veterinario",
                    "Pedir cita para mi mascota",
                    "Tengo un [perro](tipo_mascota) y quiero una consulta",
                    "Tengo un [perro](tipo_mascota)",
                    "Tengo una [perra](tipo_mascota)",
                    "Tengo un [gato](tipo_mascota)",
                    "Tengo una [gata](tipo_mascota)",
                    "Tengo un [conejo](tipo_mascota)",
                    "[Perro](tipo_mascota)",
                    "[Gato](tipo_mascota)",
                    "[Otro](tipo_mascota)",
                    "Mi mascota es un [perro](tipo_mascota)",
                    "Mi mascota es un [gato](tipo_mascota)",
                    "Necesito una cita para [otro](tipo_mascota) animal",
                ],
                input_contexts=["ctx_cita_en_curso"],
                output_contexts=[("ctx_cita_en_curso", 10)],
                parameters=appointment_parameters,
                webhook=True,
                slot_filling_webhook=True,
            ),
        ),
        (
            "confirmar_cita",
            dict(
                phrases=[
                    "Sí",
                    "Sí, confirmo",
                    "Correcto",
                    "De acuerdo, adelante",
                    "No",
                    "No, cancela",
                    "Mejor no",
                ],
                input_contexts=["ctx_confirmacion_cita"],
                webhook=True,
            ),
        ),
        (
            "cancelar_cita",
            dict(
                phrases=[
                    "Cancela la solicitud de cita",
                    "Quiero cancelar la cita",
                    "No quiero seguir con la reserva",
                ],
                webhook=True,
            ),
        ),
        (
            "transferir_humano",
            dict(
                phrases=[
                    "Es una emergencia",
                    "Es una urgencia",
                    "Mi perro se ha intoxicado",
                    "Mi gato está sangrando",
                    "Necesito hablar con una persona",
                    "Quiero hablar con un operador",
                    "Pásame con un humano",
                    "Mi mascota ha tenido un accidente",
                    "Mi mascota no respira bien",
                    "Urgencia veterinaria",
                ],
                priority=1000000,
                webhook=True,
            ),
        ),
        (
            "consultar_horarios",
            dict(
                phrases=[
                    "¿Cuál es el horario de la clínica?",
                    "¿A qué hora abrís?",
                    "¿Abrís los sábados?",
                ],
                webhook=True,
            ),
        ),
        (
            "consultar_servicios",
            dict(
                phrases=[
                    "¿Qué servicios ofrecéis?",
                    "¿Ponéis microchip?",
                    "¿Hacéis vacunación?",
                ],
                webhook=True,
            ),
        ),
        (
            "consultar_documentos",
            dict(
                phrases=[
                    "¿Cómo preparo la visita de mi perro?",
                    "¿Qué necesito llevar para mi gato?",
                    "¿Qué dicen los documentos sobre la visita?",
                    "¿Qué debo hacer antes de la visita?",
                    "¿Qué tengo que llevar a la consulta?",
                    "¿Cuánto cuesta una consulta?",
                    "¿Cuáles son los precios?",
                ],
                webhook=True,
            ),
        ),
        (
            "Default Fallback Intent",
            dict(
                fallback=True,
                webhook=True,
                messages=[
                    "No he entendido la petición. Puedes pedir una cita, "
                    "consultar horarios o servicios, o preguntar por los documentos."
                ],
            ),
        ),
    ]

    for name, options in intent_specs:
        intent, user_says = make_intent(name, **options)
        write_json(EXPORT_DIR / "intents" / f"{name}.json", intent)
        write_json(
            EXPORT_DIR / "intents" / f"{name}_usersays_es.json",
            user_says,
        )

    with zipfile.ZipFile(ZIP_FILE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(EXPORT_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(EXPORT_DIR).as_posix())
    print(f"Export listo: {ZIP_FILE}")


if __name__ == "__main__":
    generate_export()
