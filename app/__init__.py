import os

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .extensions import db, migrate


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.json.sort_keys = False
    app.json.ensure_ascii = False

    db.init_app(app)
    from . import models  # noqa: F401  регистрирует модели для миграций

    migrate.init_app(app, db)

    from .routes import bp

    app.register_blueprint(bp)

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        return jsonify(error=err.description), err.code

    return app
