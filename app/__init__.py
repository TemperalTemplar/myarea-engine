"""
MyArea Game Engine
Flask application factory — wires up all extensions and registers blueprints.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from flask_socketio import SocketIO
from authlib.integrations.flask_client import OAuth
from celery import Celery

# ─── Extension instances (no app bound yet) ───────────────────
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
cache = Cache()
socketio = SocketIO()
oauth = OAuth()
celery_app = Celery()


def create_app(config_name: str | None = None) -> Flask:
    """Application factory — create and configure the Flask app."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # ── Load config ───────────────────────────────────────────
    from app.config import config_map
    cfg = config_name or os.getenv("FLASK_ENV", "production")
    app.config.from_object(config_map[cfg])

    # ── Override with runtime env vars ───────────────────────
    import os as _os
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    if _os.getenv('PREFERRED_URL_SCHEME'):
        app.config['PREFERRED_URL_SCHEME'] = _os.getenv('PREFERRED_URL_SCHEME')

    # ── Bind extensions ───────────────────────────────────────
    _init_extensions(app)

    # ── Register blueprints ───────────────────────────────────
    _register_blueprints(app)

    # ── Register CLI commands ─────────────────────────────────
    _register_commands(app)
    _register_context_processors_engine(app)

    # ── Shell context ─────────────────────────────────────────
    @app.shell_context_processor
    def shell_ctx():
        from app.models import User, Player, Property, Item, Gang, Job, AttackLog
        return dict(db=db, User=User, Player=Player, Property=Property,
                    Item=Item, Gang=Gang, Job=Job, AttackLog=AttackLog)

    return app


def _init_extensions(app: Flask) -> None:
    """Bind all Flask extensions to the app instance."""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    cache.init_app(app)
    oauth.init_app(app)
    socketio.init_app(
        app,
        message_queue=app.config["REDIS_URL"],
        async_mode="eventlet",
        cors_allowed_origins=app.config.get("CORS_ORIGINS", "*"),
    )

    # Configure login manager
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to play MyArea."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        from app.models import User
        return db.session.get(User, int(user_id))

    # Configure Celery
    celery_app.conf.update(
        broker_url=app.config["REDIS_URL"],
        result_backend=app.config["REDIS_URL"],
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )

    # Push app context into Celery tasks
    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask

    # Register OIDC provider if configured
    if app.config.get("OIDC_CLIENT_ID"):
        oauth.register(
            name="authentik",
            client_id=app.config["OIDC_CLIENT_ID"],
            client_secret=app.config["OIDC_CLIENT_SECRET"],
            server_metadata_url=app.config["OIDC_DISCOVERY_URL"],
            client_kwargs={"scope": "openid email profile"},
        )


def _register_blueprints(app: Flask) -> None:
    """Register all route blueprints."""
    from app.admin.routes import admin_bp
    from app.auth.routes import auth_bp
    from app.game.routes import game_bp
    from app.game.jobs.routes import jobs_bp
    from app.game.attacks.routes import attacks_bp
    from app.game.properties.routes import properties_bp
    from app.game.items.routes import items_bp
    from app.game.gangs.routes import gangs_bp
    from app.api.routes import api_bp

    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(game_bp, url_prefix="/game")
    app.register_blueprint(jobs_bp, url_prefix="/game/jobs")
    app.register_blueprint(attacks_bp, url_prefix="/game/attacks")
    app.register_blueprint(properties_bp, url_prefix="/game/properties")
    app.register_blueprint(items_bp, url_prefix="/game/items")
    app.register_blueprint(gangs_bp, url_prefix="/game/gangs")
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # Root redirect
    from flask import redirect, url_for
    @app.route("/")
    def index():
        return redirect(url_for("game.dashboard"))


def _register_commands(app: Flask) -> None:
    """Register Flask CLI commands."""
    from app.cli import register_commands
    register_commands(app)


def _register_context_processors_engine(app: Flask) -> None:
    from datetime import datetime, timezone

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        unread = 0
        if current_user.is_authenticated and hasattr(current_user, 'player') and current_user.player:
            from app.models import Notification
            unread = Notification.query.filter_by(
                player_id=current_user.player.id, is_read=False
            ).count()
        return dict(
            now=datetime.now(timezone.utc),
            unread_notifications=unread,
            blueprint_names=[],
        )
