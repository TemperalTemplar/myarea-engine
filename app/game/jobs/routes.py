import random
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.route("/")
@login_required
def index():
    from app.models import JobTemplate, JobLog
    from sqlalchemy import desc
    jobs = JobTemplate.query.filter_by(is_active=True).order_by(
        JobTemplate.min_level, JobTemplate.energy_cost
    ).all()
    recent = JobLog.query.filter_by(
        player_id=current_user.player.id
    ).order_by(desc(JobLog.attempted_at)).limit(10).all()
    return render_template("game/jobs.html", jobs=jobs, recent=recent)


@jobs_bp.route("/do/<int:job_id>", methods=["POST"])
@login_required
def do_job(job_id):
    from app.models import JobTemplate, JobLog, Notification
    from flask import current_app

    player = current_user.player
    job = JobTemplate.query.get_or_404(job_id)

    # Checks
    if player.level < job.min_level:
        flash(f"You need to be level {job.min_level} for this job.", "danger")
        return redirect(url_for("jobs.index"))

    if player.energy < job.energy_cost:
        flash(f"Not enough energy. Need {job.energy_cost}, have {player.energy}.", "danger")
        return redirect(url_for("jobs.index"))

    if player.in_hospital:
        flash("You can't work from the hospital.", "danger")
        return redirect(url_for("jobs.index"))

    # Deduct energy
    player.energy -= job.energy_cost

    # Calculate success — higher level/crime_points improves odds slightly
    bonus = min(0.15, player.level * 0.003 + player.crime_points * 0.001)
    success_rate = min(0.95, job.base_success_rate + bonus)
    success = random.random() < success_rate

    log = JobLog(
        player_id=player.id,
        job_id=job.id,
        success=success,
    )

    if success:
        cash = random.randint(job.cash_min, job.cash_max)
        # Scale cash with level
        cash = int(cash * (1 + player.level * 0.05))
        xp = job.xp_reward
        player.cash += cash
        player.experience += xp
        player.crime_points += job.crime_points
        log.cash_earned = cash
        log.xp_earned = xp

        # Level up check
        _check_level_up(player, current_app)

        flash(f"✅ {job.name} successful! +${cash:,} +{xp}xp", "success")
    else:
        # Jail check
        if random.random() < 0.4:
            release = datetime.now(timezone.utc) + timedelta(seconds=job.jail_time_seconds)
            log.jailed = True
            log.jail_release_at = release
            flash(f"❌ Caught! You're in jail for {job.jail_time_seconds//60} minutes.", "danger")
        else:
            flash(f"❌ {job.name} failed. Better luck next time.", "warning")

    db.session.add(log)
    db.session.commit()
    return redirect(url_for("jobs.index"))


def _check_level_up(player, app):
    from app.models import Notification
    xp_table = app.config.get("LEVEL_XP_TABLE", {})
    next_level = player.level + 1
    xp_needed = xp_table.get(next_level, int(100 * (next_level ** 1.8)))
    if player.experience >= xp_needed and player.level < 200:
        player.level = next_level
        player.energy_max += 2
        player.stamina_max += 1
        player.health_max += 5
        notif = Notification(
            player_id=player.id,
            type="system",
            title=f"Level Up! You are now level {next_level}",
            message="Your max energy, stamina and health have increased.",
            link="/game/dashboard",
        )
        db.session.add(notif)
