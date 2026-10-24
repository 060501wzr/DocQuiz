from datetime import datetime

import json
from io import BytesIO

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
from ..models import PracticeRecord, Question, QuestionBank, WrongBook, Favorite
from ..services.grading import grade_question

bp = Blueprint("pages", __name__)

def get_user_answer(question, form):
    qtype = question.type
    if qtype == "multiple":
        return form.getlist("answer")
    return form.get("answer")

def save_record(question, user_answer, is_correct):
    record = PracticeRecord(
        question_id=question.id,
        user_answer=user_answer,
        is_correct=is_correct,
    )
    db.session.add(record)

def update_wrong_book(question, is_correct):
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
    questions = Question.query.filter_by(bank_id=bank.id).order_by(Question.order_no).all()
    return render_template("bank_detail.html", bank=bank, questions=questions)

@bp.route("/bank/<int:bank_id>/practice")
def practice_start(bank_id):
    return redirect(url_for("pages.practice", bank_id=bank_id, index=0))

@bp.route("/bank/<int:bank_id>/practice/<int:index>", methods=["GET", "POST"])
def practice(bank_id, index):
    bank = QuestionBank.query.get_or_404(bank_id)
    questions = Question.query.filter_by(bank_id=bank.id).order_by(Question.order_no).all()
    total = len(questions)
    if total == 0 or index < 0 or index >= total:
        abort(404)

    question = questions[index]
    session_key = f"answers_bank_{bank_id}"
    answers = session.get(session_key, {})
    
    submitted_key = f"submitted_bank_{bank_id}"
    is_submitted = session.get(submitted_key, False)

    if request.method == "POST":
        nav = request.form.get("nav")
        next_index = index
        if nav == "next" and index < total - 1:
            next_index = index + 1
        elif nav == "prev" and index > 0:
            next_index = index - 1

        if is_submitted:
            return redirect(url_for("pages.practice", bank_id=bank_id, index=next_index))

        user_answer = get_user_answer(question, request.form)
        answers[str(index)] = {"user_answer": user_answer, "is_correct": None}
        session[session_key] = answers

        return redirect(url_for("pages.practice", bank_id=bank_id, index=next_index))

    current = answers.get(str(index))
    return render_template(
        "practice.html",
        bank=bank,
        question=question,
        index=index,
        total=total,
        current=current,
        answers=answers,
        is_submitted=is_submitted,
        favorite_ids=[f.question_id for f in Favorite.query.all()]  # 正确加在这里
    )

@bp.route("/bank/<int:bank_id>/submit", methods=["POST"])
def submit_practice(bank_id):
    bank = QuestionBank.query.get_or_404(bank_id)
    questions = Question.query.filter_by(bank_id=bank.id).order_by(Question.order_no).all()
    
    session_key = f"answers_bank_{bank_id}"
    answers = session.get(session_key, {})
    submitted_key = f"submitted_bank_{bank_id}"
    
    if session.get(submitted_key):
        return redirect(url_for("pages.practice", bank_id=bank_id, index=0))

    for i, question in enumerate(questions):
        ans_data = answers.get(str(i), {})
        user_answer = ans_data.get("user_answer")
        
        if user_answer is None or user_answer == "" or user_answer == []:
            if question.type in ["fill_blank", "short_answer"]:
                result = None
            else:
                result = False
        else:
            result = grade_question(question, user_answer)

        save_record(question, user_answer, result)
        
        if result is False:
            update_wrong_book(question, result)

        answers[str(i)] = {"user_answer": user_answer, "is_correct": result}

    db.session.commit()
    session[session_key] = answers
    session[submitted_key] = True
    
    return redirect(url_for("pages.practice", bank_id=bank_id, index=0))

@bp.route("/bank/<int:bank_id>/reset", methods=["POST"])
def reset_practice(bank_id):
    QuestionBank.query.get_or_404(bank_id)
    session.pop(f"answers_bank_{bank_id}", None)
    session.pop(f"submitted_bank_{bank_id}", None)
    return redirect(url_for("pages.practice", bank_id=bank_id, index=0))

# ================= 错题本与收藏 =================

@bp.route("/wrong")
def wrong_book():
    wrongs = WrongBook.query.order_by(WrongBook.last_wrong_at.desc()).all()
    return render_template("wrong.html", wrongs=wrongs)

