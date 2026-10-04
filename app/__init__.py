from flask import Flask

from app.clock import Clock
from app.openapi import docs
from app.repository import Repository
from app.routes import api, register_error_handlers


def create_app(clock: Clock | None = None) -> Flask:
    app = Flask(__name__)
    repo = Repository()
    repo.seed()
    app.extensions["repo"] = repo
    app.extensions["clock"] = clock or Clock()

    app.register_blueprint(api)
    app.register_blueprint(docs)  # /docs (Swagger UI) e /openapi.json
    register_error_handlers(app)
    return app
