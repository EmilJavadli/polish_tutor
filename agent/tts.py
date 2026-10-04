"""Text-to-speech for listening practice."""
from agent.llm import get_client
from config import TTS_MODEL, TTS_VOICE
import os
from functools import lru_cache
from dotenv import load_dotenv
from elevenlabs import VoiceSettings
from elevenlabs import ElevenLabs

load_dotenv()

ELEVENLABS_API_KEY: str | None = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID: str | None = os.getenv("ELEVENLABS_VOICE_ID")
ELEVENLABS_MODEL: str = os.getenv("ELEVENLABS_MODEL")
OUTPUT_FORMAT: str = "mp3_44100_128"


PACE_SETTINGS: dict[str, VoiceSettings] = {
    "normal": VoiceSettings(stability=0.5, similarity_boost=0.75, style=0.2,
                            use_speaker_boost=True, speed=1.0),
    "slow": VoiceSettings(stability=0.6, similarity_boost=0.75, style=0.1,
                          use_speaker_boost=True, speed=0.8),
}

@lru_cache(maxsize=1)
def get_client() -> ElevenLabs:
    """Return a cached ElevenLabs client.

    Raises:
        RuntimeError: if the API key or voice ID is missing.
    """
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not set. Add it to your .env file.")
    if not ELEVENLABS_VOICE_ID:
        raise RuntimeError("ELEVENLABS_VOICE_ID is not set. Add it to your .env file.")
    return ElevenLabs(api_key=ELEVENLABS_API_KEY)


def synthesize_speech(text: str, pace: str = "normal") -> bytes:
    """Convert Polish text to MP3 bytes with ElevenLabs.

    Args:
        text: Polish text to read aloud.
        pace: "normal" or "slow". Unknown values fall back to "normal".

    Returns:
        MP3 audio as bytes.

    Raises:
        ValueError: if text is empty.
        RuntimeError: if configuration is missing or the API call fails.
    """
    if not text or not text.strip():
        raise ValueError("Text for speech synthesis is empty.")

    kwargs: dict = {
        "voice_id": ELEVENLABS_VOICE_ID,
        "model_id": ELEVENLABS_MODEL,
        "text": text.strip(),
        "language_code": "pl",
        "output_format": OUTPUT_FORMAT,
        "voice_settings": PACE_SETTINGS.get(pace, PACE_SETTINGS["normal"]),
    }

    try:
        audio_chunks = get_client().text_to_speech.convert(**kwargs)
        audio = b"".join(audio_chunks)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"ElevenLabs text-to-speech failed: {exc}") from exc

    if not audio:
        raise RuntimeError("ElevenLabs returned empty audio.")
    return audio
