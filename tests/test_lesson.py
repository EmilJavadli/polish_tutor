"""Unit tests for lesson validation and storage. Run: python -m unittest discover tests"""
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from agent.lesson_generator import contains_phrase, validate_lesson
from agent.schemas import Example, GrammarRule, Lesson, VocabItem
from storage.repository import LessonRepository

WORDS = ["kawę", "rano", "sklep", "chleb", "mleko", "kupuje", "idzie", "dom", "ulica", "pani", "dzień dobry"]


def make_lesson(n_words: int = 11, n_rules: int = 1, lesson_date: str = "2026-10-04") -> Lesson:
    story = ("Dzień dobry! Rano Anna idzie do sklep na ulica. Kupuje chleb, mleko i kawę. "
             "Pani w sklep mówi dzień dobry. Potem Anna wraca do dom. ") * 5
    vocab = [VocabItem(polish=w, form_in_story=w, english="x", example_pl="x", example_en="x")
             for w in WORDS[:n_words]]
    rules = [GrammarRule(title=f"Rule {i}", explanation="Explained.",
                         examples=[Example(polish="a", english="a")] * 2) for i in range(n_rules)]
    return Lesson(title_pl="T", title_en="T", story_pl=story, story_en="S",
                  new_vocabulary=vocab, grammar_rules=rules, lesson_date=lesson_date, level="A1")


class TestValidation(unittest.TestCase):
    def test_valid_lesson_has_no_problems(self):
        self.assertEqual(validate_lesson(make_lesson(), [], [], "A1"), [])

    def test_too_few_words(self):
        problems = validate_lesson(make_lesson(n_words=9), [], [], "A1")
        self.assertTrue(any("at least 10" in p for p in problems))

    def test_missing_grammar_rule(self):
        problems = validate_lesson(make_lesson(n_rules=0), [], [], "A1")
        self.assertTrue(any("grammar rule" in p for p in problems))

    def test_known_word_rejected(self):
        problems = validate_lesson(make_lesson(), ["Chleb"], [], "A1")
        self.assertTrue(any("already known" in p for p in problems))

    def test_repeated_grammar_rejected(self):
        problems = validate_lesson(make_lesson(), [], ["rule 0"], "A1")
        self.assertTrue(any("already taught" in p for p in problems))

    def test_word_not_in_story(self):
        lesson = make_lesson()
        lesson.new_vocabulary[0].form_in_story = "samochód"
        problems = validate_lesson(lesson, [], [], "A1")
        self.assertTrue(any("samochód" in p for p in problems))

    def test_contains_phrase_whole_words_only(self):
        self.assertTrue(contains_phrase("Kupuję kawę.", "kawę"))
        self.assertFalse(contains_phrase("Kupuję kawę.", "kaw"))


class TestRepository(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = LessonRepository(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_load(self):
        self.repo.save_lesson(make_lesson())
        self.assertEqual(self.repo.load_lesson("2026-10-04").title_pl, "T")

    def test_taught_words_excludes_date(self):
        self.repo.save_lesson(make_lesson(lesson_date="2026-10-03"))
        self.repo.save_lesson(make_lesson(lesson_date="2026-10-04"))
        self.assertEqual(len(self.repo.taught_words(exclude_date="2026-10-04")), 11)

    def test_streak(self):
        for d in ["2026-10-02", "2026-10-03", "2026-10-04"]:
            self.repo.save_lesson(make_lesson(lesson_date=d))
            self.repo.mark_completed(d)
        stats = self.repo.stats(dt.date(2026, 10, 4))
        self.assertEqual(stats["streak"], 3)
        self.assertEqual(stats["words"], 33)


if __name__ == "__main__":
    unittest.main()
