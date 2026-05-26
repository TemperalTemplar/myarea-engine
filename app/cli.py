"""
Flask CLI commands for MyArea.
Usage: flask <command>
"""

import click
from flask import Flask


def register_commands(app: Flask) -> None:

    @app.cli.command("seed-db")
    @click.option("--reset", is_flag=True, help="Drop and recreate all tables first")
    def seed_db(reset):
        """Seed the database with job templates, property templates, and items."""
        from app import db
        from app.models import JobTemplate, PropertyTemplate, Item
        from slugify import slugify

        if reset:
            click.echo("⚠️  Dropping all tables...")
            db.drop_all()
            db.create_all()
            click.echo("✅ Tables recreated.")

        click.echo("🌱 Seeding job templates...")
        _seed_jobs(db, JobTemplate)

        click.echo("🌱 Seeding property templates...")
        _seed_properties(db, PropertyTemplate)

        click.echo("🌱 Seeding items...")
        _seed_items(db, Item, slugify)

        db.session.commit()
        click.echo("✅ Database seeded successfully.")

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.argument("email")
    @click.option("--password", prompt=True, hide_input=True,
                  confirmation_prompt=True)
    def create_admin(username, email, password):
        """Create an admin user."""
        from app import db
        from app.models import User, Player
        from slugify import slugify

        user = User(username=username, email=email, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        player = Player(
            user_id=user.id,
            slug=slugify(username),
            display_name=username,
            cash=app.config["NEW_PLAYER_CASH"],
            energy=app.config["NEW_PLAYER_ENERGY"],
            stamina=app.config["NEW_PLAYER_STAMINA"],
        )
        db.session.add(player)
        db.session.commit()
        click.echo(f"✅ Admin user '{username}' created.")

    @app.cli.command("gen-fake-players")
    @click.option("--count", default=20, help="Number of fake players to generate")
    def gen_fake_players(count):
        """Generate fake players for development/testing."""
        from app import db
        from app.models import User, Player
        from faker import Faker
        from slugify import slugify
        import random

        fake = Faker()
        created = 0

        for _ in range(count):
            username = fake.user_name()[:32]
            if User.query.filter_by(username=username).first():
                continue

            user = User(
                username=username,
                email=fake.email(),
                is_admin=False,
            )
            user.set_password("testpass123")
            db.session.add(user)
            db.session.flush()

            player = Player(
                user_id=user.id,
                slug=slugify(username),
                display_name=username,
                level=random.randint(1, 50),
                experience=random.randint(0, 500_000),
                cash=random.randint(1_000, 1_000_000),
                fights_won=random.randint(0, 500),
                fights_lost=random.randint(0, 200),
                attack_power=random.randint(10, 200),
                defense_power=random.randint(10, 200),
            )
            db.session.add(player)
            created += 1

        db.session.commit()
        click.echo(f"✅ Created {created} fake players.")


# ─── Seed data helpers ────────────────────────────────────────

def _seed_jobs(db, JobTemplate):
    jobs = [
        dict(name="Pickpocket", category="crime", energy_cost=2,
             cash_min=50, cash_max=200, xp_reward=5, crime_points=1,
             base_success_rate=0.90, jail_time_seconds=60),
        dict(name="Mug a Tourist", category="crime", energy_cost=3,
             cash_min=100, cash_max=400, xp_reward=8, crime_points=2,
             base_success_rate=0.80, jail_time_seconds=120),
        dict(name="Break and Enter", category="crime", energy_cost=5,
             cash_min=300, cash_max=1000, xp_reward=15, crime_points=5,
             base_success_rate=0.70, jail_time_seconds=300, min_level=3),
        dict(name="Car Theft", category="crime", energy_cost=8,
             cash_min=500, cash_max=2000, xp_reward=25, crime_points=8,
             base_success_rate=0.65, jail_time_seconds=600, min_level=5),
        dict(name="Bank Robbery", category="heist", energy_cost=20,
             cash_min=5000, cash_max=20000, xp_reward=100, crime_points=25,
             base_success_rate=0.45, jail_time_seconds=1800, min_level=15),
        dict(name="Drug Deal", category="hustle", energy_cost=4,
             cash_min=200, cash_max=800, xp_reward=12, crime_points=4,
             base_success_rate=0.75, jail_time_seconds=240, min_level=2),
        dict(name="Arms Dealing", category="hustle", energy_cost=10,
             cash_min=1000, cash_max=5000, xp_reward=40, crime_points=15,
             base_success_rate=0.60, jail_time_seconds=900, min_level=10),
    ]
    for j in jobs:
        if not JobTemplate.query.filter_by(name=j["name"]).first():
            db.session.add(JobTemplate(**j))


def _seed_properties(db, PropertyTemplate):
    props = [
        dict(name="Crack House", category="criminal", purchase_price=10_000,
             sell_price=7_000, income_per_hour=150, min_level=1),
        dict(name="Pawn Shop", category="business", purchase_price=25_000,
             sell_price=18_000, income_per_hour=400, min_level=5),
        dict(name="Strip Club", category="business", purchase_price=75_000,
             sell_price=55_000, income_per_hour=1200, min_level=10),
        dict(name="Casino", category="business", purchase_price=500_000,
             sell_price=375_000, income_per_hour=8000, min_level=25),
        dict(name="Safehouse", category="residential", purchase_price=50_000,
             sell_price=35_000, income_per_hour=0, defense_bonus=20, min_level=8),
        dict(name="Armory", category="criminal", purchase_price=150_000,
             sell_price=100_000, income_per_hour=500, attack_bonus=15, min_level=15),
    ]
    for p in props:
        if not PropertyTemplate.query.filter_by(name=p["name"]).first():
            db.session.add(PropertyTemplate(**p))


def _seed_items(db, Item, slugify):
    items = [
        # Weapons
        dict(name="Brass Knuckles", category="weapon", rarity="common",
             buy_price=500, sell_price=250, attack_bonus=5),
        dict(name="Baseball Bat", category="weapon", rarity="common",
             buy_price=1000, sell_price=500, attack_bonus=10),
        dict(name="Switchblade", category="weapon", rarity="uncommon",
             buy_price=2500, sell_price=1200, attack_bonus=18),
        dict(name="Desert Eagle", category="weapon", rarity="rare",
             buy_price=15000, sell_price=7500, attack_bonus=45),
        dict(name="AK-47", category="weapon", rarity="epic",
             buy_price=50000, sell_price=25000, attack_bonus=90),
        # Armor
        dict(name="Leather Jacket", category="armor", rarity="common",
             buy_price=800, sell_price=400, defense_bonus=8),
        dict(name="Kevlar Vest", category="armor", rarity="uncommon",
             buy_price=5000, sell_price=2500, defense_bonus=25),
        dict(name="Full Body Armor", category="armor", rarity="rare",
             buy_price=20000, sell_price=10000, defense_bonus=60),
        # Consumables
        dict(name="First Aid Kit", category="consumable", rarity="common",
             buy_price=500, sell_price=200, is_consumable=True, health_restore=30),
        dict(name="Adrenaline Shot", category="consumable", rarity="uncommon",
             buy_price=2000, sell_price=1000, is_consumable=True,
             energy_restore=20, stamina_restore=10),
        # Vehicles
        dict(name="Stolen Sedan", category="vehicle", rarity="common",
             buy_price=5000, sell_price=2500, defense_bonus=5, attack_bonus=3),
        dict(name="Armored SUV", category="vehicle", rarity="rare",
             buy_price=80000, sell_price=40000, defense_bonus=30, attack_bonus=10),
    ]
    for i in items:
        slug = slugify(i["name"])
        if not Item.query.filter_by(slug=slug).first():
            db.session.add(Item(slug=slug, **i))
