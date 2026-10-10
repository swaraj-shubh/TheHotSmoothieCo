# The Hot Smoothie Co.

E-commerce platform for posters, prints, stickers and framed art.

| Part | Where | Status |
|---|---|---|
| Backend API + worker (FastAPI, Postgres, Redis) | [`backend/`](backend/README.md) | ready for staging |
| Storefront + admin (Next.js) | [`frontend/`](frontend/README.md) | ready for staging |

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md): system design, modules, critical flows, decisions, AWS path
- [API.md](docs/API.md): conventions (auth, errors, pagination, idempotency, rate limits) and every endpoint
- [DATABASE.md](docs/DATABASE.md): schema, indexes, migrations, backups and restore
- [DEPLOYMENT.md](docs/DEPLOYMENT.md): Render/Neon/Upstash/Cloudflare setup, release flow, rollback, operations
- [SECURITY.md](docs/SECURITY.md): threat model, controls, roles, go-live checklist
- [ENVIRONMENT.md](docs/ENVIRONMENT.md): every configuration variable

## Quick start

```bash
cd backend
cp .env.example .env
docker compose up --build            # Postgres, Redis, migrations, API on :8000, worker
docker compose exec api python -m scripts.seed_demo      # demo catalog
docker compose exec api python -m scripts.create_admin you@example.com "Your Name"
open http://localhost:8000/docs

cd ../frontend && cp .env.example .env.local && npm ci && npm run dev   # http://localhost:3000
```
# TheHotSmoothieCo
