# AM Lightspeed VT

Full-stack app with **FastAPI** (backend), **Vue.js + Tailwind CSS** (frontend), and **PostgreSQL**, all containerized with Docker and health checks.

## Stack

- **Backend**: FastAPI (Python 3.12), Uvicorn
- **Frontend**: Vue 3, Vite, Tailwind CSS, Nginx (production)
- **Database**: PostgreSQL 16
- **Orchestration**: Docker Compose, Makefile

## Prerequisites

- Docker and Docker Compose
- Make

## Quick start

```bash
# Build and start all services
make up-build

# Check status and health
make ps
make health
```

- **Frontend**: http://localhost (port 80)
- **Backend API**: http://localhost:8001
- **API docs**: http://localhost:8001/docs
- **PostgreSQL**: localhost:5432 (user `app`, password `appsecret`, database `appdb`)

## Development vs production

- **Development**: `make dev` (DB only, run backend/frontend on host with hot reload) or `make up-dev` (full stack with backend hot reload). Use `make clean` / `make down-volumes` only locally.
- **Production**: Copy `.env.example` to `.env.prod`, set real secrets and optional `DOCKER_REGISTRY`. Then `make prod-up` (or `make deploy`). Use `make build-push` to build and push images when `DOCKER_REGISTRY` is set in `.env.prod`. Never commit `.env.prod`.

## Makefile targets

| Command | Description |
|---------|-------------|
| `make help` | Show all targets (default) |
| **Development** | |
| `make dev` | Start only DB (run backend/frontend locally) |
| `make up-dev` | Full stack with backend hot reload |
| `make up-dev-build` | Same as up-dev, rebuild images |
| `make build` | Build all images |
| `make up` | Start all containers (default compose) |
| `make up-build` | Build and start |
| `make down` | Stop and remove containers |
| `make down-volumes` | Down and remove volumes (dev only) |
| `make restart` | Restart all containers |
| **Production** | |
| `make prod-up` | Start with prod overrides (needs .env.prod) |
| `make prod-down` | Stop prod stack |
| `make build-push` | Build and push images (DOCKER_REGISTRY in .env.prod) |
| `make deploy` | Alias for prod-up |
| **Common** | |
| `make logs` | Follow all logs |
| `make logs-backend` | Backend logs only (and logs-frontend, logs-db) |
| `make ps` | Container status |
| `make health` | Run health checks (curl + pg_isready) |
| `make shell-backend` | Shell in backend container |
| `make shell-frontend` | Shell in frontend container |
| `make shell-db` | `psql` in database |
| `make clean` | Remove containers, volumes, images (dev only) |

## Health checks

Each service has a health check:

- **Backend**: `GET /health` (200 = healthy)
- **Frontend**: `GET /health` (Nginx returns 200)
- **PostgreSQL**: `pg_isready -U app -d appdb`

Compose waits for the database to be healthy before starting the backend. Use `make health` to run checks from the host (requires `curl` for HTTP).

## Project layout

```
.
├── backend/           # FastAPI app
│   ├── app/
│   │   ├── api/
│   │   │   └── health.py
│   │   ├── config.py   # env: DATABASE_URL, HOST, PORT
│   │   └── main.py
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/          # Vue + Vite + Tailwind
│   ├── src/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── docker-compose.yml
├── docker-compose.dev.yml   # Dev overrides (backend hot reload)
├── docker-compose.prod.yml  # Prod overrides (restart, registry image names)
├── .env.example             # Template for .env.prod
├── Makefile
└── README.md
```

## Local development (without Docker)

**Backend**

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

**Database**: Run PostgreSQL in a container with `make dev`, then point the backend at `localhost:5432`.

## Environment

All config is driven by environment variables. See `.env.example` at the repo root.

- **Compose**: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`; optional port overrides `BACKEND_PORT`, `FRONTEND_PORT`, `POSTGRES_PORT`. Defaults work without a `.env`; copy `.env.example` to `.env` to override.
- **Backend**: Reads `DATABASE_URL`, `HOST`, `PORT` (see `backend/app/config.py`). Set in compose or when running locally.
- **Frontend dev**: Optional `VITE_DEV_PORT`, `VITE_API_TARGET` when running `npm run dev`.
- **Production**: Copy `.env.example` to `.env.prod`, set real secrets and optional `DOCKER_REGISTRY` / `IMAGE_TAG`. Never commit `.env.prod`.
