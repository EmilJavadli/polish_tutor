"""Text-to-speech for listening practice."""
from agent.llm import get_client
from config import TTS_MODEL, TTS_VOICE

PACE_INSTRUCTIONS = {
    "normal": "Read this Polish text aloud like a native Polish speaker, at a natural pace.",
    "slow": (
        "Read this Polish text aloud like a native Polish speaker for a language learner: "
        "speak slowly and clearly, with a short pause after each sentence."
    ),
}


def synthesize_speech(text: str, pace: str = "normal") -> bytes:
    """Convert Polish text to MP3 bytes."""
    kwargs: dict = {
        "model": TTS_MODEL,
        "voice": TTS_VOICE,
        "input": text,
        "response_format": "mp3",
    }
    if TTS_MODEL.startswith("tts-1"):
        # Classic TTS models: control pace with `speed`
        kwargs["speed"] = 0.8 if pace == "slow" else 1.0
    else:
        # Steerable TTS models: control pace with `instructions`
        kwargs["instructions"] = PACE_INSTRUCTIONS.get(pace, PACE_INSTRUCTIONS["normal"])

    response = get_client().audio.speech.create(**kwargs)
    return response.content
