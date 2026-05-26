"""
MyArea Game Engine — Admin Panel
/admin — requires is_admin=True
"""
import functools
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db

admin_bp = Blueprint("admin", __name__)


def admin_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


# ─── Dashboard ────────────────────────────────────────────────
@admin_bp.route("/")
@login_required
@admin_required
def index():
    from app.models import User, Player, Gang, JobLog, AttackLog, Item, JobTemplate
    from sqlalchemy import desc
    stats = {
        "players":       Player.query.count(),
        "users":         User.query.count(),
        "banned":        User.query.filter_by(is_banned=True).count(),
        "gangs":         Gang.query.count(),
        "jobs_today":    JobLog.query.filter(JobLog.attempted_at >= db.func.current_date()).count(),
        "attacks_today": AttackLog.query.filter(AttackLog.attacked_at >= db.func.current_date()).count(),
        "items":         Item.query.count(),
        "job_templates": JobTemplate.query.count(),
    }
    recent = Player.query.order_by(desc(Player.created_at)).limit(10).all()
    top    = Player.query.order_by(desc(Player.level), desc(Player.experience)).limit(5).all()
    return render_template("admin/index.html", stats=stats, recent=recent, top=top)


# ─── Players ──────────────────────────────────────────────────
@admin_bp.route("/players")
@login_required
@admin_required
def players():
    from app.models import Player, User
    from sqlalchemy import desc
    q    = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    query = Player.query
    if q:
        query = query.join(User).filter(
            (Player.display_name.ilike(f"%{q}%")) | (User.username.ilike(f"%{q}%"))
        )
    pagination = query.order_by(desc(Player.level)).paginate(page=page, per_page=30, error_out=False)
    return render_template("admin/players.html", pagination=pagination, q=q)


@admin_bp.route("/players/<int:player_id>")
@login_required
@admin_required
def player_detail(player_id):
    from app.models import Player, JobLog, AttackLog
    from sqlalchemy import desc, or_
    player       = Player.query.get_or_404(player_id)
    recent_jobs  = JobLog.query.filter_by(player_id=player_id).order_by(desc(JobLog.attempted_at)).limit(20).all()
    recent_attacks = AttackLog.query.filter(
        or_(AttackLog.attacker_id == player_id, AttackLog.defender_id == player_id)
    ).order_by(desc(AttackLog.attacked_at)).limit(20).all()
    return render_template("admin/player_detail.html", player=player,
                           recent_jobs=recent_jobs, recent_attacks=recent_attacks)


@admin_bp.route("/players/<int:player_id>/ban", methods=["POST"])
@login_required
@admin_required
def ban_player(player_id):
    from app.models import Player
    player = Player.query.get_or_404(player_id)
    if player.user.id == current_user.id:
        flash("You can't ban yourself.", "danger")
        return redirect(url_for("admin.player_detail", player_id=player_id))
    player.user.is_banned = not player.user.is_banned
    db.session.commit()
    flash(f"{'Banned' if player.user.is_banned else 'Unbanned'} {player.display_name}.", "success")
    return redirect(url_for("admin.player_detail", player_id=player_id))


@admin_bp.route("/players/<int:player_id>/edit", methods=["POST"])
@login_required
@admin_required
def edit_player(player_id):
    from app.models import Player
    player = Player.query.get_or_404(player_id)
    try:
        player.cash   = int(request.form.get("cash",   player.cash))
        player.level  = int(request.form.get("level",  player.level))
        player.energy = int(request.form.get("energy", player.energy))
        player.health = int(request.form.get("health", player.health))
    except ValueError:
        flash("Invalid values.", "danger")
        return redirect(url_for("admin.player_detail", player_id=player_id))
    db.session.commit()
    flash(f"Player {player.display_name} updated.", "success")
    return redirect(url_for("admin.player_detail", player_id=player_id))


# ─── Gangs ────────────────────────────────────────────────────
@admin_bp.route("/gangs")
@login_required
@admin_required
def gangs():
    from app.models import Gang
    from sqlalchemy import desc
    page       = request.args.get("page", 1, type=int)
    pagination = Gang.query.order_by(desc(Gang.territory_points)).paginate(page=page, per_page=30, error_out=False)
    return render_template("admin/gangs.html", pagination=pagination)


