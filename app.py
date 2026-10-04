"""Polish Tutor - Streamlit app.

Run with:  streamlit run app.py
"""
import datetime as dt
import re

import streamlit as st

from agent.lesson_generator import LessonGenerationError, generate_lesson
from agent.schemas import Lesson
from agent.tts import synthesize_speech
from agent.tutor_chat import stream_tutor_reply
from config import DATA_DIR, DEFAULT_TOPICS, LEVELS, OPENAI_API_KEY
from storage.repository import LessonRepository

st.set_page_config(page_title="Polish Tutor", page_icon="🇵🇱", layout="wide")


@st.cache_resource
def get_repository() -> LessonRepository:
    return LessonRepository(DATA_DIR)


repo = get_repository()
today = dt.date.today()
today_str = today.isoformat()


# ---------- helpers ----------
def default_topic(day: dt.date) -> str:
    return DEFAULT_TOPICS[day.toordinal() % len(DEFAULT_TOPICS)]


def highlight_new_words(story: str, lesson: Lesson) -> str:
    """Bold every new word/phrase in the story (single pass, longest match first)."""
    forms = sorted({v.form_in_story for v in lesson.new_vocabulary if v.form_in_story},
                   key=len, reverse=True)
    if not forms:
        return story
    pattern = r"(?<!\w)(" + "|".join(re.escape(f) for f in forms) + r")(?!\w)"
    return re.sub(pattern, r"**\1**", story, flags=re.IGNORECASE)


def chat_key(lesson_date: str) -> str:
    return f"chat_{lesson_date}"


def run_generation(level: str, topic: str, lesson_date: str) -> None:
    with st.spinner("Your tutor is writing today's story… (≈20–40 s)"):
        try:
            lesson = generate_lesson(
                level=level,
                topic=topic,
                lesson_date=lesson_date,
                known_words=repo.taught_words(exclude_date=lesson_date),
                known_grammar=repo.taught_grammar(exclude_date=lesson_date),
            )
        except LessonGenerationError as exc:
            st.error(str(exc))
            return
        except Exception as exc:  # API / network errors
            st.error(f"OpenAI request failed: {exc}")
            return
    repo.save_lesson(lesson)
    repo.delete_audio(lesson_date)
    repo.unmark_completed(lesson_date)
    st.session_state.pop(chat_key(lesson_date), None)
    st.rerun()


# ---------- sidebar ----------
with st.sidebar:
    st.title("🇵🇱 Polish Tutor")

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is missing. Add it to your `.env` file and restart.")
        st.stop()

    saved_level = repo.get_setting("level", "A1")
    level = st.selectbox("Your level", LEVELS, index=LEVELS.index(saved_level))
    if level != saved_level:
        repo.set_setting("level", level)

    topic_input = st.text_input(
        "Story topic (optional)", placeholder=f"e.g. {default_topic(today)}"
    )

    dates = repo.list_lesson_dates()
    if today_str not in dates:
        dates = [today_str] + dates
    selected_date = st.selectbox(
        "Lesson", dates, format_func=lambda d: "Today" if d == today_str else d
    )

    lesson = repo.load_lesson(selected_date)

    if selected_date == today_str:
        label = "🔄 Regenerate today's lesson" if lesson else "✨ Generate today's lesson"
        if st.button(label, width="stretch", type="primary" if not lesson else "secondary"):
            run_generation(level, topic_input.strip() or default_topic(today), today_str)

    st.divider()
    stats = repo.stats(today)
    c1, c2 = st.columns(2)
    c1.metric("🔥 Streak", f"{stats['streak']} d")
    c2.metric("📚 Lessons", stats["lessons"])
    c1.metric("🔤 Words", stats["words"])
    c2.metric("📐 Grammar", stats["grammar"])


# ---------- main ----------
if lesson is None:
    st.header("Dzień dobry! 👋")
    st.info("Click **Generate today's lesson** in the sidebar to get your story for today.")
    st.stop()

st.header(f"{lesson.title_pl}")
st.caption(f"{lesson.title_en} · Level {lesson.level} · Topic: {lesson.topic} · {lesson.lesson_date}")

