from __future__ import annotations

import unittest

from business import (
    complete_appointment,
    is_valid_phone,
    normalize_confirmation,
    normalize_phone,
    parameter_text,
)


class BusinessRulesTests(unittest.TestCase):
    def test_phone_accepts_spanish_mobile_with_optional_country_code(self) -> None:
        self.assertTrue(is_valid_phone("612 345 678"))
        self.assertTrue(is_valid_phone("+34 612345678"))
        self.assertEqual(normalize_phone("+34 612-345-678"), "+34612345678")

    def test_phone_rejects_invalid_values(self) -> None:
        self.assertFalse(is_valid_phone("912345678"))
        self.assertFalse(is_valid_phone("61234567"))
        self.assertFalse(is_valid_phone("texto"))

    def test_parameter_text_reads_dialogflow_date_objects(self) -> None:
        self.assertEqual(parameter_text({"date": "2026-10-12"}), "2026-10-12")
        self.assertEqual(parameter_text({"unknown": "value"}), "")

    def test_complete_appointment_validates_all_required_fields(self) -> None:
        appointment = complete_appointment(
            {
                "tipo_mascota": "gato",
                "nombre_mascota": "Nube",
                "motivo": "revision",
                "fecha": {"date": "2026-10-12"},
                "hora": {"time": "10:30:00"},
                "telefono": "612 345 678",
            }
        )
        self.assertEqual(appointment["telefono"], "612345678")
        self.assertEqual(appointment["fecha"], "lunes 12 de octubre")
        self.assertEqual(appointment["hora"], "10:30")

    def test_spell_phone_and_goodbye(self) -> None:
        from business import is_goodbye, spell_phone

        self.assertEqual(spell_phone("632270999"), "6 3 2, 2 7 0, 9 9 9")
        self.assertTrue(is_goodbye("Adiós."))
        self.assertTrue(is_goodbye("No, gracias"))
        self.assertFalse(is_goodbye("¿Qué horario tienen?"))

    def test_cleans_pet_name_and_rejects_closed_slots(self) -> None:
        base = {
            "tipo_mascota": "gato",
            "nombre_mascota": "se llama nina",
            "motivo": "revision",
            "fecha": "2026-10-14T12:00:00+02:00",
            "hora": "2026-10-11T11:00:00+02:00",
            "telefono": "632632632",
        }
        self.assertEqual(complete_appointment(base)["nombre_mascota"], "Nina")
        with self.assertRaisesRegex(ValueError, "fuera del horario"):
            complete_appointment({**base, "hora": "2026-10-11T23:00:00+02:00"})
        with self.assertRaisesRegex(ValueError, "domingos"):
            complete_appointment({**base, "fecha": "2026-10-18"})

    def test_complete_appointment_rejects_missing_fields_and_bad_phone(self) -> None:
        with self.assertRaisesRegex(ValueError, "Faltan datos"):
            complete_appointment({})
        appointment = {
            "tipo_mascota": "perro",
            "nombre_mascota": "Luna",
            "motivo": "consulta",
            "fecha": "2026-10-12",
            "hora": "10:00",
            "telefono": "912345678",
        }
        with self.assertRaisesRegex(ValueError, "teléfono"):
            complete_appointment(appointment)

    def test_confirmation_is_unambiguous_and_accent_insensitive(self) -> None:
        self.assertEqual(normalize_confirmation("Sí, confirmo."), "yes")
        self.assertEqual(normalize_confirmation("si"), "yes")
        self.assertEqual(normalize_confirmation("No, cancela"), "no")
        self.assertIsNone(normalize_confirmation("No estoy seguro"))


if __name__ == "__main__":
    unittest.main()
