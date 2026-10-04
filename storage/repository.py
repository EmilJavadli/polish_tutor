"""File-based storage for lessons, audio and learner progress."""
import datetime as dt
import json
from pathlib import Path

from pydantic import ValidationError

from agent.schemas import Lesson


class LessonRepository:
    """Stores each lesson as data/lessons/YYYY-MM-DD.json and progress in progress.json."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.lessons_dir = self.root / "lessons"
        self.audio_dir = self.root / "audio"
        self.progress_file = self.root / "progress.json"
        self.lessons_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    # ---------- lessons ----------
    def _lesson_path(self, lesson_date: str) -> Path:
        return self.lessons_dir / f"{lesson_date}.json"

    def save_lesson(self, lesson: Lesson) -> None:
        self._lesson_path(lesson.lesson_date).write_text(
            lesson.model_dump_json(indent=2), encoding="utf-8"
        )

    def load_lesson(self, lesson_date: str) -> Lesson | None:
        path = self._lesson_path(lesson_date)
        if not path.exists():
            return None
        try:
            return Lesson.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, json.JSONDecodeError):
            return None

    def list_lesson_dates(self) -> list[str]:
        """All lesson dates, newest first."""
        return sorted((p.stem for p in self.lessons_dir.glob("*.json")), reverse=True)

    def _all_lessons(self, exclude_date: str | None = None) -> list[Lesson]:
        lessons = []
        for lesson_date in sorted(self.list_lesson_dates()):
            if lesson_date == exclude_date:
                continue
            lesson = self.load_lesson(lesson_date)
            if lesson:
                lessons.append(lesson)
        return lessons

    def taught_words(self, exclude_date: str | None = None) -> list[str]:
        """Dictionary forms of all words taught so far (oldest first)."""
        return [v.polish for l in self._all_lessons(exclude_date) for v in l.new_vocabulary]

    def taught_grammar(self, exclude_date: str | None = None) -> list[str]:
        return [g.title for l in self._all_lessons(exclude_date) for g in l.grammar_rules]

    # ---------- audio ----------
    def audio_path(self, lesson_date: str, pace: str) -> Path:
        return self.audio_dir / f"{lesson_date}_{pace}.mp3"

    def delete_audio(self, lesson_date: str) -> None:
        for path in self.audio_dir.glob(f"{lesson_date}_*.mp3"):
            path.unlink(missing_ok=True)

    # ---------- progress ----------
    def _read_progress(self) -> dict:
        if not self.progress_file.exists():
            return {"completed": [], "settings": {}}
        try:
            return json.loads(self.progress_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"completed": [], "settings": {}}

    def _write_progress(self, progress: dict) -> None:
        self.progress_file.write_text(
            json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def mark_completed(self, lesson_date: str) -> None:
        progress = self._read_progress()
        if lesson_date not in progress["completed"]:
            progress["completed"].append(lesson_date)
            self._write_progress(progress)

    def unmark_completed(self, lesson_date: str) -> None:
        progress = self._read_progress()
        progress["completed"] = [d for d in progress["completed"] if d != lesson_date]
        self._write_progress(progress)

    def is_completed(self, lesson_date: str) -> bool:
        return lesson_date in self._read_progress()["completed"]

    def get_setting(self, key: str, default=None):
        return self._read_progress().get("settings", {}).get(key, default)

    def set_setting(self, key: str, value) -> None:
        progress = self._read_progress()
        progress.setdefault("settings", {})[key] = value
        self._write_progress(progress)

    def stats(self, today: dt.date) -> dict:
        """Totals over completed lessons and the current daily streak."""
        completed = set(self._read_progress()["completed"])
        lessons = [l for l in self._all_lessons() if l.lesson_date in completed]

        streak, day = 0, today
        if day.isoformat() not in completed:
            day -= dt.timedelta(days=1)  # streak is still alive if today isn't done yet
        while day.isoformat() in completed:
            streak += 1
            day -= dt.timedelta(days=1)

        return {
            "lessons": len(lessons),
            "words": sum(len(l.new_vocabulary) for l in lessons),
            "grammar": sum(len(l.grammar_rules) for l in lessons),
            "streak": streak,
        }
