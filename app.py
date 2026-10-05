
import datetime as dt
import re

import streamlit as st

from agent.lesson_generator import LessonGenerationError, generate_lesson
from agent.quiz_grader import grade_quiz
from agent.schemas import Lesson, QuizAttempt
from agent.tts import synthesize_speech
from agent.tutor_chat import stream_tutor_reply
from config import DATA_DIR, DEFAULT_TOPICS, LEVELS, OPENAI_API_KEY, QUIZ_PASS_SCORE
from storage.repository import LessonRepository

st.set_page_config(page_title="Polish Tutor", page_icon="🇵🇱", layout="wide")

TYPE_LABELS = {
    "multiple_choice": "Choose the correct answer",
    "fill_blank": "Fill in the gap with the correct form",
    "open": "Answer in a full Polish sentence",
}


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
    with st.spinner("Your tutor is writing today's story and quiz… (≈30–60 s)"):
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
    repo.reset_lesson_progress(lesson_date)
    st.session_state.pop(chat_key(lesson_date), None)
    st.rerun()


def render_quiz(lesson: Lesson) -> None:
    """Quiz with no answer reveal; retry until the pass score is reached."""
    if not lesson.quiz:
        st.info("This lesson was created with an older version and has no quiz. "
                "Regenerate today's lesson to get one.")
        return

    attempts: list[QuizAttempt] = repo.quiz_attempts(lesson.lesson_date)
    passed = next((a for a in attempts if a.passed), None)
    pass_pct = int(QUIZ_PASS_SCORE * 100)

    if passed:
        st.success(f"🎉 Quiz passed with **{passed.score:.0%}** on attempt {passed.attempt}. "
                   "Lesson completed!")
        results = {r.id: r for r in passed.results}
        for i, q in enumerate(lesson.quiz, start=1):
            r = results.get(q.id)
            icon = "✅" if r and r.score == 1 else ("🟡" if r and r.score > 0 else "❌")
            st.markdown(f"{icon} **{i}.** {q.question}")
        return

    last = attempts[-1] if attempts else None
    st.write(f"**{len(lesson.quiz)} questions · pass mark {pass_pct}%.** "
             "Answers are never shown; if you don't pass, try again.")
    if last:
        st.error(f"Attempt {last.attempt}: **{last.score:.0%}**, you need {pass_pct}%. "
                 "Fix the questions marked ❌/🟡 and submit again.")

    prev_answers = last.answers if last else {}
    prev_results = {r.id: r for r in last.results} if last else {}
    attempt_no = len(attempts) + 1

    with st.form(key=f"quiz_{lesson.lesson_date}_{attempt_no}"):
        answers: dict[str, str] = {}
        for i, q in enumerate(lesson.quiz, start=1):
            qid = str(q.id)
            st.markdown(f"**{i}. {q.question}**")
            caption = TYPE_LABELS[q.type] + (f" · hint: {q.hint_en}" if q.hint_en else "")
            st.caption(caption)

            widget_key = f"q_{lesson.lesson_date}_{attempt_no}_{qid}"
            prev = prev_answers.get(qid, "")
            if q.type == "multiple_choice":
                choice = st.radio(
                    "Answer", options=list(range(len(q.options))),
                    format_func=lambda idx, opts=q.options: opts[idx],
                    index=int(prev) if prev.isdigit() and int(prev) < len(q.options) else None,
                    key=widget_key, label_visibility="collapsed",
                )
                answers[qid] = "" if choice is None else str(choice)
            elif q.type == "fill_blank":
                answers[qid] = st.text_input("Answer", value=prev, key=widget_key,
                                             label_visibility="collapsed",
                                             placeholder="Wpisz brakujące słowo…")
            else:
                answers[qid] = st.text_area("Answer", value=prev, key=widget_key, height=80,
                                            label_visibility="collapsed",
                                            placeholder="Odpowiedz pełnym zdaniem po polsku…")

            r = prev_results.get(q.id)
            if r is not None:
                if r.score == 1:
                    st.markdown("✅ Correct last time")
                else:
                    icon = "🟡 Partly correct" if r.score > 0 else "❌ Incorrect"
                    st.markdown(f"{icon} last time" + (f": {r.feedback}" if r.feedback else ""))
            st.write("")

        submitted = st.form_submit_button("Submit answers", type="primary")

    if submitted:
        missing = [i for i, q in enumerate(lesson.quiz, start=1) if not answers[str(q.id)].strip()]
        if missing:
            st.warning(f"Please answer all questions first (missing: {', '.join(map(str, missing))}).")
            return
        with st.spinner("Checking your answers…"):
            try:
                result = grade_quiz(lesson, answers, attempt=attempt_no)
            except Exception as exc:
                st.error(f"Grading failed, please submit again: {exc}")
                return
        repo.save_quiz_attempt(lesson.lesson_date, result)
        if result.passed:
            st.balloons()
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
        if lesson and repo.quiz_attempts(today_str):
            st.caption("Regenerating replaces today's story and resets your quiz attempts.")
        if st.button(label, width="stretch", type="secondary" if lesson else "primary"):
            run_generation(level, topic_input.strip() or default_topic(today), today_str)

    st.divider()
    stats = repo.stats(today)
    c1, c2 = st.columns(2)
    c1.metric("🔥 Streak", f"{stats['streak']} d")
    c2.metric("📚 Passed", stats["lessons"])
    c1.metric("🔤 Words", stats["words"])
    c2.metric("📐 Grammar", stats["grammar"])


# ---------- main ----------
if lesson is None:
    st.header("Dzień dobry! 👋")
    st.info("Click **Generate today's lesson** in the sidebar to get your story for today.")
    st.stop()

st.header(lesson.title_pl)
status = "✅ Passed" if repo.is_completed(lesson.lesson_date) else "⏳ Quiz not passed yet"
st.caption(f"{lesson.title_en} · Level {lesson.level} · Topic: {lesson.topic} · "
           f"{lesson.lesson_date} · {status}")

lesson_col, chat_col = st.columns([3, 2], gap="large")

# ----- lesson content -----
with lesson_col:
    tab_story, tab_listen, tab_words, tab_grammar, tab_quiz = st.tabs(
        ["📖 Story", "🎧 Listen", "🔤 Key words", "📐 Grammar", "📝 Quiz"]
    )

    with tab_story:
        show_translation = st.toggle("Show English translation")
        if show_translation:
            left, right = st.columns(2)
            left.markdown(highlight_new_words(lesson.story_pl, lesson))
            right.markdown(lesson.story_en)
        else:
            st.markdown(highlight_new_words(lesson.story_pl, lesson))
        st.caption("**Bold** = key words of the day. Ask the tutor about anything you don't understand →")

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
        st.write(f"**The {len(lesson.new_vocabulary)} most important and difficult words "
                 "in today's story**")
        for i, v in enumerate(lesson.new_vocabulary, start=1):
            with st.expander(f"{i}. **{v.polish}** — {v.english}"):
                st.markdown(f"*{v.part_of_speech}* · in the story: **{v.form_in_story}**")
                if v.why_important:
                    st.markdown(f"💡 {v.why_important}")
                st.markdown(f"🇵🇱 {v.example_pl}  \n🇬🇧 {v.example_en}")

    with tab_grammar:
        st.write(f"**The {len(lesson.grammar_rules)} most important grammar points in today's story**")
        for i, rule in enumerate(lesson.grammar_rules, start=1):
            with st.expander(f"{i}. {rule.title}", expanded=(i == 1)):
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
        render_quiz(lesson)

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
