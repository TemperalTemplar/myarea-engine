"""
app/notify.py  (myarea-engine — GamesHub + CrimeWars)
Fire-and-forget notification to the myarea-ai aggregator.
Best-effort: errors are swallowed so a notifier failure never breaks a response.
"""
import os
import threading
import requests

AI_BASE_URL     = os.environ.get("MYAREA_AI_URL", "http://myarea-ai:8930")
SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY", "")


def _fire(payload: dict):
    try:
        requests.post(
            f"{AI_BASE_URL}/api/notifications/push",
            json=payload,
            headers={"X-Service-Key": SERVICE_API_KEY},
            timeout=2,
        )
    except Exception:
        pass  # best-effort


def push(recipient: str, actor: str, notif_type: str,
         title: str, body: str, url: str, app: str = "games"):
    """Fire-and-forget. recipient/actor are Authentik subs (oidc_sub)."""
    if not recipient or recipient == actor:
        return
    payload = {
        "recipient": recipient, "actor": actor, "type": notif_type,
        "title": title, "body": body, "url": url, "app": app,
    }
    threading.Thread(target=_fire, args=(payload,), daemon=True).start()
