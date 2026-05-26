"""
MyArea — Database Models
Full game schema: users, players, properties, items, gangs, jobs, attacks.
"""

from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from typing import Optional
from flask_login import UserMixin
from sqlalchemy import event
from app import db


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════
# USER & PLAYER
# ═══════════════════════════════════════════════════════════════

class User(UserMixin, db.Model):
    """Authentication record — one per human. Linked to one Player profile."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True)   # null if OIDC-only
    oidc_sub = db.Column(db.String(256), unique=True, nullable=True)  # Authentik sub
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_banned = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)

    player = db.relationship("Player", back_populates="user", uselist=False,
                             cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Player(db.Model):
    """
    In-game profile and all stats. Separate from User so game logic
    never touches auth data directly.
    """
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(32), nullable=False)
    avatar_url = db.Column(db.String(512), nullable=True)

    # ── Core stats ────────────────────────────────────────────
    level = db.Column(db.Integer, default=1, nullable=False)
    experience = db.Column(db.BigInteger, default=0, nullable=False)
    cash = db.Column(db.BigInteger, default=0, nullable=False)      # on-hand cash
    bank = db.Column(db.BigInteger, default=0, nullable=False)      # banked (safe)
    crime_points = db.Column(db.Integer, default=0, nullable=False)  # reputation

    # ── Energy & Stamina (regenerate over time) ───────────────
    energy = db.Column(db.Integer, default=50, nullable=False)
    energy_max = db.Column(db.Integer, default=100, nullable=False)
    energy_last_regen = db.Column(db.DateTime(timezone=True), default=now_utc)

    stamina = db.Column(db.Integer, default=25, nullable=False)
    stamina_max = db.Column(db.Integer, default=50, nullable=False)
    stamina_last_regen = db.Column(db.DateTime(timezone=True), default=now_utc)

    # ── Health (recovers via items/hospitals) ─────────────────
    health = db.Column(db.Integer, default=100, nullable=False)
    health_max = db.Column(db.Integer, default=100, nullable=False)
    in_hospital = db.Column(db.Boolean, default=False, nullable=False)
    hospital_release_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # ── Combat stats ──────────────────────────────────────────
    attack_power = db.Column(db.Integer, default=10, nullable=False)
    defense_power = db.Column(db.Integer, default=10, nullable=False)
    fights_won = db.Column(db.Integer, default=0, nullable=False)
    fights_lost = db.Column(db.Integer, default=0, nullable=False)

    # ── Gang membership ───────────────────────────────────────
    gang_id = db.Column(db.Integer, db.ForeignKey("gangs.id"), nullable=True)
    gang_rank = db.Column(db.String(32), default="member", nullable=True)

    # ── Timestamps ────────────────────────────────────────────
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    last_active = db.Column(db.DateTime(timezone=True), default=now_utc)

    # ── Relationships ─────────────────────────────────────────
    user = db.relationship("User", back_populates="player")
    gang = db.relationship("Gang", back_populates="members", foreign_keys=[gang_id])
    properties = db.relationship("Property", back_populates="owner",
                                  cascade="all, delete-orphan")
    inventory = db.relationship("PlayerItem", back_populates="player",
                                 cascade="all, delete-orphan")
    attacks_sent = db.relationship("AttackLog", foreign_keys="AttackLog.attacker_id",
                                   back_populates="attacker")
    attacks_received = db.relationship("AttackLog", foreign_keys="AttackLog.defender_id",
                                        back_populates="defender")

    @property
    def is_alive(self) -> bool:
        return self.health > 0 and not self.in_hospital

    @property
    def fight_ratio(self) -> float:
        total = self.fights_won + self.fights_lost
        return round(self.fights_won / total, 2) if total > 0 else 0.0

    def __repr__(self) -> str:
        return f"<Player {self.display_name} Lv{self.level}>"


# ═══════════════════════════════════════════════════════════════
# GANGS
# ═══════════════════════════════════════════════════════════════

class Gang(db.Model):
    __tablename__ = "gangs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    tag = db.Column(db.String(8), unique=True, nullable=False)   # [TAG] prefix
    description = db.Column(db.Text, nullable=True)
    logo_url = db.Column(db.String(512), nullable=True)

    leader_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=True)
    bank = db.Column(db.BigInteger, default=0, nullable=False)
    territory_points = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    members = db.relationship("Player", back_populates="gang",
                               foreign_keys="Player.gang_id")
    leader = db.relationship("Player", foreign_keys=[leader_id])

    @property
    def member_count(self) -> int:
        return len(self.members)

    def __repr__(self) -> str:
        return f"<Gang [{self.tag}] {self.name}>"


# ═══════════════════════════════════════════════════════════════
# JOBS / CRIMES
# ═══════════════════════════════════════════════════════════════

class JobTemplate(db.Model):
    """Reusable crime/job definition (seeded by admin)."""
    __tablename__ = "job_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(32), nullable=False)  # crime, hustle, heist
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(512), nullable=True)

    # Requirements
    min_level = db.Column(db.Integer, default=1)
    energy_cost = db.Column(db.Integer, default=5, nullable=False)

    # Rewards (base, scaled by level)
    cash_min = db.Column(db.Integer, default=100)
    cash_max = db.Column(db.Integer, default=500)
    xp_reward = db.Column(db.Integer, default=10)
    crime_points = db.Column(db.Integer, default=1)

    # Success/failure mechanics
    base_success_rate = db.Column(db.Float, default=0.80)  # 80%
    jail_time_seconds = db.Column(db.Integer, default=120)  # if caught
    cooldown_seconds = db.Column(db.Integer, default=0)

    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self) -> str:
        return f"<Job {self.name}>"


class JobLog(db.Model):
    """Record of every job attempt a player makes."""
    __tablename__ = "job_logs"

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job_templates.id"), nullable=False)
    success = db.Column(db.Boolean, nullable=False)
    cash_earned = db.Column(db.Integer, default=0)
    xp_earned = db.Column(db.Integer, default=0)
    jailed = db.Column(db.Boolean, default=False)
    jail_release_at = db.Column(db.DateTime(timezone=True), nullable=True)
    attempted_at = db.Column(db.DateTime(timezone=True), default=now_utc, index=True)

    player = db.relationship("Player")
    job = db.relationship("JobTemplate")


# ═══════════════════════════════════════════════════════════════
# PROPERTIES
# ═══════════════════════════════════════════════════════════════

class PropertyTemplate(db.Model):
    """Blueprint for purchasable properties."""
    __tablename__ = "property_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(32), nullable=False)  # residential, business, criminal
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(512), nullable=True)

    purchase_price = db.Column(db.BigInteger, nullable=False)
    sell_price = db.Column(db.BigInteger, nullable=False)
    income_per_hour = db.Column(db.Integer, default=0)   # passive income
    defense_bonus = db.Column(db.Integer, default=0)
    attack_bonus = db.Column(db.Integer, default=0)
    energy_bonus = db.Column(db.Integer, default=0)      # increases max energy

    min_level = db.Column(db.Integer, default=1)
    max_owned = db.Column(db.Integer, default=1)         # per player
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self) -> str:
        return f"<PropertyTemplate {self.name}>"


class Property(db.Model):
    """A property owned by a specific player."""
    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey("property_templates.id"), nullable=False)

    purchased_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    last_collected_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    income_collected = db.Column(db.BigInteger, default=0)  # lifetime total

    owner = db.relationship("Player", back_populates="properties")
    template = db.relationship("PropertyTemplate")

    @property
    def pending_income(self) -> int:
        """Calculate uncollected income since last collection."""
        hours = (now_utc() - self.last_collected_at).total_seconds() / 3600
        return int(hours * self.template.income_per_hour)

    def __repr__(self) -> str:
        return f"<Property {self.template.name} owner={self.owner_id}>"


# ═══════════════════════════════════════════════════════════════
# ITEMS
# ═══════════════════════════════════════════════════════════════

class Item(db.Model):
    """Item catalog — weapons, armor, consumables, vehicles."""
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    slug = db.Column(db.String(128), unique=True, nullable=False, index=True)
    category = db.Column(db.String(32), nullable=False)  # weapon, armor, vehicle, consumable
    rarity = db.Column(db.String(16), default="common")  # common, uncommon, rare, epic, legendary
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(512), nullable=True)

    # Shop
    buy_price = db.Column(db.BigInteger, nullable=True)   # null = not in shop
    sell_price = db.Column(db.BigInteger, nullable=True)
    is_tradeable = db.Column(db.Boolean, default=True)

    # Stat modifiers (applied when equipped)
    attack_bonus = db.Column(db.Integer, default=0)
    defense_bonus = db.Column(db.Integer, default=0)
    health_bonus = db.Column(db.Integer, default=0)       # max health increase
    energy_bonus = db.Column(db.Integer, default=0)
    stamina_bonus = db.Column(db.Integer, default=0)

    # Consumable effect
    is_consumable = db.Column(db.Boolean, default=False)
    health_restore = db.Column(db.Integer, default=0)
    energy_restore = db.Column(db.Integer, default=0)
    stamina_restore = db.Column(db.Integer, default=0)

    is_active = db.Column(db.Boolean, default=True)

    inventory_entries = db.relationship("PlayerItem", back_populates="item")

    def __repr__(self) -> str:
        return f"<Item {self.name} [{self.rarity}]>"


class PlayerItem(db.Model):
    """Junction table: item in a player's inventory."""
    __tablename__ = "player_items"

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    equipped = db.Column(db.Boolean, default=False)     # weapon/armor slots
    acquired_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    player = db.relationship("Player", back_populates="inventory")
    item = db.relationship("Item", back_populates="inventory_entries")

    __table_args__ = (
        db.UniqueConstraint("player_id", "item_id", name="uq_player_item"),
    )


