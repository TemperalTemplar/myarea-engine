from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db

items_bp = Blueprint("items", __name__)


@items_bp.route("/")
@login_required
def index():
    from app.models import Item
    player = current_user.player
    inventory = {pi.item_id: pi for pi in player.inventory}
    shop_items = Item.query.filter_by(is_active=True).filter(
        Item.buy_price != None
    ).order_by(Item.category, Item.buy_price).all()
    return render_template("game/items.html",
                           shop_items=shop_items, inventory=inventory, player=player)


@items_bp.route("/buy/<int:item_id>", methods=["POST"])
@login_required
def buy(item_id):
    from app.models import Item, PlayerItem
    player = current_user.player
    item = Item.query.get_or_404(item_id)

    if not item.buy_price:
        flash("This item is not for sale.", "danger")
        return redirect(url_for("items.index"))
    if player.cash < item.buy_price:
        flash(f"Not enough cash. Need ${item.buy_price:,}", "danger")
        return redirect(url_for("items.index"))

    player.cash -= item.buy_price
    existing = PlayerItem.query.filter_by(
        player_id=player.id, item_id=item.id
    ).first()
    if existing:
        existing.quantity += 1
    else:
        pi = PlayerItem(player_id=player.id, item_id=item.id, quantity=1)
        db.session.add(pi)
    db.session.commit()
    flash(f"✅ Bought {item.name}!", "success")
    return redirect(url_for("items.index"))


@items_bp.route("/sell/<int:item_id>", methods=["POST"])
@login_required
def sell(item_id):
    from app.models import Item, PlayerItem
    player = current_user.player
    pi = PlayerItem.query.filter_by(
        player_id=player.id, item_id=item_id
    ).first_or_404()

    if not pi.item.sell_price:
        flash("This item can't be sold.", "danger")
        return redirect(url_for("items.index"))

    player.cash += pi.item.sell_price
    if pi.quantity > 1:
        pi.quantity -= 1
    else:
        if pi.equipped:
            _unequip_bonuses(player, pi.item)
        db.session.delete(pi)
    db.session.commit()
    flash(f"Sold {pi.item.name} for ${pi.item.sell_price:,}", "info")
    return redirect(url_for("items.index"))


@items_bp.route("/equip/<int:item_id>", methods=["POST"])
@login_required
def equip(item_id):
    from app.models import PlayerItem
    player = current_user.player
    pi = PlayerItem.query.filter_by(
        player_id=player.id, item_id=item_id
    ).first_or_404()

    if pi.equipped:
        # Unequip
        _unequip_bonuses(player, pi.item)
        pi.equipped = False
        flash(f"Unequipped {pi.item.name}.", "info")
    else:
        # Equip
        pi.equipped = True
        player.attack_power += pi.item.attack_bonus
        player.defense_power += pi.item.defense_bonus
        player.health_max += pi.item.health_bonus
        player.energy_max += pi.item.energy_bonus
        player.stamina_max += pi.item.stamina_bonus
        flash(f"Equipped {pi.item.name}!", "success")

    db.session.commit()
    return redirect(url_for("items.index"))


@items_bp.route("/use/<int:item_id>", methods=["POST"])
@login_required
def use_item(item_id):
    from app.models import PlayerItem
    player = current_user.player
    pi = PlayerItem.query.filter_by(
        player_id=player.id, item_id=item_id
    ).first_or_404()

    if not pi.item.is_consumable:
        flash("That item can't be used.", "danger")
        return redirect(url_for("items.index"))

    item = pi.item
    if item.health_restore:
        player.health = min(player.health + item.health_restore, player.health_max)
    if item.energy_restore:
        player.energy = min(player.energy + item.energy_restore, player.energy_max)
    if item.stamina_restore:
        player.stamina = min(player.stamina + item.stamina_restore, player.stamina_max)

    if pi.quantity > 1:
        pi.quantity -= 1
    else:
        db.session.delete(pi)

    db.session.commit()
    flash(f"Used {item.name}.", "success")
    return redirect(url_for("items.index"))


def _unequip_bonuses(player, item):
    player.attack_power = max(1, player.attack_power - item.attack_bonus)
    player.defense_power = max(1, player.defense_power - item.defense_bonus)
    player.health_max = max(10, player.health_max - item.health_bonus)
    player.energy_max = max(10, player.energy_max - item.energy_bonus)
    player.stamina_max = max(5, player.stamina_max - item.stamina_bonus)
