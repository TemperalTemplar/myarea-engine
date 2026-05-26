# MyArea Engine

The game engine powering Crime Wars and all future MyArea games. Built on Flask — copy this repo to create any new game.

## Features
- Jobs/crimes system with energy costs, success rates, jail
- PvP attacks with stamina, cash stealing, hospitalization
- Properties with passive income
- Items shop — weapons, armor, vehicles, consumables
- Gang system — create, join, territory, gang bank
- Level/XP system with 200 levels
- Energy and stamina regeneration (Celery background tasks)
- Real-time notifications via SocketIO
- Full admin panel with CRUD for jobs, properties, items
- SSO via Authentik OIDC
- Service API for cross-app communication with MyArea Social

## Requirements
- Docker
- Docker Compose
- The `myarea_shared_net` Docker network

## Quick Install

### Fresh server deployment
Use the master deploy script:
```bash
chmod +x deploy_myarea_v2.sh
./deploy_myarea_v2.sh
```

### Manual install
```bash
# 1. Clone the repo
git clone git@github.com:TemperalTemplar/myarea-engine.git
cd myarea-engine

# 2. Copy and fill in environment file
cp .env.example .env
nano .env

# 3. Create shared network if needed
docker network create myarea_shared_net

# 4. Build and start
docker compose up -d --build

# 5. Create tables
docker compose exec web python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
"

# 6. Stamp migrations
docker compose exec web flask db init
docker compose exec web flask db stamp head

# 7. Seed game data (jobs, properties, items)
docker compose exec web flask seed-db

# 8. Create admin
docker compose exec web python -c "
from app import create_app, db
from app.models import User, Player
from slugify import slugify
app = create_app()
with app.app_context():
    u = User(username='admin', email='admin@yourdomain.com', is_admin=True)
    u.set_password('yourpassword')
    db.session.add(u)
    db.session.flush()
    p = Player(user_id=u.id, slug='admin', display_name='Admin',
               cash=5000, energy=50, stamina=25, health=100)
    db.session.add(p)
    db.session.commit()
"

# 9. Connect to shared network
docker network connect myarea_shared_net myarea_games_web
docker network connect myarea_shared_net myarea_games_celery

# 10. Restart nginx
docker compose restart nginx
```

## Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask secret key |
| `POSTGRES_PASSWORD` | Database password |
| `REDIS_PASSWORD` | Redis password |
| `SERVICE_API_KEY` | Shared key with social app — must match |
| `SOCIAL_APP_URL` | Internal URL of social app container |
| `OIDC_CLIENT_ID` | Authentik client ID |
| `OIDC_CLIENT_SECRET` | Authentik client secret |
| `OIDC_DISCOVERY_URL` | Authentik discovery URL |
| `OIDC_REDIRECT_URI` | `https://yourdomain.com/auth/oidc/callback` |
| `HTTP_PORT` | Host port (default 8921) |
| `ENERGY_REGEN_SECONDS` | Seconds per energy point (default 300) |
| `STAMINA_REGEN_SECONDS` | Seconds per stamina point (default 180) |

## Spinning up a new game
Use `new_game.sh` from the myarea-scripts repo. It copies this engine, renames all containers, applies a theme color, and deploys automatically:
```bash
./new_game.sh
```

## Admin Panel
`https://yourdomain.com/admin`

- **Players** — view stats, edit cash/level/health, ban/unban
- **Gangs** — view all gangs, delete
- **Jobs** — create, edit, enable/disable, delete
- **Properties** — create, edit, enable/disable, delete
- **Items** — create, edit, enable/disable, delete
- **Notify All** — broadcast notification to all players

## After `docker compose down`
```bash
docker compose up -d
docker network connect myarea_shared_net myarea_games_web
docker compose restart nginx
```

## Ports
- Default port: `8921`
- Change with `HTTP_PORT=` in `.env`
