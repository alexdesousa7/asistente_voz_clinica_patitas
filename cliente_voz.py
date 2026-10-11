"""Talk to the Dialogflow ES agent using its native STT and TTS audio APIs."""

from __future__ import annotations

import os
from io import BytesIO
import uuid
import wave

import numpy as np
import sounddevice as sd
from google.cloud import dialogflow

SAMPLE_RATE = 16_000
RECORD_SECONDS = 7


def record_audio() -> bytes:
    print(f"Habla ahora ({RECORD_SECONDS} segundos)...")
    audio = sd.rec(
        int(RECORD_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    return audio.tobytes()


def play_dialogflow_audio(audio: bytes) -> None:
    with wave.open(BytesIO(audio), "rb") as stream:
        frames = stream.readframes(stream.getnframes())
        sample_rate = stream.getframerate()
        channels = stream.getnchannels()
    samples = np.frombuffer(frames, dtype=np.int16)
    if channels > 1:
        samples = samples.reshape(-1, channels)
    sd.play(samples, sample_rate)
    sd.wait()


def main() -> None:
    project_id = os.getenv("DIALOGFLOW_PROJECT_ID", "").strip()
    if not project_id:
        raise RuntimeError("Configura DIALOGFLOW_PROJECT_ID en el archivo .env.")
    client = dialogflow.SessionsClient()
    session_id = str(uuid.uuid4())
    session = client.session_path(project_id, session_id)
    input_audio = dialogflow.QueryInput(
        audio_config=dialogflow.InputAudioConfig(
            audio_encoding=dialogflow.AudioEncoding.AUDIO_ENCODING_LINEAR_16,
            language_code="es",
            sample_rate_hertz=SAMPLE_RATE,
            speech_contexts=[
                dialogflow.SpeechContext(
                    phrases=["perro", "gato", "cita", "teléfono", "móvil"],
                    boost=10.0,
                )
            ],
        )
    )
    output_audio = dialogflow.OutputAudioConfig(
        audio_encoding=dialogflow.OutputAudioEncoding.OUTPUT_AUDIO_ENCODING_LINEAR_16
    )

    print(
        "Cliente de voz de Clínica Patitas. Pulsa Enter para empezar. "
        "Habla cuando aparezca 'Habla ahora'. Ctrl+C para salir."
    )
    input("> ")
    try:
        while True:
            response = client.detect_intent(
                request={
                    "session": session,
                    "query_input": input_audio,
                    "input_audio": record_audio(),
                    "output_audio_config": output_audio,
                }
            )
            result = response.query_result
            if not result.query_text:
                print("No te he oído. Inténtalo de nuevo.")
                continue
            print(f"Has dicho: {result.query_text}")
            print(f"Intent: {result.intent.display_name}")
            print(f"Responde: {result.fulfillment_text}")
            if response.output_audio:
                play_dialogflow_audio(response.output_audio)
            if result.intent.display_name == "transferir_humano":
                print("Transfiriendo a un operador humano... Conversación terminada.")
                break
            if "hasta pronto" in result.fulfillment_text.lower():
                print("Conversación terminada.")
                break
    except KeyboardInterrupt:
        print("\nConversación terminada.")


if __name__ == "__main__":
    main()
