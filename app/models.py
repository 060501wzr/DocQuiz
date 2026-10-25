from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db

class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class QuestionBank(db.Model):
    __tablename__ = "question_bank"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False) # 新增归属
    name = db.Column(db.String(200), nullable=False)
    source_type = db.Column(db.String(20), nullable=False, default="json")
    source_file = db.Column(db.String(255))
    status = db.Column(db.String(20), default="success")
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

    # 关系映射
    wrong_book = db.relationship('WrongBook', backref='question', uselist=False, cascade="all, delete-orphan")
    favorite = db.relationship('Favorite', backref='question', uselist=False, cascade="all, delete-orphan")

class PracticeRecord(db.Model):
    __tablename__ = "practice_record"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False) # 新增归属
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    user_answer = db.Column(db.JSON)
    is_correct = db.Column(db.Boolean)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)

class WrongBook(db.Model):
    __tablename__ = "wrong_book"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False) # 新增归属
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    wrong_count = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default="unmastered")
    first_wrong_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_wrong_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_review_at = db.Column(db.DateTime)
    
    # 一个用户同一道题只能有一条错题记录
    __table_args__ = (db.UniqueConstraint('user_id', 'question_id', name='_user_question_uc'),)

class Favorite(db.Model):
    __tablename__ = "favorite"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False) # 新增归属
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 一个用户同一道题只能收藏一次
    __table_args__ = (db.UniqueConstraint('user_id', 'question_id', name='_user_favorite_uc'),)