"""
Transcription Service for Humsafar.
Integrates with Groq's audio transcription endpoint (Whisper-large-v3)
to transcribe user speech clips recorded via MediaRecorder (webm/ogg).
"""

import os
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_WHISPER_MODEL = os.getenv("GROQ_AUDIO_MODEL", "whisper-large-v3")


class TranscriptionError(Exception):
    """General error during audio transcription."""
    pass


class NoSpeechDetectedError(TranscriptionError):
    """Raised when the audio clip contains no detectable speech."""
    pass


def transcribe_audio_clip(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    content_type: str = "audio/webm",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> str:
    """
    Send an audio clip (webm or ogg) to Groq's audio transcription API
    and return the plain text transcript.
    """
    key = api_key or os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise TranscriptionError("GROQ_API_KEY is not configured on the server.")

    if not audio_bytes or len(audio_bytes) < 100:
        raise NoSpeechDetectedError("No audio content received or recording was too short.")

    active_model = model or DEFAULT_WHISPER_MODEL

    # Normalize content type and filename
    fn = filename or "audio.webm"
    ct = content_type or "audio/webm"
    if "webm" in ct and not fn.endswith(".webm"):
        fn += ".webm"
    elif "ogg" in ct and not fn.endswith(".ogg"):
        fn += ".ogg"

    headers = {
        "Authorization": f"Bearer {key}",
    }

    files = {
        "file": (fn, audio_bytes, ct),
    }
    data = {
        "model": active_model,
        "response_format": "json",
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                GROQ_TRANSCRIPTION_URL,
                headers=headers,
                files=files,
                data=data,
            )

            if resp.status_code != 200:
                logger.error("Groq Whisper API returned %d: %s", resp.status_code, resp.text)
                raise TranscriptionError(f"Groq Whisper transcription failed: {resp.text}")

            res_json = resp.json()
            transcript = res_json.get("text", "").strip()

            if not transcript:
                raise NoSpeechDetectedError("No speech detected in audio clip.")

            return transcript

    except httpx.TimeoutException:
        logger.error("Transcription request to Groq timed out.")
        raise TranscriptionError("Transcription service timed out. Please try again.")
    except (NoSpeechDetectedError, TranscriptionError):
        raise
    except Exception as exc:
        logger.exception("Unexpected error during audio transcription: %s", exc)
        raise TranscriptionError(f"Audio transcription failed: {str(exc)}")
