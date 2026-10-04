"""Generates a daily lesson and validates it against the learning targets."""
import json
import re

from pydantic import ValidationError

from agent.llm import chat_json
from agent.prompts import LESSON_SYSTEM_PROMPT, build_lesson_user_prompt
from agent.schemas import Lesson
from config import (
    MAX_GENERATION_ATTEMPTS,
    MAX_KNOWN_WORDS_IN_PROMPT,
    MIN_GRAMMAR_RULES,
    MIN_NEW_WORDS,
    STORY_LENGTH,
    TARGET_NEW_WORDS,
)


class LessonGenerationError(Exception):
    """Raised when no valid lesson could be produced."""


def normalize(text: str) -> str:
    """Lower-case and collapse whitespace for comparisons."""
    return re.sub(r"\s+", " ", text).strip().lower()


def contains_phrase(text: str, phrase: str) -> bool:
    """True if `phrase` occurs in `text` as whole word(s), case-insensitive."""
    pattern = rf"(?<!\w){re.escape(normalize(phrase))}(?!\w)"
    return re.search(pattern, normalize(text)) is not None


def validate_lesson(
    lesson: Lesson,
    known_words: list[str],
    known_grammar: list[str],
    level: str,
) -> list[str]:
    """Return a list of problems; an empty list means the lesson is valid."""
    problems: list[str] = []
    known_word_set = {normalize(w) for w in known_words}
    known_grammar_set = {normalize(g) for g in known_grammar}

    # 1. Minimum number of new words
    vocab = lesson.new_vocabulary
    if len(vocab) < MIN_NEW_WORDS:
        problems.append(
            f"new_vocabulary has {len(vocab)} items; at least {MIN_NEW_WORDS} are required."
        )

    # 2. Words must be new, unique and used in the story
    seen: set[str] = set()
    for item in vocab:
        key = normalize(item.polish)
        if key in seen:
            problems.append(f"'{item.polish}' is listed twice in new_vocabulary.")
        seen.add(key)
        if key in known_word_set:
            problems.append(f"'{item.polish}' is already known; replace it with a new word.")
        if not contains_phrase(lesson.story_pl, item.form_in_story):
            problems.append(
                f"form_in_story '{item.form_in_story}' (for '{item.polish}') does not appear "
                "exactly in story_pl. Use it in the story or fix form_in_story."
            )

    # 3. Grammar rules
    rules = lesson.grammar_rules
    if len(rules) < MIN_GRAMMAR_RULES:
        problems.append(f"At least {MIN_GRAMMAR_RULES} grammar rule(s) are required.")
    for rule in rules:
        if normalize(rule.title) in known_grammar_set:
            problems.append(f"Grammar rule '{rule.title}' was already taught; choose a new one.")
        if not rule.explanation.strip():
            problems.append(f"Grammar rule '{rule.title}' has no explanation.")
        if len(rule.examples) < 2:
            problems.append(f"Grammar rule '{rule.title}' needs at least 2 examples.")

    # 4. Story length (allow 25% tolerance)
    min_len, max_len = STORY_LENGTH.get(level, (100, 200))
    word_count = len(lesson.story_pl.split())
    if word_count < min_len * 0.75 or word_count > max_len * 1.25:
        problems.append(
            f"story_pl has {word_count} words; it should have {min_len}-{max_len} words."
        )

    return problems


def generate_lesson(
    level: str,
    topic: str,
    lesson_date: str,
    known_words: list[str],
    known_grammar: list[str],
) -> Lesson:
    """Generate a lesson, retrying with feedback until it passes validation.

    Raises:
        LessonGenerationError: if all attempts fail validation.
    """
    recent_known_words = known_words[-MAX_KNOWN_WORDS_IN_PROMPT:]
    messages: list[dict] = [
        {"role": "system", "content": LESSON_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_lesson_user_prompt(
                level=level,
                topic=topic,
                story_length=STORY_LENGTH.get(level, (100, 200)),
                min_words=MIN_NEW_WORDS,
                target_words=TARGET_NEW_WORDS,
                min_grammar=MIN_GRAMMAR_RULES,
                known_words=recent_known_words,
                known_grammar=known_grammar,
            ),
        },
    ]

    last_problems: list[str] = []
    for _ in range(MAX_GENERATION_ATTEMPTS):
        raw_text = ""
        try:
            raw = chat_json(messages)
            raw_text = json.dumps(raw, ensure_ascii=False)
            lesson = Lesson.model_validate(raw)
            last_problems = validate_lesson(lesson, known_words, known_grammar, level)
        except json.JSONDecodeError as exc:
            last_problems = [f"The response was not valid JSON: {exc}"]
        except ValidationError as exc:
            last_problems = [f"The JSON does not match the required structure: {exc}"]

        if not last_problems:
            return lesson.model_copy(
                update={"lesson_date": lesson_date, "level": level, "topic": topic}
            )

        # Feed problems back to the model and try again
        if raw_text:
            messages.append({"role": "assistant", "content": raw_text})
        messages.append(
            {
                "role": "user",
                "content": "Fix these problems and return the full corrected JSON:\n- "
                + "\n- ".join(last_problems),
            }
        )

    raise LessonGenerationError(
        "Could not generate a valid lesson. Last problems:\n- " + "\n- ".join(last_problems)
    )
