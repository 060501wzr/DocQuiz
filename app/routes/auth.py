from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("pages.index"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if User.query.filter_by(username=username).first():
            flash("用户名已存在", "danger")
            return redirect(url_for("auth.register"))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("注册成功，请登录", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pages.index"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session.clear()
            login_user(user)
            return redirect(url_for("pages.index"))
        else:
            flash("用户名或密码错误", "danger")
    return render_template("auth/login.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))