@admin_bp.route("/gangs/<int:gang_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_gang(gang_id):
    from app.models import Gang
    gang = Gang.query.get_or_404(gang_id)
    for member in gang.members:
        member.gang_id   = None
        member.gang_rank = None
    db.session.delete(gang)
    db.session.commit()
    flash(f"Gang {gang.name} deleted.", "success")
    return redirect(url_for("admin.gangs"))


# ═══════════════════════════════════════════════════════════════
# JOB TEMPLATES — full CRUD
# ═══════════════════════════════════════════════════════════════

@admin_bp.route("/jobs")
@login_required
@admin_required
def jobs():
    from app.models import JobTemplate
    jobs = JobTemplate.query.order_by(JobTemplate.min_level, JobTemplate.energy_cost).all()
    return render_template("admin/jobs.html", jobs=jobs)


@admin_bp.route("/jobs/new", methods=["GET", "POST"])
@login_required
@admin_required
def job_new():
    from app.models import JobTemplate
    if request.method == "POST":
        job = JobTemplate(
            name=request.form["name"].strip(),
            category=request.form["category"].strip(),
            description=request.form.get("description", "").strip() or None,
            min_level=int(request.form.get("min_level", 1)),
            energy_cost=int(request.form.get("energy_cost", 5)),
            cash_min=int(request.form.get("cash_min", 100)),
            cash_max=int(request.form.get("cash_max", 500)),
            xp_reward=int(request.form.get("xp_reward", 10)),
            crime_points=int(request.form.get("crime_points", 1)),
            base_success_rate=float(request.form.get("base_success_rate", 0.80)),
            jail_time_seconds=int(request.form.get("jail_time_seconds", 120)),
            cooldown_seconds=int(request.form.get("cooldown_seconds", 0)),
            is_active=True,
        )
        db.session.add(job)
        db.session.commit()
        flash(f"Job '{job.name}' created.", "success")
        return redirect(url_for("admin.jobs"))
    return render_template("admin/job_form.html", job=None, action="Create")


@admin_bp.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def job_edit(job_id):
    from app.models import JobTemplate
    job = JobTemplate.query.get_or_404(job_id)
    if request.method == "POST":
        job.name               = request.form["name"].strip()
        job.category           = request.form["category"].strip()
        job.description        = request.form.get("description", "").strip() or None
        job.min_level          = int(request.form.get("min_level", 1))
        job.energy_cost        = int(request.form.get("energy_cost", 5))
        job.cash_min           = int(request.form.get("cash_min", 100))
        job.cash_max           = int(request.form.get("cash_max", 500))
        job.xp_reward          = int(request.form.get("xp_reward", 10))
        job.crime_points       = int(request.form.get("crime_points", 1))
        job.base_success_rate  = float(request.form.get("base_success_rate", 0.80))
        job.jail_time_seconds  = int(request.form.get("jail_time_seconds", 120))
        job.cooldown_seconds   = int(request.form.get("cooldown_seconds", 0))
        db.session.commit()
        flash(f"Job '{job.name}' updated.", "success")
        return redirect(url_for("admin.jobs"))
    return render_template("admin/job_form.html", job=job, action="Edit")


@admin_bp.route("/jobs/<int:job_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_job(job_id):
    from app.models import JobTemplate
    job = JobTemplate.query.get_or_404(job_id)
    job.is_active = not job.is_active
    db.session.commit()
    flash(f"Job '{job.name}' {'enabled' if job.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin.jobs"))


@admin_bp.route("/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
@admin_required
def job_delete(job_id):
    from app.models import JobTemplate
    job = JobTemplate.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()
    flash(f"Job '{job.name}' deleted.", "success")
    return redirect(url_for("admin.jobs"))


# ═══════════════════════════════════════════════════════════════
# PROPERTY TEMPLATES — full CRUD
# ═══════════════════════════════════════════════════════════════

@admin_bp.route("/properties")
@login_required
@admin_required
def properties():
    from app.models import PropertyTemplate
    props = PropertyTemplate.query.order_by(PropertyTemplate.min_level, PropertyTemplate.purchase_price).all()
    return render_template("admin/properties.html", props=props)


@admin_bp.route("/properties/new", methods=["GET", "POST"])
@login_required
@admin_required
def property_new():
    from app.models import PropertyTemplate
    if request.method == "POST":
        prop = PropertyTemplate(
            name=request.form["name"].strip(),
            category=request.form["category"].strip(),
            description=request.form.get("description", "").strip() or None,
            purchase_price=int(request.form.get("purchase_price", 10000)),
            sell_price=int(request.form.get("sell_price", 7000)),
            income_per_hour=int(request.form.get("income_per_hour", 0)),
            defense_bonus=int(request.form.get("defense_bonus", 0)),
            attack_bonus=int(request.form.get("attack_bonus", 0)),
            energy_bonus=int(request.form.get("energy_bonus", 0)),
            min_level=int(request.form.get("min_level", 1)),
            max_owned=int(request.form.get("max_owned", 1)),
            is_active=True,
        )
        db.session.add(prop)
        db.session.commit()
        flash(f"Property '{prop.name}' created.", "success")
        return redirect(url_for("admin.properties"))
    return render_template("admin/property_form.html", prop=None, action="Create")


@admin_bp.route("/properties/<int:prop_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def property_edit(prop_id):
    from app.models import PropertyTemplate
    prop = PropertyTemplate.query.get_or_404(prop_id)
    if request.method == "POST":
        prop.name           = request.form["name"].strip()
        prop.category       = request.form["category"].strip()
        prop.description    = request.form.get("description", "").strip() or None
        prop.purchase_price = int(request.form.get("purchase_price", prop.purchase_price))
        prop.sell_price     = int(request.form.get("sell_price", prop.sell_price))
        prop.income_per_hour= int(request.form.get("income_per_hour", prop.income_per_hour))
        prop.defense_bonus  = int(request.form.get("defense_bonus", prop.defense_bonus))
        prop.attack_bonus   = int(request.form.get("attack_bonus", prop.attack_bonus))
        prop.energy_bonus   = int(request.form.get("energy_bonus", prop.energy_bonus))
        prop.min_level      = int(request.form.get("min_level", prop.min_level))
        prop.max_owned      = int(request.form.get("max_owned", prop.max_owned))
        db.session.commit()
        flash(f"Property '{prop.name}' updated.", "success")
        return redirect(url_for("admin.properties"))
    return render_template("admin/property_form.html", prop=prop, action="Edit")


@admin_bp.route("/properties/<int:prop_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_property(prop_id):
    from app.models import PropertyTemplate
    prop = PropertyTemplate.query.get_or_404(prop_id)
    prop.is_active = not prop.is_active
    db.session.commit()
    flash(f"Property '{prop.name}' {'enabled' if prop.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin.properties"))


@admin_bp.route("/properties/<int:prop_id>/delete", methods=["POST"])
@login_required
@admin_required
def property_delete(prop_id):
    from app.models import PropertyTemplate
    prop = PropertyTemplate.query.get_or_404(prop_id)
    db.session.delete(prop)
    db.session.commit()
    flash(f"Property '{prop.name}' deleted.", "success")
    return redirect(url_for("admin.properties"))


# ═══════════════════════════════════════════════════════════════
# ITEMS — full CRUD
# ═══════════════════════════════════════════════════════════════

@admin_bp.route("/items")
@login_required
@admin_required
def items():
    from app.models import Item
    items = Item.query.order_by(Item.category, Item.buy_price).all()
    return render_template("admin/items.html", items=items)


@admin_bp.route("/items/new", methods=["GET", "POST"])
@login_required
@admin_required
def item_new():
    from app.models import Item
    from slugify import slugify
    if request.method == "POST":
        name = request.form["name"].strip()
        slug = slugify(name)
        # Make slug unique
        base_slug = slug
        n = 1
        while Item.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{n}"
            n += 1
        item = Item(
            name=name, slug=slug,
            category=request.form["category"].strip(),
            rarity=request.form.get("rarity", "common"),
            description=request.form.get("description", "").strip() or None,
            buy_price=int(request.form["buy_price"]) if request.form.get("buy_price") else None,
            sell_price=int(request.form["sell_price"]) if request.form.get("sell_price") else None,
            attack_bonus=int(request.form.get("attack_bonus", 0)),
            defense_bonus=int(request.form.get("defense_bonus", 0)),
            health_bonus=int(request.form.get("health_bonus", 0)),
            energy_bonus=int(request.form.get("energy_bonus", 0)),
            stamina_bonus=int(request.form.get("stamina_bonus", 0)),
            is_consumable=bool(request.form.get("is_consumable")),
            health_restore=int(request.form.get("health_restore", 0)),
            energy_restore=int(request.form.get("energy_restore", 0)),
            stamina_restore=int(request.form.get("stamina_restore", 0)),
            is_tradeable=bool(request.form.get("is_tradeable", True)),
            is_active=True,
        )
        db.session.add(item)
        db.session.commit()
        flash(f"Item '{item.name}' created.", "success")
        return redirect(url_for("admin.items"))
    return render_template("admin/item_form.html", item=None, action="Create")


@admin_bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def item_edit(item_id):
    from app.models import Item
    item = Item.query.get_or_404(item_id)
    if request.method == "POST":
        item.name           = request.form["name"].strip()
        item.category       = request.form["category"].strip()
        item.rarity         = request.form.get("rarity", item.rarity)
        item.description    = request.form.get("description", "").strip() or None
        item.buy_price      = int(request.form["buy_price"]) if request.form.get("buy_price") else None
        item.sell_price     = int(request.form["sell_price"]) if request.form.get("sell_price") else None
        item.attack_bonus   = int(request.form.get("attack_bonus", 0))
        item.defense_bonus  = int(request.form.get("defense_bonus", 0))
        item.health_bonus   = int(request.form.get("health_bonus", 0))
        item.energy_bonus   = int(request.form.get("energy_bonus", 0))
        item.stamina_bonus  = int(request.form.get("stamina_bonus", 0))
        item.is_consumable  = bool(request.form.get("is_consumable"))
        item.health_restore = int(request.form.get("health_restore", 0))
        item.energy_restore = int(request.form.get("energy_restore", 0))
        item.stamina_restore= int(request.form.get("stamina_restore", 0))
        item.is_tradeable   = bool(request.form.get("is_tradeable", True))
        db.session.commit()
        flash(f"Item '{item.name}' updated.", "success")
        return redirect(url_for("admin.items"))
    return render_template("admin/item_form.html", item=item, action="Edit")


@admin_bp.route("/items/<int:item_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_item(item_id):
    from app.models import Item
    item = Item.query.get_or_404(item_id)
    item.is_active = not item.is_active
    db.session.commit()
    flash(f"Item '{item.name}' {'enabled' if item.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin.items"))


@admin_bp.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
@admin_required
def item_delete(item_id):
    from app.models import Item
    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash(f"Item '{item.name}' deleted.", "success")
    return redirect(url_for("admin.items"))


# ─── Notify all players ───────────────────────────────────────
@admin_bp.route("/notify", methods=["GET", "POST"])
@login_required
@admin_required
def notify_all():
    from app.models import Player, Notification
    if request.method == "POST":
        title   = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        link    = request.form.get("link", "").strip() or None
        if not title or not message:
            flash("Title and message required.", "danger")
            return redirect(url_for("admin.notify_all"))
        players = Player.query.all()
        for p in players:
            db.session.add(Notification(player_id=p.id, type="system",
                                        title=title, message=message, link=link))
        db.session.commit()
        flash(f"Notification sent to {len(players)} players.", "success")
        return redirect(url_for("admin.index"))
    return render_template("admin/notify.html")


# ─── Re-seed game data ────────────────────────────────────────
@admin_bp.route("/seed", methods=["POST"])
@login_required
@admin_required
def reseed():
    from app.cli import _seed_jobs, _seed_properties, _seed_items
    from app.models import JobTemplate, PropertyTemplate, Item
    from slugify import slugify
    _seed_jobs(db, JobTemplate)
    _seed_properties(db, PropertyTemplate)
    _seed_items(db, Item, slugify)
    db.session.commit()
    flash("Game data re-seeded (new entries only).", "success")
    return redirect(url_for("admin.index"))
