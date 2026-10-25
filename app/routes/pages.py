from datetime import datetime
import json

from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import login_required, current_user

from ..extensions import db
from ..models import PracticeRecord, Question, QuestionBank, WrongBook, Favorite
from ..services.grading import grade_question

# 核心：定义蓝图（刚才报错就是因为缺了这行）
bp = Blueprint("pages", __name__)

# ================= 辅助函数 =================

def get_user_answer(question, form):
    qtype = question.type
    if qtype == "multiple":
        return form.getlist("answer")
    return form.get("answer")

def save_record(question, user_answer, is_correct):
    record = PracticeRecord(
        user_id=current_user.id,
        question_id=question.id,
        user_answer=user_answer,
        is_correct=is_correct,
    )
    db.session.add(record)

def update_wrong_book(question, is_correct):
    if is_correct is None or is_correct:
        return
    record = WrongBook.query.filter_by(question_id=question.id, user_id=current_user.id).first()
    now = datetime.utcnow()
    if record:
        record.wrong_count += 1
        record.last_wrong_at = now
    else:
        record = WrongBook(
            user_id=current_user.id,
            question_id=question.id,
            wrong_count=1,
            status="unmastered",
            first_wrong_at=now,
            last_wrong_at=now,
        )
        db.session.add(record)

def get_practice_data(mode):
    """根据模式获取题目列表和标题"""
    if mode.startswith("bank_"):
        bank_id = int(mode.split("_")[1])
        bank = QuestionBank.query.filter_by(id=bank_id, user_id=current_user.id).first_or_404()
        questions = Question.query.filter_by(bank_id=bank.id).order_by(Question.order_no).all()
        return bank.name, questions, bank_id
    elif mode == "wrong":
        questions = Question.query.join(WrongBook).filter(WrongBook.user_id == current_user.id).order_by(WrongBook.last_wrong_at.desc()).all()
        return "错题重刷", questions, None
    elif mode == "favorite":
        questions = Question.query.join(Favorite).filter(Favorite.user_id == current_user.id).order_by(Favorite.created_at.desc()).all()
        return "收藏重刷", questions, None
    else:
        abort(404)

# ================= 首页与题库 =================

@bp.route("/")
@login_required
def index():
    banks = QuestionBank.query.filter_by(user_id=current_user.id).order_by(QuestionBank.imported_at.desc()).all()
    return render_template("index.html", banks=banks)

@bp.route("/bank/<int:bank_id>")
@login_required
def bank_detail(bank_id):
    bank = QuestionBank.query.filter_by(id=bank_id, user_id=current_user.id).first_or_404()
    page = request.args.get('page', 1, type=int)
    pagination = Question.query.filter_by(bank_id=bank.id).order_by(Question.order_no).paginate(page=page, per_page=30, error_out=False)
    return render_template("bank_detail.html", bank=bank, questions=pagination.items, pagination=pagination)

# ================= 刷题核心逻辑 =================

@bp.route("/bank/<int:bank_id>/practice")
@login_required
def practice_start(bank_id):
    return redirect(url_for("pages.practice", mode=f"bank_{bank_id}", index=0))

@bp.route("/practice/<string:mode>")
@login_required
def practice_mode_start(mode):
    return redirect(url_for("pages.practice", mode=mode, index=0))

@bp.route("/practice/<string:mode>/<int:index>", methods=["GET", "POST"])
@login_required
def practice(mode, index):
    title, questions, bank_id = get_practice_data(mode)
    total = len(questions)
    
    if total == 0:
        return "没有找到任何题目。 <a href='/'>返回首页</a>"
    if index < 0 or index >= total:
        abort(404)

    question = questions[index]
    session_key = f"answers_{mode}_user_{current_user.id}"
    answers = session.get(session_key, {})
    
    submitted_key = f"submitted_{mode}_user_{current_user.id}"
    is_submitted = session.get(submitted_key, False)

    if request.method == "POST":
        nav = request.form.get("nav")
        next_index = index
        if nav == "next" and index < total - 1:
            next_index = index + 1
        elif nav == "prev" and index > 0:
            next_index = index - 1

        if is_submitted:
            return redirect(url_for("pages.practice", mode=mode, index=next_index))

        user_answer = get_user_answer(question, request.form)
        answers[str(index)] = {"user_answer": user_answer, "is_correct": None}
        session[session_key] = answers

        return redirect(url_for("pages.practice", mode=mode, index=next_index))

    current = answers.get(str(index))
    favs = [f.question_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]
    
    return render_template(
        "practice.html",
        title=title,
        mode=mode,
        question=question,
        index=index,
        total=total,
        current=current,
        answers=answers,
        is_submitted=is_submitted,
        favorite_ids=favs
    )

@bp.route("/practice/<string:mode>/submit", methods=["POST"])
@login_required
def submit_practice(mode):
    title, questions, bank_id = get_practice_data(mode)
    
    session_key = f"answers_{mode}_user_{current_user.id}"
    answers = session.get(session_key, {})
    submitted_key = f"submitted_{mode}_user_{current_user.id}"
    
    if session.get(submitted_key):
        return redirect(url_for("pages.practice", mode=mode, index=0))

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
            update_wrong_book(question, False)
            
        # 错题重刷模式下，答对自动移出错题本
        if mode == "wrong" and result is True:
            wb = WrongBook.query.filter_by(question_id=question.id, user_id=current_user.id).first()
            if wb:
                db.session.delete(wb)

        answers[str(i)] = {"user_answer": user_answer, "is_correct": result}

    db.session.commit()
    session[session_key] = answers
    session[submitted_key] = True
    
    return redirect(url_for("pages.practice", mode=mode, index=0))

