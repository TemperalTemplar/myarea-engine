import random
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db

attacks_bp = Blueprint("attacks", __name__)


@attacks_bp.route("/")
@login_required
def index():
    from app.models import Player, AttackLog
    from sqlalchemy import desc, and_, or_

    player = current_user.player

    # Find attackable players — not self, not in hospital, within 5 levels
    targets = Player.query.filter(
        Player.id != player.id,
        Player.in_hospital == False,
        Player.level >= max(1, player.level - 5),
        Player.level <= player.level + 5,
    ).order_by(db.func.random()).limit(20).all()

    recent = AttackLog.query.filter(
        or_(
            AttackLog.attacker_id == player.id,
            AttackLog.defender_id == player.id,
        )
    ).order_by(desc(AttackLog.attacked_at)).limit(15).all()

    return render_template("game/attacks.html", targets=targets, recent=recent, player=player)


@attacks_bp.route("/attack/<int:target_id>", methods=["POST"])
@login_required
def attack(target_id):
    from app.models import Player, AttackLog, Notification
    from flask import current_app

    attacker = current_user.player
    defender = Player.query.get_or_404(target_id)

    # Checks
    if defender.id == attacker.id:
        flash("You can't attack yourself.", "danger")
        return redirect(url_for("attacks.index"))
    if attacker.stamina < 1:
        flash("Not enough stamina to attack.", "danger")
        return redirect(url_for("attacks.index"))
    if attacker.in_hospital:
        flash("You can't fight from the hospital.", "danger")
        return redirect(url_for("attacks.index"))
    if defender.in_hospital:
        flash("That player is already in the hospital.", "warning")
        return redirect(url_for("attacks.index"))

    attacker.stamina -= 1

    # Combat — attack vs defense with randomness
    atk_roll = attacker.attack_power * random.uniform(0.8, 1.2)
    def_roll = defender.defense_power * random.uniform(0.8, 1.2)
    attacker_won = atk_roll > def_roll

    winner = attacker if attacker_won else defender
    cash_stolen = 0
    hospitalized = False

    if attacker_won:
        # Steal up to 10% of defender's cash
        cash_stolen = int(min(defender.cash, defender.cash * random.uniform(0.05, 0.10)))
        defender.cash -= cash_stolen
        attacker.cash += cash_stolen
        attacker.experience += 25
        attacker.fights_won += 1
        defender.fights_lost += 1

        # Chance to hospitalize
        if random.random() < 0.25:
            hospitalized = True
            defender.in_hospital = True
            hospital_secs = random.randint(120, 600)
            defender.hospital_release_at = datetime.now(timezone.utc) + timedelta(seconds=hospital_secs)
            notif = Notification(
                player_id=defender.id,
                type="attack",
                title=f"Hospitalized by {attacker.display_name}!",
                message=f"You were sent to the hospital for {hospital_secs//60} minutes.",
                link="/game/dashboard",
            )
            db.session.add(notif)

        flash(f"✅ You beat {defender.display_name}! Stole ${cash_stolen:,}", "success")
    else:
        attacker.fights_lost += 1
        defender.fights_won += 1
        attacker.experience += 5
        flash(f"❌ {defender.display_name} overpowered you. Better luck next time.", "danger")

    # Notify defender
    notif = Notification(
        player_id=defender.id,
        type="attack",
        title=f"{'Lost' if attacker_won else 'Defended'} against {attacker.display_name}",
        message=f"{'Lost' if attacker_won else 'You held your ground'}" +
                (f" and ${cash_stolen:,} was stolen." if cash_stolen else "."),
        link="/game/attacks",
    )
    db.session.add(notif)

    log = AttackLog(
        attacker_id=attacker.id,
        defender_id=defender.id,
        attacker_power=int(atk_roll),
        defender_power=int(def_roll),
        winner_id=winner.id,
        cash_stolen=cash_stolen,
        xp_earned=25 if attacker_won else 5,
        defender_hospitalized=hospitalized,
    )
    db.session.add(log)
    db.session.commit()
    return redirect(url_for("attacks.index"))
