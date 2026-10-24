from datetime import datetime

from .extensions import db


class Favorite(db.Model):
    __tablename__ = "favorite"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuestionBank(db.Model):
    __tablename__ = "question_bank"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    source_type = db.Column(db.String(20), nullable=False, default="json")
    source_file = db.Column(db.String(255))
    status = db.Column(db.String(20), default="success")
    note = db.Column(db.String(255))
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship("Question", backref="bank", lazy=True)


class Question(db.Model):
    __tablename__ = "question"

    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("question_bank.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    stem = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON)
    answer = db.Column(db.JSON, nullable=False)
    analysis = db.Column(db.Text)
    subject = db.Column(db.String(50))
    order_no = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    wrong_book = db.relationship('WrongBook', backref='question', uselist=False)
    favorite = db.relationship('Favorite', backref='question', uselist=False)

class PracticeRecord(db.Model):
    __tablename__ = "practice_record"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    user_answer = db.Column(db.JSON)
    is_correct = db.Column(db.Boolean)  # True/False/None
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)


class WrongBook(db.Model):
    __tablename__ = "wrong_book"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False, unique=True)
    wrong_count = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default="unmastered")  # unmastered / reviewing / mastered
    first_wrong_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_wrong_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_review_at = db.Column(db.DateTime)