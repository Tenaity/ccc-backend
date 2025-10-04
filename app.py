# backend/app.py
import os
import pathlib

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

from api.routes import register_routes
from middleware.api_key import register_api_key_middleware
from models import init_db

load_dotenv()

# Configure static asset serving (frontend build directory)
BASE_DIR = pathlib.Path(__file__).parent
DEFAULT_FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
frontend_override = os.getenv("FRONTEND_DIST")
frontend_path = (
    pathlib.Path(frontend_override).expanduser()
    if frontend_override
    else DEFAULT_FRONTEND_DIST
)
frontend_static = str(frontend_path.resolve()) if frontend_path.exists() else None

app = Flask(
    __name__,
    static_folder=frontend_static,
    static_url_path="/",
)
cors_raw = os.getenv("CORS_ORIGINS", "*")
cors_origins = [item.strip() for item in cors_raw.split(",") if item.strip()]
CORS(app, origins=cors_origins or ["*"], supports_credentials=True)

APP_HOST = os.getenv("HOST", "0.0.0.0")
APP_PORT = int(os.getenv("PORT", "8000"))
APP_DEBUG = os.getenv("APP_ENV", "local").lower() != "production"
API_KEY = os.getenv("API_KEY")

# Initialise database schema
init_db()

# Register middleware and blueprints
register_api_key_middleware(app, api_key=API_KEY)
register_routes(app)


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)

