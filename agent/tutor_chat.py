"""Chat tutor that answers questions about the current lesson."""
from collections.abc import Iterator

from agent.llm import chat_stream
from agent.prompts import TUTOR_SYSTEM_PROMPT
from agent.schemas import Lesson

MAX_HISTORY_MESSAGES = 20


def build_tutor_system_prompt(lesson: Lesson) -> str:
    """Inject the lesson content into the tutor's system prompt."""
    vocabulary = "\n".join(
        f"- {v.polish} ({v.form_in_story}) = {v.english}" for v in lesson.new_vocabulary
    )
    grammar = "\n".join(f"- {g.title}: {g.explanation}" for g in lesson.grammar_rules)
    return TUTOR_SYSTEM_PROMPT.format(
        level=lesson.level,
        title_pl=lesson.title_pl,
        title_en=lesson.title_en,
        story_pl=lesson.story_pl,
        story_en=lesson.story_en,
        vocabulary=vocabulary,
        grammar=grammar,
    )


def stream_tutor_reply(lesson: Lesson, history: list[dict]) -> Iterator[str]:
    """Stream the tutor's answer to the latest message in `history`."""
    messages = [{"role": "system", "content": build_tutor_system_prompt(lesson)}]
    messages += history[-MAX_HISTORY_MESSAGES:]
    yield from chat_stream(messages)