@bp.route("/favorites")
def favorite_list():
    favorites = Favorite.query.order_by(Favorite.created_at.desc()).all()
    return render_template("favorites.html", favorites=favorites) # 修复：渲染正确的页面

@bp.route("/api/favorite/<int:question_id>", methods=["POST"])
def toggle_favorite(question_id):
    Question.query.get_or_404(question_id)
    fav = Favorite.query.filter_by(question_id=question_id).first()
    if fav:
        db.session.delete(fav)
    else:
        db.session.add(Favorite(question_id=question_id))
    db.session.commit()
    return redirect(request.referrer or url_for("pages.index"))

@bp.route("/api/self_grade/<int:bank_id>/<int:index>", methods=["POST"])
def self_grade(bank_id, index):
    score = int(request.form.get("score", 0))
    session_key = f"answers_bank_{bank_id}"
    answers = session.get(session_key, {})
    
    if str(index) in answers:
        is_correct = score >= 6
        answers[str(index)]["is_correct"] = is_correct
        answers[str(index)]["score"] = score
        session[session_key] = answers
        
        question = Question.query.filter_by(bank_id=bank_id).order_by(Question.order_no).all()[index]
        if not is_correct:
            update_wrong_book(question, False)
            
        db.session.commit()
    return redirect(url_for("pages.practice", bank_id=bank_id, index=index))

# ================= 题库与题目的增删 =================

@bp.route("/bank/import", methods=["GET", "POST"])
def import_bank():
    """新建题库（上传 JSON 文件）"""
    if request.method == "POST":
        file = request.files.get("file")
        bank_name = request.form.get("bank_name", "新题库")
        if not file or not file.filename.endswith(".json"):
            return "请上传有效的 JSON 文件", 400
        
        try:
            data = json.load(file.stream)
            # 复用之前的解析逻辑（需要稍作改造，见文末提示）
            from ..services.parser import import_questions_from_data
            result = import_questions_from_data(data, bank_name)
            return redirect(url_for("pages.index"))
        except Exception as e:
            return f"导入失败: {str(e)}", 400

    return render_template("import.html")

@bp.route("/bank/<int:bank_id>/append", methods=["POST"])
def append_questions(bank_id):
    """给已有题库追加题目"""
    file = request.files.get("file")
    if not file or not file.filename.endswith(".json"):
        return "请上传有效的 JSON 文件", 400
    
    try:
        data = json.load(file.stream)
        from ..services.parser import import_questions_from_data
        import_questions_from_data(data, bank_name=None, bank_id=bank_id)
    except Exception as e:
        return f"追加失败: {str(e)}", 400
    
    return redirect(url_for("pages.bank_detail", bank_id=bank_id))

@bp.route("/bank/<int:bank_id>/delete", methods=["POST"])
def delete_bank(bank_id):
    """删除整个题库（包含级联清理）"""
    bank = QuestionBank.query.get_or_404(bank_id)
    questions = Question.query.filter_by(bank_id=bank.id).all()
    qids = [q.id for q in questions]

    if qids:
        # 清理所有关联数据
        PracticeRecord.query.filter(PracticeRecord.question_id.in_(qids)).delete(synchronize_session=False)
        WrongBook.query.filter(WrongBook.question_id.in_(qids)).delete(synchronize_session=False)
        Favorite.query.filter(Favorite.question_id.in_(qids)).delete(synchronize_session=False)
        Question.query.filter(Question.bank_id == bank.id).delete(synchronize_session=False)
    
    db.session.delete(bank)
    db.session.commit()
    return redirect(url_for("pages.index"))

@bp.route("/question/<int:question_id>/delete", methods=["POST"])
def delete_question(question_id):
    """删除单道题目（包含级联清理）"""
    question = Question.query.get_or_404(question_id)
    bank_id = question.bank_id

    # 清理这道题关联的流水、错题、收藏
    PracticeRecord.query.filter_by(question_id=question.id).delete()
    WrongBook.query.filter_by(question_id=question.id).delete()
    Favorite.query.filter_by(question_id=question.id).delete()
    
    db.session.delete(question)
    db.session.commit()
    return redirect(url_for("pages.bank_detail", bank_id=bank_id))