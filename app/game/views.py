from flask import render_template, abort
from flask_login import login_required, current_user
from app.game.routes import game_bp
from app import db, cache


@game_bp.route("/dashboard")
@login_required
def dashboard():
    from app.models import Notification, Player
    from sqlalchemy import desc

    notifications = Notification.query.filter_by(
        player_id=current_user.player.id
    ).order_by(desc(Notification.created_at)).limit(8).all()

    leaderboard = cache.get("leaderboard:players") or []
    if not leaderboard:
        top = Player.query.order_by(
            desc(Player.level), desc(Player.experience)
        ).limit(10).all()
        leaderboard = [
            {"rank": i+1, "display_name": p.display_name, "slug": p.slug,
             "level": p.level, "fights_won": p.fights_won,
             "gang_tag": p.gang.tag if p.gang else None}
            for i, p in enumerate(top)
        ]

    return render_template("game/dashboard.html",
                           notifications=notifications,
                           leaderboard=leaderboard)


@game_bp.route("/profile/<slug>")
@login_required
def profile(slug):
    from app.models import Player
    player = Player.query.filter_by(slug=slug).first_or_404()
    return render_template("game/profile.html", player=player)


@game_bp.route("/leaderboard")
def leaderboard():
    from app.models import Player
    from sqlalchemy import desc

    top = Player.query.order_by(
        desc(Player.level), desc(Player.experience)
    ).limit(100).all()

    leaderboard = [
        {"rank": i+1, "display_name": p.display_name, "slug": p.slug,
         "level": p.level, "fights_won": p.fights_won,
         "crime_points": p.crime_points,
         "gang_tag": p.gang.tag if p.gang else None}
        for i, p in enumerate(top)
    ]
    return render_template("game/leaderboard.html", leaderboard=leaderboard)
