from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_dialogflow_agent


class DialogflowExportTests(unittest.TestCase):
    def test_export_has_six_business_intents_and_required_context_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            export_dir = Path(temporary) / "dialogflow_agent"
            zip_file = Path(temporary) / "dialogflow_agent.zip"
            with (
                patch.object(build_dialogflow_agent, "EXPORT_DIR", export_dir),
                patch.object(build_dialogflow_agent, "ZIP_FILE", zip_file),
            ):
                build_dialogflow_agent.generate_export()

            intent_dir = export_dir / "intents"
            names = {
                path.name.removesuffix("_usersays_es.json").removesuffix(".json")
                for path in intent_dir.glob("*.json")
                if not path.name.endswith("_usersays_es.json")
            }
            self.assertEqual(
                names,
                {
                    "Default Welcome Intent",
                    "Default Fallback Intent",
                    "solicitar_cita",
                    "confirmar_cita",
                    "cancelar_cita",
                    "consultar_horarios",
                    "consultar_servicios",
                    "consultar_documentos",
                    "transferir_humano",
                },
            )

            appointment = json.loads(
                (intent_dir / "solicitar_cita.json").read_text(encoding="utf-8")
            )
            self.assertTrue(appointment["webhookForSlotFilling"])
            self.assertEqual(appointment["contexts"], ["ctx_cita_en_curso"])
            self.assertEqual(
                {item["name"] for item in appointment["responses"][0]["parameters"]},
                {
                    "tipo_mascota",
                    "nombre_mascota",
                    "motivo",
                    "fecha",
                    "hora",
                    "telefono",
                },
            )
            confirm = json.loads(
                (intent_dir / "confirmar_cita.json").read_text(encoding="utf-8")
            )
            self.assertEqual(confirm["contexts"], ["ctx_confirmacion_cita"])
            pet_entity = json.loads(
                (export_dir / "entities" / "tipo_mascota.json").read_text(encoding="utf-8")
            )
            self.assertFalse(pet_entity["isEnum"])
            pet_entries = json.loads(
                (export_dir / "entities" / "tipo_mascota_entries_es.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("perra", pet_entries[0]["synonyms"])
            welcome = json.loads(
                (intent_dir / "Default Welcome Intent.json").read_text(encoding="utf-8")
            )
            welcome_speech = welcome["responses"][0]["messages"][0]["speech"]
            self.assertIn("Clínica Patitas", welcome_speech[0])
            self.assertIn("perro, gato u otra", welcome_speech[0])
            with zipfile.ZipFile(zip_file) as archive:
                self.assertIn("agent.json", archive.namelist())
                self.assertIn("intents/solicitar_cita.json", archive.namelist())


if __name__ == "__main__":
    unittest.main()