# ═══════════════════════════════════════════════════════════════
# ATTACKS / COMBAT
# ═══════════════════════════════════════════════════════════════

class AttackLog(db.Model):
    """Every PvP attack attempt, win or lose."""
    __tablename__ = "attack_logs"

    id = db.Column(db.Integer, primary_key=True)
    attacker_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False, index=True)
    defender_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False, index=True)

    # Snapshot of power at time of fight
    attacker_power = db.Column(db.Integer, nullable=False)
    defender_power = db.Column(db.Integer, nullable=False)

    winner_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    cash_stolen = db.Column(db.BigInteger, default=0)
    xp_earned = db.Column(db.Integer, default=0)
    defender_hospitalized = db.Column(db.Boolean, default=False)

    attacked_at = db.Column(db.DateTime(timezone=True), default=now_utc, index=True)

    attacker = db.relationship("Player", foreign_keys=[attacker_id],
                                back_populates="attacks_sent")
    defender = db.relationship("Player", foreign_keys=[defender_id],
                                back_populates="attacks_received")
    winner = db.relationship("Player", foreign_keys=[winner_id])

    @property
    def attacker_won(self) -> bool:
        return self.winner_id == self.attacker_id


# ═══════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════

class Notification(db.Model):
    """In-game notifications (also pushed via SocketIO)."""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False, index=True)
    type = db.Column(db.String(32), nullable=False)  # attack, property, system, gang
    title = db.Column(db.String(128), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, index=True)
    link = db.Column(db.String(256), nullable=True)   # optional deep link

    player = db.relationship("Player")
