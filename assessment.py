from llm import ask_json

LEVELS = ["A1", "A2", "B1", "B2", "C1"]
SKILLS = ["reading", "listening", "writing", "speaking"]
N_ITEMS = {"reading": 5, "listening": 5, "writing": 2, "speaking": 2}

ITEM_SYSTEM = """
You are an expert Polish-as-a-foreign-language examiner.
Create ONE test item that precisely matches the requested CEFR level.
Polish content must be natural and grammatically correct. Return JSON only.
"""

def generate_item(skill: str, level: str) -> dict:
    if skill in ("reading", "listening"):
        spec = ('{"text": "<Polish passage, length suited to level>", '
                '"question": "<question in English>", '
                '"options": ["4 options"], "answer_index": <0-3>}')
        extra = "For listening, write text that sounds natural when spoken." if skill == "listening" else ""
    else:
        spec = '{"task": "<task instruction in English, with expected length>"}'
        extra = ("Speaking task: something answerable in 30-60 seconds."
                 if skill == "speaking" else "Writing task: e.g. email, description, opinion.")
    return ask_json(ITEM_SYSTEM, f"Skill: {skill}. CEFR level: {level}. {extra}\nFormat: {spec}")

GRADER_SYSTEM = """
You are a strict, fair CEFR examiner for Polish.
Assess: task achievement, grammar (cases, verb aspect, agreement),
vocabulary range, coherence{extra}.
Return JSON: {{"cefr": "A1|A2|B1|B2|C1", "score": 0-100,
"feedback": "<2-3 sentences in English>",
"errors": [{{"wrong": "...", "correct": "...", "rule": "..."}}]}}
"""

def grade_production(skill: str, task: str, answer: str) -> dict:
    extra = (", fluency (judged from transcript; pronunciation cannot be assessed)"
             if skill == "speaking" else ", spelling and diacritics")
    return ask_json(GRADER_SYSTEM.format(extra=extra),
                    f"Task: {task}\nLearner answer: {answer}", temperature=0)