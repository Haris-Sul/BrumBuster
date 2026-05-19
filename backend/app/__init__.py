from flask import Flask
from flask_cors import CORS

from app.config import get_settings
from app.routes import api_bp


def create_app() -> Flask:
    app = Flask(__name__)
    settings = get_settings()

    app.config.update(
        ENV=settings.flask_env,
        DEBUG=settings.flask_debug,
    )

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.register_blueprint(api_bp)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
