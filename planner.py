import json
from llm import ask_json

PLAN_SYSTEM = """You are a Polish language curriculum designer.
Build a 4-week plan. Give MORE time to the weakest skills, but train all 4 every week.
Return JSON: {"summary": "...", "weeks": [{"week": 1, "focus": "...",
"sessions": [{"day": "Mon", "skill": "reading|listening|writing|speaking",
"topic": "...", "grammar": "...", "minutes": 20}]}]}"""

def make_plan(levels: dict, goal: str, minutes_per_day: int) -> dict:
    return ask_json(PLAN_SYSTEM,
        f"Levels: {json.dumps(levels)}\nGoal: {goal}\nTime per day: {minutes_per_day} min")