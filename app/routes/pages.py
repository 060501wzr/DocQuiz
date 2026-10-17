from datetime import datetime

from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..extensions import db
from ..models import PracticeRecord, Question, QuestionBank, WrongBook
from ..services.grading import grade_question

bp = Blueprint("pages", __name__)


def get_user_answer(question, form):
    qtype = question.type
    if qtype == "multiple":
        return form.getlist("answer")
    return form.get("answer")


def save_record(question, user_answer, is_correct):
    """写练习记录。主观题 is_correct 为 None。"""
    record = PracticeRecord(
        question_id=question.id,
        user_answer=user_answer,
        is_correct=is_correct,
    )
    db.session.add(record)


def update_wrong_book(question, is_correct):
    """客观题答错写入错题本；已存在就 +1。"""
    if is_correct is None:
        return
    if is_correct:
        return

    record = WrongBook.query.filter_by(question_id=question.id).first()
    now = datetime.utcnow()
    if record:
        record.wrong_count += 1
        record.last_wrong_at = now
    else:
        record = WrongBook(
            question_id=question.id,
            wrong_count=1,
            status="unmastered",
            first_wrong_at=now,
            last_wrong_at=now,
        )
        db.session.add(record)


@bp.route("/")
def index():
    banks = QuestionBank.query.order_by(QuestionBank.imported_at.desc()).all()
    return render_template("index.html", banks=banks)


@bp.route("/bank/<int:bank_id>")
def bank_detail(bank_id):
    bank = QuestionBank.query.get_or_404(bank_id)
    questions = (
        Question.query
        .filter_by(bank_id=bank.id)
        .order_by(Question.order_no)
        .all()
    )
    return render_template("bank_detail.html", bank=bank, questions=questions)


@bp.route("/bank/<int:bank_id>/practice")
def practice_start(bank_id):
    return redirect(url_for("pages.practice", bank_id=bank_id, index=0))


@bp.route("/bank/<int:bank_id>/practice/<int:index>", methods=["GET", "POST"])
def practice(bank_id, index):
    bank = QuestionBank.query.get_or_404(bank_id)
    questions = (
        Question.query
        .filter_by(bank_id=bank.id)
        .order_by(Question.order_no)
        .all()
    )
    total = len(questions)
    if total == 0 or index < 0 or index >= total:
        abort(404)

    question = questions[index]
    session_key = f"answers_bank_{bank_id}"
    answers = session.get(session_key, {})

    if request.method == "POST":
        user_answer = get_user_answer(question, request.form)
        result = grade_question(question, user_answer)

        save_record(question, user_answer, result)
        update_wrong_book(question, result)
        db.session.commit()

        answers[str(index)] = {
            "user_answer": user_answer,
            "is_correct": result,
        }
        session[session_key] = answers
        return redirect(url_for("pages.practice", bank_id=bank_id, index=index))

    current = answers.get(str(index))
    return render_template(
        "practice.html",
        bank=bank,
        question=question,
        index=index,
        total=total,
        current=current,
    )

@bp.route("/bank/<int:bank_id>/reset", methods=["POST"])
def reset_practice(bank_id):
    QuestionBank.query.get_or_404(bank_id)

    # 只清当前题库的 session 作答状态，不动数据库
    session.pop(f"answers_bank_{bank_id}", None)

    return redirect(url_for("pages.practice", bank_id=bank_id, index=0))