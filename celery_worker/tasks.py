"""
MyArea Celery Tasks
All background game logic runs here.
"""

from datetime import datetime, timezone
from celery_worker.worker import worker, get_flask_app


def now_utc():
    return datetime.now(timezone.utc)


@worker.task(name="celery_worker.tasks.regen_energy", bind=True, max_retries=3)
def regen_energy(self):
    """Tick energy regeneration for all players who aren't at max."""
    try:
        from app import create_app, db
        from app.models import Player
        app = get_flask_app()  # shared (no per-task pool)
        with app.app_context():
            now = now_utc()
            regen_secs = app.config["ENERGY_REGEN_SECONDS"]

            players = Player.query.filter(
                Player.energy < Player.energy_max
            ).all()

            updated = 0
            for player in players:
                elapsed = (now - player.energy_last_regen).total_seconds()
                ticks = int(elapsed // regen_secs)
                if ticks > 0:
                    gain = min(ticks, player.energy_max - player.energy)
                    player.energy += gain
                    # Advance by exactly the ticks consumed (keep leftover seconds,
                    # so regen is accurate and doesn't silently lose time).
                    from datetime import timedelta as _td
                    player.energy_last_regen = player.energy_last_regen + _td(seconds=ticks * regen_secs)
                    updated += 1

            db.session.commit()
            return {"players_updated": updated}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@worker.task(name="celery_worker.tasks.regen_stamina", bind=True, max_retries=3)
def regen_stamina(self):
    """Tick stamina regeneration for all players who aren't at max."""
    try:
        from app import create_app, db
        from app.models import Player
        app = get_flask_app()  # shared (no per-task pool)
        with app.app_context():
            now = now_utc()
            regen_secs = app.config["STAMINA_REGEN_SECONDS"]

            players = Player.query.filter(
                Player.stamina < Player.stamina_max
            ).all()

            updated = 0
            for player in players:
                elapsed = (now - player.stamina_last_regen).total_seconds()
                ticks = int(elapsed // regen_secs)
                if ticks > 0:
                    gain = min(ticks, player.stamina_max - player.stamina)
                    player.stamina += gain
                    player.stamina_last_regen = now
                    updated += 1

            db.session.commit()
            return {"players_updated": updated}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@worker.task(name="celery_worker.tasks.property_income_tick")
def property_income_tick():
    """
    Property income is calculated on-the-fly from last_collected_at.
    This task just logs the tick — no DB writes needed.
    Players collect manually and the pending_income property calculates it.
    """
    return {"status": "tick recorded", "at": now_utc().isoformat()}


@worker.task(name="celery_worker.tasks.hospital_release", bind=True, max_retries=3)
def hospital_release(self):
    """Release players whose hospital time has expired."""
    try:
        from app import create_app, db
        from app.models import Player, Notification
        app = get_flask_app()  # shared (no per-task pool)
        with app.app_context():
            now = now_utc()
            patients = Player.query.filter(
                Player.in_hospital == True,
                Player.hospital_release_at <= now
            ).all()

            released = 0
            for player in patients:
                player.in_hospital = False
                player.hospital_release_at = None
                player.health = max(player.health, 10)  # release with at least 10hp

                # Notify player
                notif = Notification(
                    player_id=player.id,
                    type="system",
                    title="Released from Hospital",
                    message="You've been patched up and released. Watch your back.",
                    link="/game/dashboard",
                )
                db.session.add(notif)
                released += 1

            db.session.commit()

            # Push SocketIO notifications
            if released > 0:
                _push_hospital_release_notifications(patients)

            return {"released": released}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=15)


@worker.task(name="celery_worker.tasks.jail_release", bind=True, max_retries=3)
def jail_release(self):
    """Release players from jail when sentence expires."""
    try:
        from app import create_app, db
        from app.models import JobLog, Player, Notification
        from sqlalchemy import and_
        app = get_flask_app()  # shared (no per-task pool)
        with app.app_context():
            now = now_utc()
            # Find jailed logs that have expired
            expired = JobLog.query.filter(
                and_(
                    JobLog.jailed == True,
                    JobLog.jail_release_at <= now,
                )
            ).all()

            released_players = set()
            for log in expired:
                log.jailed = False
                released_players.add(log.player_id)

            for player_id in released_players:
                notif = Notification(
                    player_id=player_id,
                    type="system",
                    title="Released from Jail",
                    message="You're free. Don't get caught again.",
                    link="/game/dashboard",
                )
                db.session.add(notif)

            db.session.commit()
            return {"released_from_jail": len(released_players)}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=15)


@worker.task(name="celery_worker.tasks.daily_reset")
def daily_reset():
    """
    Daily midnight reset:
    - Credit property income automatically
    - Reset daily crime counters
    - Award gang territory bonuses
    """
    from app import create_app, db
    from app.models import Player, Gang
    app = get_flask_app()  # shared (no per-task pool)
    with app.app_context():
        # Give each gang territory bonus to leader's bank
        gangs = Gang.query.filter(Gang.territory_points > 0).all()
        for gang in gangs:
            bonus = gang.territory_points * 100  # $100 per territory point
            gang.bank += bonus

        db.session.commit()
        return {"status": "daily reset complete", "gangs_paid": len(gangs)}


@worker.task(name="celery_worker.tasks.refresh_leaderboard_cache")
def refresh_leaderboard_cache():
    """Pre-compute and cache leaderboard data."""
    from app import create_app, cache
    from app.models import Player, Gang
    from sqlalchemy import desc
    app = get_flask_app()  # shared (no per-task pool)
    with app.app_context():
        # Top players by level/XP
        top_players = Player.query.order_by(
            desc(Player.level), desc(Player.experience)
        ).limit(100).all()

        leaderboard = [
            {
                "rank": i + 1,
                "display_name": p.display_name,
                "slug": p.slug,
                "level": p.level,
                "fights_won": p.fights_won,
                "gang": p.gang.tag if p.gang else None,
            }
            for i, p in enumerate(top_players)
        ]

        cache.set("leaderboard:players", leaderboard, timeout=700)

        return {"cached_players": len(leaderboard)}


def _push_hospital_release_notifications(players):
    """Fire SocketIO events for released players (best effort)."""
    try:
        from flask_socketio import SocketIO
        import redis as redis_lib
        import os
        # Push via Redis pub/sub to SocketIO server
        r = redis_lib.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        for player in players:
            r.publish(f"player:{player.id}:notify", "hospital_release")
    except Exception:
        pass  # Non-critical
