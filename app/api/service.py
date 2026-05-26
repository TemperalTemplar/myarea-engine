"""
MyArea Game Engine — Outbound Service Client
─────────────────────────────────────────────
Functions for the game engine to PUSH data to the social app.
Used by Celery tasks and game logic to fire social notifications.

Usage:
    from app.api.service import notify_social_user, push_game_event
    notify_social_user(oidc_sub="abc123", title="You were attacked!", ...)
"""

import os
import requests
from typing import Optional
from flask import current_app


def _headers() -> dict:
    key = os.getenv("SERVICE_API_KEY", "")
    return {
        "X-Service-Key": key,
        "Content-Type": "application/json",
    }


def _social_url(path: str) -> str:
    base = os.getenv("SOCIAL_APP_URL", "http://myarea_social_web:5000")
    return f"{base.rstrip('/')}{path}"


def notify_social_user(
    oidc_sub: str,
    title: str,
    message: str,
    notif_type: str = "game",
    link: Optional[str] = None,
) -> bool:
    """
    Push a notification to a user on the social app.
    The social app will store it in its Notification table
    and forward it via SocketIO if the user is online.

    Returns True on success, False on any failure.
    """
    try:
        resp = requests.post(
            _social_url("/api/v1/service/notify"),
            json={
                "oidc_sub": oidc_sub,
                "type": notif_type,
                "title": title,
                "message": message,
                "link": link,
            },
            headers=_headers(),
            timeout=5,
        )
        return resp.status_code == 200
    except Exception as e:
        # Non-critical — game keeps running even if social is down
        print(f"[service] notify_social_user failed: {e}")
        return False


def push_game_event(event_type: str, payload: dict) -> bool:
    """
    Generic game event push to social app.
    event_type examples: 'level_up', 'gang_join', 'leaderboard_rank'
    """
    try:
        resp = requests.post(
            _social_url("/api/v1/service/game-event"),
            json={"event": event_type, "data": payload},
            headers=_headers(),
            timeout=5,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[service] push_game_event failed: {e}")
        return False