@bp.route("/practice/<string:mode>/reset", methods=["POST"])
@login_required
def reset_practice(mode):
    session.pop(f"answers_{mode}_user_{current_user.id}", None)
    session.pop(f"submitted_{mode}_user_{current_user.id}", None)
    return redirect(url_for("pages.practice", mode=mode, index=0))

# ================= 错题本与收藏 =================

@bp.route("/wrong")
@login_required
def wrong_book():
    wrongs = WrongBook.query.filter_by(user_id=current_user.id).order_by(WrongBook.last_wrong_at.desc()).all()
    return render_template("wrong.html", wrongs=wrongs)

@bp.route("/favorites")
@login_required
def favorite_list():
    favorites = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).all()
    return render_template("favorites.html", favorites=favorites)

@bp.route("/api/favorite/<int:question_id>", methods=["POST"])
@login_required
def toggle_favorite(question_id):
    Question.query.get_or_404(question_id)
    fav = Favorite.query.filter_by(question_id=question_id, user_id=current_user.id).first()
    if fav:
        db.session.delete(fav)
    else:
        db.session.add(Favorite(question_id=question_id, user_id=current_user.id))
    db.session.commit()
    return redirect(request.referrer or url_for("pages.index"))

@bp.route("/api/self_grade/<int:bank_id>/<int:index>", methods=["POST"])
@login_required
def self_grade(bank_id, index):
    QuestionBank.query.filter_by(id=bank_id, user_id=current_user.id).first_or_404()
    score = int(request.form.get("score", 0))
    session_key = f"answers_bank_{bank_id}_user_{current_user.id}"
    answers = session.get(session_key, {})
    
    if str(index) in answers:
        is_correct = score >= 6
        answers[str(index)]["is_correct"] = is_correct
        answers[str(index)]["score"] = score
        session[session_key] = answers
        
        question = Question.query.filter_by(bank_id=bank_id).order_by(Question.order_no).all()[index]
        if not is_correct:
            update_wrong_book(question, False)
        else:
            # 如果自评及格，且之前在错题本，可以移除（可选）
            wb = WrongBook.query.filter_by(question_id=question.id, user_id=current_user.id).first()
            if wb: db.session.delete(wb)
            
        db.session.commit()
    return redirect(url_for("pages.practice", mode=f"bank_{bank_id}", index=index))

# ================= 题库与题目的增删 =================

@bp.route("/bank/import", methods=["GET", "POST"])
@login_required
def import_bank():
    if request.method == "POST":
        file = request.files.get("file")
        bank_name = request.form.get("bank_name", "新题库")
        if not file or not file.filename.endswith(".json"):
            return "请上传有效的 JSON 文件", 400
        
        try:
            data = json.load(file.stream)
            from ..services.parser import import_questions_from_data
            import_questions_from_data(data, bank_name, user_id=current_user.id)
            return redirect(url_for("pages.index"))
        except Exception as e:
            return f"导入失败: {str(e)}", 400

    return render_template("import.html")

@bp.route("/bank/<int:bank_id>/append", methods=["POST"])
@login_required
def append_questions(bank_id):
    QuestionBank.query.filter_by(id=bank_id, user_id=current_user.id).first_or_404()
    file = request.files.get("file")
    if not file or not file.filename.endswith(".json"):
        return "请上传有效的 JSON 文件", 400
    
    try:
        data = json.load(file.stream)
        from ..services.parser import import_questions_from_data
        import_questions_from_data(data, bank_name=None, bank_id=bank_id, user_id=current_user.id)
    except Exception as e:
        return f"追加失败: {str(e)}", 400
    
    return redirect(url_for("pages.bank_detail", bank_id=bank_id))

@bp.route("/bank/<int:bank_id>/delete", methods=["POST"])
@login_required
def delete_bank(bank_id):
    bank = QuestionBank.query.filter_by(id=bank_id, user_id=current_user.id).first_or_404()
    questions = Question.query.filter_by(bank_id=bank.id).all()
    qids = [q.id for q in questions]

    if qids:
        PracticeRecord.query.filter(PracticeRecord.question_id.in_(qids)).delete(synchronize_session=False)
        WrongBook.query.filter(WrongBook.question_id.in_(qids)).delete(synchronize_session=False)
        Favorite.query.filter(Favorite.question_id.in_(qids)).delete(synchronize_session=False)
        Question.query.filter(Question.bank_id == bank.id).delete(synchronize_session=False)
    
    db.session.delete(bank)
    db.session.commit()
    return redirect(url_for("pages.index"))

@bp.route("/question/<int:question_id>/delete", methods=["POST"])
@login_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    QuestionBank.query.filter_by(id=question.bank_id, user_id=current_user.id).first_or_404()
    bank_id = question.bank_id

    PracticeRecord.query.filter_by(question_id=question.id).delete()
    WrongBook.query.filter_by(question_id=question.id).delete()
    Favorite.query.filter_by(question_id=question.id).delete()
    
    db.session.delete(question)
    db.session.commit()
    return redirect(url_for("pages.bank_detail", bank_id=bank_id))