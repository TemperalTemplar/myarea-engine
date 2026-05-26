from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.auth.routes import auth_bp
from app import db


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("game.dashboard"))

    if request.method == "POST":
        from app.models import User
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "")
        remember   = bool(request.form.get("remember"))

        user = (User.query.filter_by(username=identifier).first() or
                User.query.filter_by(email=identifier).first())

        if user and user.check_password(password):
            if user.is_banned:
                flash("Your account has been suspended.", "danger")
                return redirect(url_for("auth.login"))
            from datetime import datetime, timezone
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user, remember=remember)
            return redirect(request.args.get("next") or url_for("game.dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("game.dashboard"))

    if request.method == "POST":
        from app.models import User, Player
        from slugify import slugify

        username  = request.form.get("username", "").strip()
        email     = request.form.get("email", "").strip().lower()
        password  = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        errors = []
        if len(username) < 3 or len(username) > 32:
            errors.append("Username must be 3–32 characters.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != password2:
            errors.append("Passwords do not match.")
        if User.query.filter_by(username=username).first():
            errors.append("Username already taken.")
        if User.query.filter_by(email=email).first():
            errors.append("Email already registered.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", username=username, email=email)

        from flask import current_app
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        player = Player(
            user_id=user.id,
            slug=slugify(username),
            display_name=username,
            cash=current_app.config["NEW_PLAYER_CASH"],
            energy=current_app.config["NEW_PLAYER_ENERGY"],
            stamina=current_app.config["NEW_PLAYER_STAMINA"],
            health=current_app.config["NEW_PLAYER_HEALTH"],
        )
        db.session.add(player)
        db.session.commit()
        login_user(user)
        flash(f"Welcome to MyArea, {username}! Your criminal career begins now.", "success")
        return redirect(url_for("game.dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/oidc/login")
def oidc_login():
    from flask import current_app
    from app import oauth
    if not current_app.config.get("OIDC_CLIENT_ID"):
        flash("SSO is not configured.", "warning")
        return redirect(url_for("auth.login"))
    import os
    redirect_uri = os.getenv('OIDC_REDIRECT_URI', 'https://crimewars.wrds361.com/auth/oidc/callback')
    return oauth.authentik.authorize_redirect(redirect_uri)


@auth_bp.route("/oidc/callback")
def oidc_callback():
    from flask import current_app
    from app import oauth, db
    from app.models import User, Player
    from slugify import slugify
    try:
        token    = oauth.authentik.authorize_access_token()
        userinfo = token.get("userinfo") or oauth.authentik.userinfo()
    except Exception:
        flash("SSO login failed. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    sub      = userinfo["sub"]
    email    = userinfo.get("email", "")
    username = userinfo.get("preferred_username", sub[:32])

    user = User.query.filter_by(oidc_sub=sub).first()
    if not user:
        user = User.query.filter_by(email=email).first()
        if user:
            user.oidc_sub = sub
        else:
            safe_username = username[:32].replace(" ", "_")
            n = 1
            base = safe_username
            while User.query.filter_by(username=safe_username).first():
                safe_username = f"{base}{n}"
                n += 1
            user = User(username=safe_username, email=email, oidc_sub=sub)
            db.session.add(user)
            db.session.flush()
            player = Player(
                user_id=user.id,
                slug=slugify(safe_username),
                display_name=userinfo.get("name", safe_username),
                cash=current_app.config["NEW_PLAYER_CASH"],
                energy=current_app.config["NEW_PLAYER_ENERGY"],
                stamina=current_app.config["NEW_PLAYER_STAMINA"],
                health=current_app.config["NEW_PLAYER_HEALTH"],
            )
            db.session.add(player)

    from datetime import datetime, timezone
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    if user.is_banned:
        flash("Your account has been suspended.", "danger")
        return redirect(url_for("auth.login"))

    login_user(user, remember=True)
    return redirect(url_for("game.dashboard"))
