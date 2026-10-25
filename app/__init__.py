from flask import Flask
from .config import Config
from .extensions import db, login_manager
from .models import User

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .routes import pages, auth
    
    app.register_blueprint(pages.bp)
    app.register_blueprint(auth.bp)

    with app.app_context():
        db.create_all()

    return app