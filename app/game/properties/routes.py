from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db

properties_bp = Blueprint("properties", __name__)


@properties_bp.route("/")
@login_required
def index():
    from app.models import PropertyTemplate, Property
    player = current_user.player
    owned = {p.template_id: p for p in player.properties}
    templates = PropertyTemplate.query.filter_by(is_active=True).order_by(
        PropertyTemplate.min_level, PropertyTemplate.purchase_price
    ).all()
    return render_template("game/properties.html",
                           templates=templates, owned=owned, player=player)


@properties_bp.route("/buy/<int:template_id>", methods=["POST"])
@login_required
def buy(template_id):
    from app.models import PropertyTemplate, Property
    player = current_user.player
    tmpl = PropertyTemplate.query.get_or_404(template_id)

    if player.level < tmpl.min_level:
        flash(f"Need level {tmpl.min_level} to buy this.", "danger")
        return redirect(url_for("properties.index"))

    already_owned = Property.query.filter_by(
        owner_id=player.id, template_id=tmpl.id
    ).count()
    if already_owned >= tmpl.max_owned:
        flash("You already own the maximum number of this property.", "warning")
        return redirect(url_for("properties.index"))

    if player.cash < tmpl.purchase_price:
        flash(f"Not enough cash. Need ${tmpl.purchase_price:,}", "danger")
        return redirect(url_for("properties.index"))

    player.cash -= tmpl.purchase_price
    if tmpl.energy_bonus:
        player.energy_max += tmpl.energy_bonus

    prop = Property(owner_id=player.id, template_id=tmpl.id)
    db.session.add(prop)
    db.session.commit()
    flash(f"✅ You bought {tmpl.name}!", "success")
    return redirect(url_for("properties.index"))


@properties_bp.route("/sell/<int:property_id>", methods=["POST"])
@login_required
def sell(property_id):
    from app.models import Property
    player = current_user.player
    prop = Property.query.filter_by(
        id=property_id, owner_id=player.id
    ).first_or_404()

    tmpl = prop.template
    player.cash += tmpl.sell_price
    if tmpl.energy_bonus:
        player.energy_max = max(player.energy_max - tmpl.energy_bonus,
                                current_user.player.energy_max)
    db.session.delete(prop)
    db.session.commit()
    flash(f"Sold {tmpl.name} for ${tmpl.sell_price:,}", "info")
    return redirect(url_for("properties.index"))


@properties_bp.route("/collect", methods=["POST"])
@login_required
def collect():
    from app.models import Property
    from datetime import datetime, timezone
    player = current_user.player
    total = 0
    for prop in player.properties:
        income = prop.pending_income
        if income > 0:
            total += income
            prop.income_collected += income
            prop.last_collected_at = datetime.now(timezone.utc)
    player.cash += total
    db.session.commit()
    if total:
        flash(f"✅ Collected ${total:,} from your properties.", "success")
    else:
        flash("No income to collect yet.", "info")
    return redirect(url_for("properties.index"))
