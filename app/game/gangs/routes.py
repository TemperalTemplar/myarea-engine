"""
Gang system — create, join, leave, manage, territory.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db

gangs_bp = Blueprint("gangs", __name__)


@gangs_bp.route("/")
@login_required
def index():
    from app.models import Gang
    from sqlalchemy import desc
    player = current_user.player
    gangs = Gang.query.order_by(desc(Gang.territory_points)).all()
    return render_template("game/gangs/index.html", gangs=gangs, player=player)


@gangs_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    player = current_user.player

    if player.gang_id:
        flash("You must leave your current gang before creating one.", "danger")
        return redirect(url_for("gangs.index"))

    if player.level < 5:
        flash("You need to be level 5 to create a gang.", "danger")
        return redirect(url_for("gangs.index"))

    if request.method == "POST":
        from app.models import Gang
        from slugify import slugify

        name        = request.form.get("name", "").strip()
        tag         = request.form.get("tag", "").strip().upper()
        description = request.form.get("description", "").strip()

        errors = []
        if len(name) < 3 or len(name) > 64:
            errors.append("Gang name must be 3-64 characters.")
        if len(tag) < 2 or len(tag) > 6:
            errors.append("Tag must be 2-6 characters.")
        if not tag.isalnum():
            errors.append("Tag must be letters and numbers only.")
        if Gang.query.filter_by(name=name).first():
            errors.append("That gang name is already taken.")
        if Gang.query.filter_by(tag=tag).first():
            errors.append("That tag is already taken.")
        if player.cash < 50000:
            errors.append("Creating a gang costs $50,000.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("game/gangs/create.html", player=player)

        player.cash -= 50000
        slug = slugify(name)
        from app.models import Gang
        gang = Gang(name=name, slug=slug, tag=tag,
                    description=description, leader_id=player.id)
        db.session.add(gang)
        db.session.flush()
        player.gang_id = gang.id
        player.gang_rank = "leader"
        db.session.commit()
        flash(f"Gang [{tag}] {name} created!", "success")
        return redirect(url_for("gangs.view", slug=slug))

    return render_template("game/gangs/create.html", player=player)


@gangs_bp.route("/<slug>")
@login_required
def view(slug):
    from app.models import Gang
    gang = Gang.query.filter_by(slug=slug).first_or_404()
    player = current_user.player
    is_member = player.gang_id == gang.id
    is_leader = gang.leader_id == player.id
    return render_template("game/gangs/view.html",
                           gang=gang, player=player,
                           is_member=is_member, is_leader=is_leader)


@gangs_bp.route("/<slug>/join", methods=["POST"])
@login_required
def join(slug):
    from app.models import Gang
    player = current_user.player
    gang = Gang.query.filter_by(slug=slug).first_or_404()

    if player.gang_id:
        flash("Leave your current gang first.", "danger")
        return redirect(url_for("gangs.view", slug=slug))
    if gang.member_count >= 50:
        flash("This gang is full (max 50 members).", "danger")
        return redirect(url_for("gangs.view", slug=slug))

    player.gang_id = gang.id
    player.gang_rank = "member"
    db.session.commit()
    flash(f"You joined [{gang.tag}] {gang.name}!", "success")
    return redirect(url_for("gangs.view", slug=slug))


@gangs_bp.route("/<slug>/leave", methods=["POST"])
@login_required
def leave(slug):
    from app.models import Gang
    player = current_user.player
    gang = Gang.query.filter_by(slug=slug).first_or_404()

    if player.gang_id != gang.id:
        flash("You're not in this gang.", "danger")
        return redirect(url_for("gangs.view", slug=slug))

    if gang.leader_id == player.id:
        other = next((m for m in gang.members if m.id != player.id), None)
        if other:
            gang.leader_id = other.id
            other.gang_rank = "leader"
        else:
            db.session.delete(gang)
            player.gang_id = None
            player.gang_rank = None
            db.session.commit()
            flash("Gang disbanded.", "info")
            return redirect(url_for("gangs.index"))

    player.gang_id = None
    player.gang_rank = None
    db.session.commit()
    flash("You left the gang.", "info")
    return redirect(url_for("gangs.index"))


@gangs_bp.route("/<slug>/kick/<int:player_id>", methods=["POST"])
@login_required
def kick(slug, player_id):
    from app.models import Gang, Player
    player = current_user.player
    gang = Gang.query.filter_by(slug=slug).first_or_404()

    if gang.leader_id != player.id:
        flash("Only the leader can kick members.", "danger")
        return redirect(url_for("gangs.view", slug=slug))

    target = Player.query.get_or_404(player_id)
    if target.gang_id != gang.id or target.id == player.id:
        flash("Invalid target.", "danger")
        return redirect(url_for("gangs.view", slug=slug))

    target.gang_id = None
    target.gang_rank = None
    db.session.commit()
    flash(f"{target.display_name} kicked.", "success")
    return redirect(url_for("gangs.view", slug=slug))


@gangs_bp.route("/<slug>/deposit", methods=["POST"])
@login_required
def deposit(slug):
    from app.models import Gang
    player = current_user.player
    gang = Gang.query.filter_by(slug=slug).first_or_404()

    if player.gang_id != gang.id:
        flash("You're not in this gang.", "danger")
        return redirect(url_for("gangs.view", slug=slug))

    try:
        amount = int(request.form.get("amount", 0))
    except ValueError:
        amount = 0

    if amount <= 0 or player.cash < amount:
        flash("Invalid amount or not enough cash.", "danger")
        return redirect(url_for("gangs.view", slug=slug))

    player.cash -= amount
    gang.bank += amount
    db.session.commit()
    flash(f"Deposited ${amount:,} into gang bank.", "success")
    return redirect(url_for("gangs.view", slug=slug))


@gangs_bp.route("/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit(slug):
    from app.models import Gang
    player = current_user.player
    gang = Gang.query.filter_by(slug=slug).first_or_404()

    if gang.leader_id != player.id:
        flash("Only the leader can edit the gang.", "danger")
        return redirect(url_for("gangs.view", slug=slug))

    if request.method == "POST":
        gang.description = request.form.get("description", "").strip()
        db.session.commit()
        flash("Gang updated.", "success")
        return redirect(url_for("gangs.view", slug=slug))

    return render_template("game/gangs/edit.html", gang=gang, player=player)
