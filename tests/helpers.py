"""Builds a valid fake lesson for tests."""
from agent.schemas import Example, GrammarRule, Lesson, QuizQuestion, VocabItem

WORDS = ["rano", "sklep", "chleb", "mleko", "kawę", "kupuje", "idzie", "dom", "ulica", "pani",
         "dzień dobry", "wraca", "potem", "Anna", "mówi"]


def make_lesson(n_words: int = 15, n_rules: int = 3, lesson_date: str = "2026-10-04") -> Lesson:
    story = ("Dzień dobry! Rano Anna idzie do sklep na ulica. Kupuje chleb, mleko i kawę. "
             "Pani w sklep mówi dzień dobry. Potem Anna wraca do dom. ") * 7
    vocab = [VocabItem(polish=w, form_in_story=w, english="x", example_pl="x", example_en="x")
             for w in WORDS[:n_words]]
    rules = [GrammarRule(title=f"Rule {i}", explanation="Explained.",
                         examples=[Example(polish="a", english="a")] * 3,
                         story_examples=["Kupuje kawę."]) for i in range(n_rules)]
    quiz = (
        [QuizQuestion(id=i, type="multiple_choice", question=f"Pytanie {i}?",
                      options=["a", "b", "c", "d"], correct_option=1) for i in range(1, 5)]
        + [QuizQuestion(id=i, type="fill_blank", question="Piję ___ (kawa).",
                        accepted_answers=["kawę"]) for i in range(5, 8)]
        + [QuizQuestion(id=i, type="open", question=f"Dlaczego {i}?",
                        reference_answer="Bo tak.") for i in range(8, 11)]
    )
    return Lesson(title_pl="T", title_en="T", story_pl=story, story_en="S",
                  new_vocabulary=vocab, grammar_rules=rules, quiz=quiz,
                  lesson_date=lesson_date, level="A1")
