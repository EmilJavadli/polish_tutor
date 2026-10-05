"""Generates a daily lesson and validates it against the learning targets."""
import json
import re

from pydantic import ValidationError

from agent.llm import chat_json
from agent.prompts import build_lesson_system_prompt, build_lesson_user_prompt
from agent.schemas import Lesson
from config import (
    GRAMMAR_RULES_PER_LESSON,
    MAX_GENERATION_ATTEMPTS,
    MAX_KNOWN_WORDS_IN_PROMPT,
    NEW_WORDS_PER_LESSON,
    QUIZ_COMPOSITION,
    STORY_LENGTH,
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


def _validate_vocabulary(lesson: Lesson, known_words: list[str]) -> list[str]:
    problems: list[str] = []
    vocab = lesson.new_vocabulary
    if len(vocab) != NEW_WORDS_PER_LESSON:
        problems.append(
            f"new_vocabulary has {len(vocab)} items; exactly {NEW_WORDS_PER_LESSON} are required."
        )
    known = {normalize(w) for w in known_words}
    seen: set[str] = set()
    for item in vocab:
        key = normalize(item.polish)
        if key in seen:
            problems.append(f"'{item.polish}' is listed twice in new_vocabulary.")
        seen.add(key)
        if key in known:
            problems.append(f"'{item.polish}' is already known; replace it with another word.")
        if not contains_phrase(lesson.story_pl, item.form_in_story):
            problems.append(
                f"form_in_story '{item.form_in_story}' (for '{item.polish}') does not appear "
                "exactly in story_pl. Use it in the story or fix form_in_story."
            )
    return problems


def _validate_grammar(lesson: Lesson, known_grammar: list[str]) -> list[str]:
    problems: list[str] = []
    rules = lesson.grammar_rules
    if len(rules) != GRAMMAR_RULES_PER_LESSON:
        problems.append(
            f"grammar_rules has {len(rules)} items; exactly {GRAMMAR_RULES_PER_LESSON} are required."
        )
    known = {normalize(g) for g in known_grammar}
    for rule in rules:
        if normalize(rule.title) in known:
            problems.append(f"Grammar rule '{rule.title}' was already taught; choose another one.")
        if not rule.explanation.strip():
            problems.append(f"Grammar rule '{rule.title}' has no explanation.")
        if len(rule.examples) < 3:
            problems.append(f"Grammar rule '{rule.title}' needs at least 3 examples.")
        if not rule.story_examples:
            problems.append(f"Grammar rule '{rule.title}' needs story_examples from the story.")
    return problems


def _validate_quiz(lesson: Lesson) -> list[str]:
    problems: list[str] = []
    quiz = lesson.quiz
    expected_total = sum(QUIZ_COMPOSITION.values())
    if len(quiz) != expected_total:
        problems.append(f"quiz has {len(quiz)} questions; exactly {expected_total} are required.")
    for q_type, expected in QUIZ_COMPOSITION.items():
        actual = sum(1 for q in quiz if q.type == q_type)
        if actual != expected:
            problems.append(f"quiz has {actual} '{q_type}' questions; {expected} are required.")
    if len({q.id for q in quiz}) != len(quiz):
        problems.append("quiz question ids must be unique.")

    for q in quiz:
        if not q.question.strip():
            problems.append(f"Question {q.id} is empty.")
        if q.type == "multiple_choice":
            if len(q.options) != 4:
                problems.append(f"Question {q.id} must have exactly 4 options.")
            if q.correct_option is None or not 0 <= q.correct_option < len(q.options):
                problems.append(f"Question {q.id} has an invalid correct_option.")
        elif q.type == "fill_blank":
            if q.question.count("___") != 1:
                problems.append(f"Question {q.id} must contain exactly one '___' gap.")
            if not q.accepted_answers:
                problems.append(f"Question {q.id} needs accepted_answers.")
        elif q.type == "open" and not q.reference_answer.strip():
            problems.append(f"Question {q.id} needs a reference_answer.")
    return problems


def validate_lesson(
    lesson: Lesson,
    known_words: list[str],
    known_grammar: list[str],
    level: str,
) -> list[str]:
    """Return a list of problems; an empty list means the lesson is valid."""
    problems = _validate_vocabulary(lesson, known_words)
    problems += _validate_grammar(lesson, known_grammar)
    problems += _validate_quiz(lesson)

    min_len, max_len = STORY_LENGTH.get(level, (150, 250))
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
    messages: list[dict] = [
        {
            "role": "system",
            "content": build_lesson_system_prompt(
                NEW_WORDS_PER_LESSON, GRAMMAR_RULES_PER_LESSON, QUIZ_COMPOSITION
            ),
        },
        {
            "role": "user",
            "content": build_lesson_user_prompt(
                level=level,
                topic=topic,
                story_length=STORY_LENGTH.get(level, (150, 250)),
                known_words=known_words[-MAX_KNOWN_WORDS_IN_PROMPT:],
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
