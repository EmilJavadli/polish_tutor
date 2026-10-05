# 🇵🇱 Polish Tutor (Streamlit + OpenAI + ElevenLabs)

Daily Polish lesson: a story to read, audio to listen to, a tutor chat, and a quiz you must pass.

## Each lesson (enforced in code; the model is asked to fix anything that fails, up to 3 tries)
- **15 key words**: the most important and most difficult words of the story, all new and all used in the story
- **3 grammar rules**: the most important grammar points used in the story, none repeated from earlier days
- **10-question quiz**: 4 multiple choice + 3 fill-in-the-gap (one per grammar rule) + 3 open answers in Polish
  - multiple choice and gaps are checked in code; open answers are graded by the LLM (1 / 0.5 / 0)
  - **pass mark 80%**; answers are never shown; retry until you pass
  - passing the quiz marks the lesson as completed (counts for the streak)

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # add OPENAI_API_KEY and ELEVENLABS_* values
streamlit run app.py
```

Lessons from the previous version have no quiz. Regenerate today's lesson or delete `data/lessons/`.

## Tests
```bash
python -m unittest discover tests -v
```

## Structure
```
app.py                     Streamlit UI (story, listen, key words, grammar, quiz, chat)
config.py                  Model, word/grammar counts, quiz composition, pass score
agent/prompts.py           Lesson, grader and tutor prompts
agent/lesson_generator.py  Generation + validation/retry loop
agent/quiz_grader.py       Quiz grading (code + LLM), never returns answers
agent/tutor_chat.py        Streaming chat grounded in today's lesson
agent/tts.py               ElevenLabs text-to-speech (slow / normal)
storage/repository.py      JSON files: data/lessons, data/audio, data/progress.json
tests/                     unittest suite
```
