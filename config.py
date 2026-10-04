"""Central configuration loaded from environment variables / .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-6-luna")
TTS_MODEL: str = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE: str = os.getenv("TTS_VOICE", "coral")
DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))

# Daily learning targets
MIN_NEW_WORDS: int = 10
TARGET_NEW_WORDS: int = 12
MIN_GRAMMAR_RULES: int = 1
MAX_GENERATION_ATTEMPTS: int = 3

# How many previously taught words to send to the model (keeps prompts small)
MAX_KNOWN_WORDS_IN_PROMPT: int = 400

LEVELS: list[str] = ["A0", "A1", "A2", "B1", "B2"]

# Story length (in words) per CEFR level
STORY_LENGTH: dict[str, tuple[int, int]] = {
    "A0": (80, 120),
    "A1": (100, 160),
    "A2": (150, 220),
    "B1": (200, 300),
    "B2": (250, 350),
}

# Rotated automatically when the learner does not choose a topic
DEFAULT_TOPICS: list[str] = [
    "morning routine", "shopping at the market", "taking the tram in Kraków",
    "visiting the doctor", "a weekend trip to the mountains", "cooking pierogi",
    "a day at the office", "meeting a new neighbour", "renting a flat",
    "a birthday party", "at the post office", "weather and seasons",
    "a walk with a child in the park", "ordering in a restaurant",
    "a phone call with a friend", "going to the bank", "public holidays in Poland",
    "hobbies and free time", "a job interview", "a train journey to Gdańsk",
]
