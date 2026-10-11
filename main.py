"""Dialogflow ES fulfillment webhook for the veterinary clinic demo."""

from __future__ import annotations

import json
import hmac
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from google import genai
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import DefaultCredentialsError
from google.genai import types

from business import complete_appointment, is_goodbye, normalize_confirmation, spell_phone

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
OCR_FILE = BASE_DIR / "documentos" / "documentos_ocr.json"
MAX_CONTEXT_CHARS = 18_000
DRAFT_TTL_SECONDS = 15 * 60
PENDING_APPOINTMENTS: dict[str, tuple[float, dict[str, str]]] = {}

app = FastAPI(title="Clínica Patitas — Dialogflow webhook")
DOCUMENTS: dict[str, str] = {}
_GENAI_CLIENT: genai.Client | None = None

SYSTEM_INSTRUCTIONS = (
    "Eres el asistente de una clínica veterinaria ficticia de demostración. "
    "Responde en español y en un máximo de tres frases, aptas para voz. "
    "Usa exclusivamente el CONTEXTO suministrado. Si la pregunta no trata de la clínica, o el dato (por ejemplo un precio) no aparece en el contexto, responde que esa información no consta en los documentos de la clínica y sugiere llamar a la clínica. No diagnostiques ni "
    "recomiendes tratamientos. Si falta la respuesta, dilo con claridad y "
    "sugiere consultar directamente con un veterinario."
)


def load_ocr_documents(path: Path = OCR_FILE) -> dict[str, str]:
    if not path.is_file():
        LOGGER.warning(
            "No existe %s. Ejecuta `python ocr.py` antes de consultar documentos.",
            path,
        )
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"No se pudo leer el resultado de OCR: {path}") from exc
    if not isinstance(data, dict) or not all(
        isinstance(name, str) and isinstance(text, str)
        for name, text in data.items()
    ):
        raise ValueError(f"El archivo de OCR debe contener un objeto texto: {path}")
    return data


@app.on_event("startup")
def load_documents_on_startup() -> None:
    global DOCUMENTS
    DOCUMENTS = load_ocr_documents()


