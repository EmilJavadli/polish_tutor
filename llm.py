import os, json
from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st

# load_dotenv()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODEL = os.getenv("LLM_MODEL", "gpt-6-luna") 

def ask_json(system: str, user: str, temperature: float = 1.0) -> dict:
    """Call the LLM and return parsed JSON."""
    r = client.chat.completions.create(
        model=MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    return json.loads(r.choices[0].message.content)

def chat(messages: list[dict]) -> str:
    r = client.chat.completions.create(model=MODEL, messages=messages)
    return r.choices[0].message.content

def tts(text: str) -> bytes:
    """Polish text -> mp3 bytes."""
    return client.audio.speech.create(model="tts-1", voice="alloy", input=text).content

def stt(audio_bytes: bytes) -> str:
    """Recorded audio -> Polish transcript."""
    r = client.audio.transcriptions.create(
        model="whisper-1", file=("answer.wav", audio_bytes), language="pl")
    return r.text