lesson_col, chat_col = st.columns([3, 2], gap="large")

# ----- lesson content -----
with lesson_col:
    tab_story, tab_listen, tab_words, tab_grammar, tab_quiz = st.tabs(
        ["📖 Story", "🎧 Listen", "🔤 New words", "📐 Grammar", "❓ Questions"]
    )

    with tab_story:
        show_translation = st.toggle("Show English translation")
        if show_translation:
            left, right = st.columns(2)
            left.markdown(highlight_new_words(lesson.story_pl, lesson))
            right.markdown(lesson.story_en)
        else:
            st.markdown(highlight_new_words(lesson.story_pl, lesson))
        st.caption("**Bold** = new words of the day. Ask the tutor about anything you don't understand →")

    with tab_listen:
        st.write("Listen first without reading, then check yourself with the text.")
        for pace, label in [("slow", "🐢 Slow"), ("normal", "▶️ Normal speed")]:
            path = repo.audio_path(lesson.lesson_date, pace)
            st.subheader(label)
            if path.exists():
                st.audio(path.read_bytes(), format="audio/mpeg")
            elif st.button(f"Create {label.split(' ', 1)[1].lower()} audio", key=f"tts_{pace}"):
                with st.spinner("Recording…"):
                    try:
                        path.write_bytes(synthesize_speech(lesson.story_pl, pace=pace))
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Text-to-speech failed: {exc}")
        with st.expander("Show text"):
            st.markdown(lesson.story_pl)

    with tab_words:
        st.write(f"**{len(lesson.new_vocabulary)} new words and phrases today**")
        for i, v in enumerate(lesson.new_vocabulary, start=1):
            with st.expander(f"{i}. **{v.polish}** — {v.english}"):
                st.markdown(f"*{v.part_of_speech}* · in the story: **{v.form_in_story}**")
                st.markdown(f"🇵🇱 {v.example_pl}  \n🇬🇧 {v.example_en}")

    with tab_grammar:
        for rule in lesson.grammar_rules:
            st.subheader(rule.title)
            st.write(rule.explanation)
            if rule.pattern:
                st.code(rule.pattern, language=None)
            if rule.examples:
                st.markdown("**Examples**")
                st.table([{"Polish": e.polish, "English": e.english} for e in rule.examples])
            if rule.story_examples:
                st.markdown("**In today's story**")
                for sentence in rule.story_examples:
                    st.markdown(f"- {sentence}")

    with tab_quiz:
        for i, q in enumerate(lesson.questions, start=1):
            st.markdown(f"**{i}. {q.question_pl}**  \n*{q.question_en}*")
            st.text_input("Your answer", key=f"ans_{lesson.lesson_date}_{i}",
                          label_visibility="collapsed", placeholder="Odpowiedz po polsku…")
            with st.expander("Show answer"):
                st.write(q.answer_pl)

    st.divider()
    if repo.is_completed(lesson.lesson_date):
        st.success("✅ Lesson completed. Świetnie!")
    elif st.button("✅ Mark lesson as completed", type="primary"):
        repo.mark_completed(lesson.lesson_date)
        st.balloons()
        st.rerun()

# ----- tutor chat -----
with chat_col:
    st.subheader("💬 Ask your tutor")
    key = chat_key(lesson.lesson_date)
    history: list[dict] = st.session_state.setdefault(key, [])

    messages_box = st.container(height=520)
    with messages_box:
        if not history:
            st.caption("Examples: *What does „zamówić” mean?* · *Why „kawę” and not „kawa”?* · "
                       "*Translate the second sentence.*")
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    question = st.chat_input("Ask about a word, phrase or grammar…")
    if question:
        history.append({"role": "user", "content": question})
        with messages_box:
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                try:
                    answer = st.write_stream(stream_tutor_reply(lesson, history))
                except Exception as exc:
                    answer = f"⚠️ Sorry, something went wrong: {exc}"
                    st.error(answer)
        history.append({"role": "assistant", "content": answer})
