"""
Configuration classes for MyArea.
Loaded by the app factory based on FLASK_ENV.
"""

import os
from datetime import timedelta


class BaseConfig:
    # ── Core ──────────────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-CHANGE-IN-PROD")
    WTF_CSRF_SECRET_KEY = os.getenv("WTF_CSRF_SECRET_KEY", SECRET_KEY)
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour

    # ── Database ──────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///myarea_dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # ── Redis / Celery ────────────────────────────────────────
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    # ── Cache ─────────────────────────────────────────────────
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
    CACHE_KEY_PREFIX = "myarea:"

    # ── Auth / OIDC ───────────────────────────────────────────
    OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
    OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
    OIDC_DISCOVERY_URL = os.getenv("OIDC_DISCOVERY_URL", "")

    # ── Sessions ──────────────────────────────────────────────
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # ── File Uploads ──────────────────────────────────────────
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", 5)) * 1024 * 1024
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # ── Game Constants ────────────────────────────────────────
    ENERGY_REGEN_SECONDS = int(os.getenv("ENERGY_REGEN_SECONDS", 300))
    STAMINA_REGEN_SECONDS = int(os.getenv("STAMINA_REGEN_SECONDS", 180))
    DAILY_RESET_HOUR = int(os.getenv("DAILY_RESET_HOUR", 0))
    BASE_MAX_ENERGY = int(os.getenv("BASE_MAX_ENERGY", 100))
    BASE_MAX_STAMINA = int(os.getenv("BASE_MAX_STAMINA", 50))
    BASE_MAX_HEALTH = int(os.getenv("BASE_MAX_HEALTH", 100))

    # Starting stats for new players
    NEW_PLAYER_CASH = 5_000
    NEW_PLAYER_ENERGY = 50
    NEW_PLAYER_STAMINA = 25
    NEW_PLAYER_HEALTH = 100

    # Experience table: level -> XP required to reach that level
    LEVEL_XP_TABLE = {i: int(100 * (i ** 1.8)) for i in range(1, 201)}

    # ── SocketIO ──────────────────────────────────────────────
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:///myarea_dev.db"
    )
    # Use simple cache in dev if Redis not available
    CACHE_TYPE = "SimpleCache"
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = True


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    CACHE_TYPE = "SimpleCache"
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost.test"


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True

    # Trust Cloudflare for form submissions
    WTF_CSRF_TRUSTED_ORIGINS = ["https://myareagams.wrds361.com", "https://myareagames.wrds361.com"]

    # Evaluate and format the URL immediately
    _url = os.getenv("DATABASE_URL")
    if not _url:
        raise ValueError("DATABASE_URL must be set in production")
    # Fix legacy postgres:// scheme for SQLAlchemy 2.x
    if _url.startswith("postgres://"):
        _url = _url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = _url

    # ── Cross-app service auth ─────────────────────────────────
    SERVICE_API_KEY  = os.getenv("SERVICE_API_KEY", "")   
    SOCIAL_APP_URL   = os.getenv("SOCIAL_APP_URL", "http://myarea_social_web:5000")

# config_map goes at the absolute bottom, with ZERO spaces on the left!
config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    # Aliases
    "dev": DevelopmentConfig,
    "test": TestingConfig,
    "prod": ProductionConfig,
}

