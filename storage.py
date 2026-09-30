import json, os
PATH = "profile.json"

def load() -> dict:
    return json.load(open(PATH, encoding="utf-8")) if os.path.exists(PATH) else {}

def save(profile: dict) -> None:
    json.dump(profile, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)