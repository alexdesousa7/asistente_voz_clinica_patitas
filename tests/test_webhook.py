from __future__ import annotations

import unittest
from unittest.mock import patch

import main


class WebhookFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        main.PENDING_APPOINTMENTS.clear()

    def tearDown(self) -> None:
        main.PENDING_APPOINTMENTS.clear()

    def test_appointment_flow_stores_context_then_confirms_and_clears(self) -> None:
        session = "projects/demo/agent/sessions/session-1"
        parameters = {
            "tipo_mascota": "gato",
            "nombre_mascota": "Nube",
            "motivo": "revision",
            "fecha": {"date": "2026-10-12"},
            "hora": {"time": "10:30:00"},
            "telefono": "612345678",
        }
        prepared = main.prepare_appointment(session, parameters, now=100)
        self.assertIn("¿Lo confirmo?", prepared["fulfillmentText"])
        self.assertIn("/contexts/ctx_confirmacion_cita", prepared["outputContexts"][0]["name"])

        with patch("main.uuid.uuid4") as uuid4:
            uuid4.return_value.hex = "abcdef123456"
            confirmed = main.confirm_appointment(session, "Sí, confirmo.", now=101)
        self.assertIn("VP-ABCDEF", confirmed["fulfillmentText"])
        self.assertEqual(confirmed["outputContexts"][0]["lifespanCount"], 0)
        self.assertNotIn(session, main.PENDING_APPOINTMENTS)

    def test_urgency_transfers_to_human_and_drops_pending_draft(self) -> None:
        session = "projects/demo/agent/sessions/session-3"
        main.PENDING_APPOINTMENTS[session] = (0, {})
        result = main.transfer_to_human(session)
        self.assertIn("operador", result["fulfillmentText"])
        self.assertEqual(result["payload"]["google"]["transferencia"], "operador_humano")
        self.assertNotIn(session, main.PENDING_APPOINTMENTS)

    def test_appointment_decline_cancels_without_recording(self) -> None:
        session = "projects/demo/agent/sessions/session-2"
        parameters = {
            "tipo_mascota": "perro",
            "nombre_mascota": "Luna",
            "motivo": "consulta",
            "fecha": "2026-10-12",
            "hora": "10:00",
            "telefono": "612345678",
        }
        main.prepare_appointment(session, parameters, now=100)
        declined = main.confirm_appointment(session, "No, cancela.", now=101)
        self.assertIn("no he enviado", declined["fulfillmentText"])
        self.assertNotIn(session, main.PENDING_APPOINTMENTS)

    def test_expired_confirmation_cannot_be_used(self) -> None:
        session = "projects/demo/agent/sessions/session-3"
        main.PENDING_APPOINTMENTS[session] = (
            0,
            {
                "tipo_mascota": "perro",
                "nombre_mascota": "Luna",
                "motivo": "consulta",
                "fecha": "2026-10-12",
                "hora": "10:00",
                "telefono": "612345678",
            },
        )
        response = main.confirm_appointment(session, "sí", now=main.DRAFT_TTL_SECONDS + 1)
        self.assertIn("No encuentro una cita pendiente", response["fulfillmentText"])

    def test_document_question_never_calls_model_when_documents_missing(self) -> None:
        with patch.object(main, "DOCUMENTS", {}), patch.object(main, "_client") as client:
            response = main.answer_from_documents("¿A qué hora abrís?")
        self.assertIn("no tengo documentos procesados", response["fulfillmentText"])
        client.assert_not_called()

    def test_webhook_requires_configured_shared_secret(self) -> None:
        from fastapi.testclient import TestClient

        with TestClient(main.app) as client:
            with patch.dict("os.environ", {}, clear=True):
                missing_config = client.post("/webhook", json={})
            self.assertEqual(missing_config.status_code, 503)

            with patch.dict("os.environ", {"DIALOGFLOW_WEBHOOK_SECRET": "test-secret"}):
                unauthorized = client.post("/webhook", json={})
                authorized = client.post(
                    "/webhook",
                    json={},
                    headers={"X-Dialogflow-Webhook-Secret": "test-secret"},
                )
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(authorized.status_code, 200)


if __name__ == "__main__":
    unittest.main()
