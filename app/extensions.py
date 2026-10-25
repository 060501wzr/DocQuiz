from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

# 未登录访问受限页面时，跳转到登录路由
login_manager.login_view = "auth.login"
login_manager.login_message = "请先登录后再访问该页面。"