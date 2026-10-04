# 🇵🇱 Polish Tutor (Streamlit + OpenAI)

A daily Polish lesson app: a short story to read, audio to listen to, and a chat tutor to ask about any word or phrase.

## Daily guarantees (enforced in code, not just in the prompt)
`agent/lesson_generator.py` validates every generated lesson and asks the model to fix it (up to 3 tries) if:
- fewer than **10 new words/phrases** are taught
- fewer than **1 new grammar rule** is taught
- a word or grammar rule was **already taught** on a previous day
- a "new word" does **not actually appear** in the story
- the story length doesn't fit the level

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # then put your OPENAI_API_KEY in .env
streamlit run app.py
```

## Tests
```bash
python -m unittest discover tests -v
```

## Structure
```
app.py                     Streamlit UI (story, listening, words, grammar, quiz, chat)
config.py                  Models, daily targets, levels, topics
agent/prompts.py           Lesson + tutor prompts
agent/lesson_generator.py  Generation + validation/retry loop
agent/tutor_chat.py        Streaming chat grounded in today's lesson
agent/tts.py               Text-to-speech (slow / normal)
storage/repository.py      JSON files: data/lessons, data/audio, data/progress.json
tests/test_lesson.py       unittest suite
```
