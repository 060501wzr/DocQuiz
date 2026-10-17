from flask import Flask

from .config import Config
from .extensions import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from . import models  # 注册模型
    from .routes import pages  # 注册页面蓝图

    app.register_blueprint(pages.bp)

    with app.app_context():
        db.create_all()

    return app