"""
MyArea Game Engine — Service API v1
────────────────────────────────────
All endpoints here are machine-to-machine only.
Authentication: X-Service-Key header must match SERVICE_API_KEY in config.

Endpoints called BY the social app:
  GET  /api/v1/player/<oidc_sub>          → player stats for profile widget
  GET  /api/v1/player/<oidc_sub>/summary  → short summary (level, gang, rank)
  GET  /api/v1/leaderboard                → top 20 players

Endpoints called BY the game engine (push to social):
  POST /api/v1/social/notify              → push notification to social app
  (outbound — see service.py)
"""

import functools
import os
from flask import Blueprint, jsonify, request, current_app
from app import db

api_bp = Blueprint("api", __name__)


# ─── Auth decorator ───────────────────────────────────────────

def require_service_key(fn):
    """Reject requests that don't carry the correct X-Service-Key header."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("SERVICE_API_KEY", "")
        provided = request.headers.get("X-Service-Key", "")
        if not expected or not provided or provided != expected:
            return jsonify({"error": "Unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


# ─── Player endpoints (read by social app) ───────────────────

@api_bp.route("/player/<oidc_sub>")
@require_service_key
def get_player(oidc_sub: str):
    """
    Full player stats for the game widget on the social profile page.
    Called by: social app profile view
    """
    from app.models import User, Player
    user = User.query.filter_by(oidc_sub=oidc_sub).first()
    if not user or not user.player:
        return jsonify({"error": "Player not found"}), 404

    p = user.player
    return jsonify({
        "found": True,
        "slug": p.slug,
        "display_name": p.display_name,
        "level": p.level,
        "experience": p.experience,
        "cash": p.cash,
        "bank": p.bank,
        "crime_points": p.crime_points,
        # Stats
        "energy": p.energy,
        "energy_max": p.energy_max,
        "stamina": p.stamina,
        "stamina_max": p.stamina_max,
        "health": p.health,
        "health_max": p.health_max,
        "in_hospital": p.in_hospital,
        # Combat
        "attack_power": p.attack_power,
        "defense_power": p.defense_power,
        "fights_won": p.fights_won,
        "fights_lost": p.fights_lost,
        "fight_ratio": p.fight_ratio,
        # Gang
        "gang": p.gang.name if p.gang else None,
        "gang_tag": p.gang.tag if p.gang else None,
        "gang_rank": p.gang_rank,
        # Links
        "profile_url": f"/game/profile/{p.slug}",
        "avatar_url": p.avatar_url,
    })


@api_bp.route("/player/<oidc_sub>/summary")
@require_service_key
def get_player_summary(oidc_sub: str):
    """
    Short summary — level, gang, rank. Used in social sidebar widgets.
    Called by: social app anywhere a compact game badge is shown
    """
    from app.models import User, Player
    user = User.query.filter_by(oidc_sub=oidc_sub).first()
    if not user or not user.player:
        return jsonify({"found": False}), 200   # 200 so social app can show "not a player yet"

    p = user.player
    return jsonify({
        "found": True,
        "level": p.level,
        "display_name": p.display_name,
        "gang_tag": p.gang.tag if p.gang else None,
        "fights_won": p.fights_won,
        "crime_points": p.crime_points,
        "profile_url": f"/game/profile/{p.slug}",
    })


@api_bp.route("/leaderboard")
@require_service_key
def get_leaderboard():
    """
    Top 20 players. Social app can embed this as a widget.
    Results are cached — refreshed by Celery beat task every 10 min.
    """
    from app import cache
    cached = cache.get("leaderboard:players")
    if cached:
        return jsonify({"leaderboard": cached[:20], "cached": True})

    from app.models import Player
    from sqlalchemy import desc
    top = Player.query.order_by(
        desc(Player.level), desc(Player.experience)
    ).limit(20).all()

    data = [
        {
            "rank": i + 1,
            "display_name": p.display_name,
            "slug": p.slug,
            "level": p.level,
            "fights_won": p.fights_won,
            "gang_tag": p.gang.tag if p.gang else None,
        }
        for i, p in enumerate(top)
    ]
    return jsonify({"leaderboard": data, "cached": False})


@api_bp.route("/player/by-username/<username>")
@require_service_key
def get_player_by_username(username: str):
    """
    Look up a player by their username (for social cross-links).
    Called by: social app when displaying a friend's game stats
    """
    from app.models import User, Player
    user = User.query.filter_by(username=username).first()
    if not user or not user.player:
        return jsonify({"found": False}), 200

    p = user.player
    return jsonify({
        "found": True,
        "oidc_sub": user.oidc_sub,
        "level": p.level,
        "display_name": p.display_name,
        "slug": p.slug,
        "gang_tag": p.gang.tag if p.gang else None,
        "fights_won": p.fights_won,
    })


# ─── Inbound webhook from social app ──────────────────────────

@api_bp.route("/webhook/social-event", methods=["POST"])
@require_service_key
def social_event_webhook():
    """
    Called by the social app when something game-relevant happens
    (e.g. a new user registers — auto-create their Player record).
    """
    data = request.get_json(silent=True) or {}
    event_type = data.get("event")

    if event_type == "user_registered":
        _handle_user_registered(data)
        return jsonify({"status": "ok"})

    return jsonify({"status": "ignored", "event": event_type})


def _handle_user_registered(data: dict):
    """Auto-create a Player profile when a new user registers on the social app."""
    from app.models import User, Player
    from slugify import slugify

    oidc_sub  = data.get("oidc_sub")
    username  = data.get("username")
    email     = data.get("email")

    if not username:
        return

    # Don't duplicate
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return

    user = User(
        username=username,
        email=email or f"{username}@myarea.local",
        oidc_sub=oidc_sub,
    )
    db.session.add(user)
    db.session.flush()

    from flask import current_app
    player = Player(
        user_id=user.id,
        slug=slugify(username),
        display_name=username,
        cash=current_app.config["NEW_PLAYER_CASH"],
        energy=current_app.config["NEW_PLAYER_ENERGY"],
        stamina=current_app.config["NEW_PLAYER_STAMINA"],
        health=current_app.config["NEW_PLAYER_HEALTH"],
    )
    db.session.add(player)
    db.session.commit()
