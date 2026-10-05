"""Grades quiz answers. Multiple choice and fill-in-the-blank are graded in code;
open answers are graded by the LLM. Correct answers are never returned."""
import re
import unicodedata

from agent.llm import chat_json
from agent.prompts import GRADER_SYSTEM_PROMPT, build_grader_user_prompt
from agent.schemas import Lesson, QuestionResult, QuizAttempt, QuizQuestion
from config import QUIZ_PASS_SCORE


def normalize_answer(text: str) -> str:
    """Lower-case, NFC-normalize, strip punctuation and extra spaces (diacritics are kept)."""
    text = unicodedata.normalize("NFC", text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def grade_multiple_choice(question: QuizQuestion, answer: str) -> QuestionResult:
    correct = answer != "" and answer.isdigit() and int(answer) == question.correct_option
    feedback = "" if correct else "Read the story again carefully - the answer depends on a detail."
    return QuestionResult(id=question.id, score=1.0 if correct else 0.0, feedback=feedback)


def grade_fill_blank(question: QuizQuestion, answer: str) -> QuestionResult:
    accepted = {normalize_answer(a) for a in question.accepted_answers}
    correct = normalize_answer(answer) in accepted
    feedback = "" if correct else "Check the case/ending required here and the Polish letters (ą, ę, ł…)."
    return QuestionResult(id=question.id, score=1.0 if correct else 0.0, feedback=feedback)


def grade_open_answers(lesson: Lesson, questions: list[QuizQuestion],
                       answers: dict[str, str]) -> list[QuestionResult]:
    """Grade open questions with the LLM; empty answers get 0 without an API call."""
    results: list[QuestionResult] = []
    to_grade = []
    for q in questions:
        learner_answer = answers.get(str(q.id), "").strip()
        if not learner_answer:
            results.append(QuestionResult(id=q.id, score=0.0, feedback="No answer given."))
        else:
            to_grade.append({"id": q.id, "question": q.question,
                             "reference_answer": q.reference_answer,
                             "learner_answer": learner_answer})
    if not to_grade:
        return results

    raw = chat_json([
        {"role": "system", "content": GRADER_SYSTEM_PROMPT},
        {"role": "user", "content": build_grader_user_prompt(lesson.story_pl, to_grade)},
    ])
    graded = {int(r["id"]): r for r in raw.get("results", []) if "id" in r}
    for item in to_grade:
        r = graded.get(item["id"], {})
        try:
            score = float(r.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        score = min((0.0, 0.5, 1.0), key=lambda allowed: abs(allowed - score))
        results.append(QuestionResult(id=item["id"], score=score,
                                      feedback=str(r.get("feedback", ""))))
    return results


def grade_quiz(lesson: Lesson, answers: dict[str, str], attempt: int) -> QuizAttempt:
    """Grade all answers. `answers` maps question id (as str) -> answer
    (option index as str for multiple choice)."""
    results: list[QuestionResult] = []
    open_questions: list[QuizQuestion] = []
    for q in lesson.quiz:
        answer = answers.get(str(q.id), "")
        if q.type == "multiple_choice":
            results.append(grade_multiple_choice(q, answer))
        elif q.type == "fill_blank":
            results.append(grade_fill_blank(q, answer))
        else:
            open_questions.append(q)
    results += grade_open_answers(lesson, open_questions, answers)

    order = {q.id: i for i, q in enumerate(lesson.quiz)}
    results.sort(key=lambda r: order.get(r.id, 0))
    score = sum(r.score for r in results) / len(lesson.quiz) if lesson.quiz else 0.0
    return QuizAttempt(attempt=attempt, score=round(score, 4),
                       passed=score >= QUIZ_PASS_SCORE, answers=answers, results=results)