def respond(text: str, contexts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {"fulfillmentText": text}
    if contexts:
        response["outputContexts"] = contexts
    return response


def _confirmation_context(session: str, appointment: dict[str, str]) -> dict[str, Any]:
    if not session:
        raise ValueError("Dialogflow no envió el identificador de sesión.")
    return {
        "name": f"{session}/contexts/ctx_confirmacion_cita",
        "lifespanCount": 5,
        "parameters": appointment,
    }


def _clear_contexts(session: str) -> list[dict[str, Any]]:
    if not session:
        return []
    return [
        {
            "name": f"{session}/contexts/{name}",
            "lifespanCount": 0,
        }
        for name in ("ctx_cita_en_curso", "ctx_confirmacion_cita")
    ]


def _clean_expired_drafts(now: float | None = None) -> None:
    current = time.monotonic() if now is None else now
    expired = [
        session
        for session, (created, _) in PENDING_APPOINTMENTS.items()
        if current - created > DRAFT_TTL_SECONDS
    ]
    for session in expired:
        del PENDING_APPOINTMENTS[session]


def prepare_appointment(
    session: str, parameters: dict[str, Any], now: float | None = None
) -> dict[str, Any]:
    if not session:
        raise ValueError("Dialogflow no envió el identificador de sesión.")
    _clean_expired_drafts(now)
    appointment = complete_appointment(parameters)
    timestamp = time.monotonic() if now is None else now
    PENDING_APPOINTMENTS[session] = (timestamp, appointment)
    pet = appointment["tipo_mascota"]
    message = (
        f"Perfecto. Voy a pedir una cita para {appointment['nombre_mascota']}, "
        f"tu {pet}. El motivo es: {appointment['motivo']}. "
        f"Sería el {appointment['fecha']} a las {appointment['hora']}. "
        f"Si hace falta, te llamaremos al {spell_phone(appointment['telefono'])}. "
        "¿Lo confirmo? Dime sí o no."
    )
    return respond(message, [_confirmation_context(session, appointment)])


def confirm_appointment(session: str, query: str, now: float | None = None) -> dict[str, Any]:
    _clean_expired_drafts(now)
    decision = normalize_confirmation(query)
    draft = PENDING_APPOINTMENTS.get(session)
    if not session or draft is None:
        return respond(
            "No encuentro una cita pendiente para confirmar. "
            "Si quieres, podemos iniciar una nueva solicitud."
        )
    if decision is None:
        return respond("No he podido distinguir la respuesta. Di sí para confirmar o no para cancelar.")
    _, appointment = draft
    del PENDING_APPOINTMENTS[session]
    if decision == "no":
        return respond(
            "De acuerdo, no he enviado la solicitud de cita.",
            _clear_contexts(session),
        )
    reference = f"VP-{uuid.uuid4().hex[:6].upper()}"
    return respond(
        f"Solicitud de cita registrada con el localizador {reference} "
        f"para {appointment['nombre_mascota']}. Es una confirmación de "
        "demostración; la clínica debe validar la disponibilidad. "
        "¿Necesitas algo más?",
        _clear_contexts(session),
    )


def cancel_appointment(session: str) -> dict[str, Any]:
    had_pending_appointment = bool(session and PENDING_APPOINTMENTS.pop(session, None))
    message = (
        "He cancelado la solicitud pendiente. No se ha reservado ninguna cita."
        if had_pending_appointment
        else "No había una solicitud de cita pendiente que cancelar."
    )
    return respond(message, _clear_contexts(session))


def transfer_to_human(session: str) -> dict[str, Any]:
    PENDING_APPOINTMENTS.pop(session, None)
    response = respond(
        "Entiendo que es una urgencia. Te paso ahora mismo con un operador de "
        "la clínica. Por favor, no cuelgues. Si se corta, llama al 9 0 0, "
        "0 0 0, 0 0 0, que es un número ficticio de demostración.",
        _clear_contexts(session),
    )
    response["payload"] = {"google": {"transferencia": "operador_humano"}}
    return response


def _client() -> genai.Client:
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        if not project:
            raise ValueError(
                "Configura GOOGLE_CLOUD_PROJECT para usar Gemini en Vertex AI."
            )
        _GENAI_CLIENT = genai.Client(
            vertexai=True,
            project=project,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            http_options=types.HttpOptions(timeout=3_000),
        )
    return _GENAI_CLIENT


def answer_from_documents(question: str) -> dict[str, Any]:
    if not DOCUMENTS:
        return respond(
            "Todavía no tengo documentos procesados para responder. "
            "Por favor, consulta directamente con la clínica."
        )
    context = "\n\n".join(
        f"Documento: {name}\n{text}" for name, text in sorted(DOCUMENTS.items())
    )[:MAX_CONTEXT_CHARS]
    prompt = (
        f"CONTEXTO DOCUMENTAL:\n{context}\n\n"
        f"PREGUNTA: {question}\n"
        "Si el contexto no contiene la respuesta, indícalo sin inferir ni inventar."
    )
    try:
        response = _client().models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTIONS,
                temperature=0.1,
                max_output_tokens=400,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
    except (GoogleAPICallError, DefaultCredentialsError, TimeoutError, ValueError) as exc:
        LOGGER.error("Fallo al consultar Vertex AI: %s", exc)
        return respond(
            "Ahora mismo no puedo consultar los documentos. "
            "Por favor, contacta directamente con la clínica."
        )
    answer = (response.text or "").strip()
    if not answer:
        LOGGER.error("Vertex AI devolvió una respuesta vacía.")
        return respond(
            "No he podido preparar una respuesta documental. "
            "Por favor, contacta directamente con la clínica."
        )
    return respond(answer)


DOCUMENT_INTENTS = {
    "consultar_horarios",
    "consultar_servicios",
    "consultar_documentos",
}


@app.get("/")
def health() -> dict[str, Any]:
    return {"estado": "ok", "documentos_ocr": len(DOCUMENTS)}


@app.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    expected_secret = os.getenv("DIALOGFLOW_WEBHOOK_SECRET", "").strip()
    if not expected_secret:
        LOGGER.error("DIALOGFLOW_WEBHOOK_SECRET no está configurado.")
        raise HTTPException(
            status_code=503,
            detail="Webhook no configurado para recibir peticiones.",
        )
    provided_secret = request.headers.get("X-Dialogflow-Webhook-Secret", "")
    if not hmac.compare_digest(provided_secret, expected_secret):
        raise HTTPException(status_code=401, detail="Autenticación requerida.")

    body = await request.json()
    result = body.get("queryResult", {})
    intent = result.get("intent", {}).get("displayName", "")
    parameters = result.get("parameters", {})
    session = body.get("session", "")
    query = result.get("queryText", "")

    if intent == "solicitar_cita":
        if not result.get("allRequiredParamsPresent", False):
            return {}
        try:
            return prepare_appointment(session, parameters)
        except ValueError as exc:
            LOGGER.info("Datos de cita no válidos: %s", exc)
            return respond(
                f"{exc} Por favor, vuelve a iniciar la solicitud y revisa los datos."
            )
    if intent == "confirmar_cita":
        return confirm_appointment(session, query)
    if intent == "cancelar_cita":
        return cancel_appointment(session)
    if intent == "transferir_humano":
        return transfer_to_human(session)
    if intent in DOCUMENT_INTENTS:
        return answer_from_documents(query)
    if is_goodbye(query):
        return respond("Gracias por contactar con Clínica Patitas. ¡Hasta pronto!")
    if intent == "Default Fallback Intent":
        return answer_from_documents(query)
    LOGGER.warning("Intención sin handler: %s", intent or "(vacía)")
    return respond("No tengo configurada esa operación. Contacta con la clínica.")
