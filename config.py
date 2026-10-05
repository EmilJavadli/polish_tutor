"""Central configuration loaded from environment variables / .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-6-luna")
DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))

# Daily learning content
NEW_WORDS_PER_LESSON: int = 15
GRAMMAR_RULES_PER_LESSON: int = 3
MAX_GENERATION_ATTEMPTS: int = 3

# Quiz
QUIZ_COMPOSITION: dict[str, int] = {
    "multiple_choice": 4,   # detailed comprehension / inference
    "fill_blank": 3,        # one per grammar rule, graded automatically
    "open": 3,              # full-sentence answers in Polish, graded by the LLM
}
QUIZ_PASS_SCORE: float = 0.80

# How many previously taught words to send to the model (keeps prompts small)
MAX_KNOWN_WORDS_IN_PROMPT: int = 400

LEVELS: list[str] = ["A0", "A1", "A2", "B1", "B2"]

# Story length (in words) per CEFR level - long enough to hold 15 new words + 3 rules
STORY_LENGTH: dict[str, tuple[int, int]] = {
    "A0": (120, 180),
    "A1": (150, 220),
    "A2": (200, 280),
    "B1": (250, 350),
    "B2": (300, 400),
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
