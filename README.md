# EVE Station Trader

Greenfield trading analysis platform for EVE Online regional and structure hauling workflows. The app is designed as a modular monolith with a separate React frontend, FastAPI backend, APScheduler worker, PostgreSQL persistence, and query-ready derived tables for the `/trade` experience.

## Architecture

- `frontend/`: React + TypeScript + Vite UI with dense trading tables and operational pages.
- `backend/`: FastAPI API, SQLAlchemy models, Alembic migrations, domain formulas, sync services, and background worker code.
- `docker-compose.yml`: local development stack with PostgreSQL, Redis, backend, worker, and frontend.

## Current scaffold status

- Runnable page shells for `/trade`, `/sync`, `/characters`, and `/settings`
- API route stubs for targets, opportunities, sync, characters, auth, and settings
- SQLAlchemy models covering the initial schema surface
- Alembic initial migration
- Seeded tracked structure mechanism
- Mock-friendly service layer for Adam4EVE and ESI
- Initial backend formula, aggregation, sync, and API tests
- Initial frontend page and trade component tests

## Local development

### Docker

```bash
docker compose up --build
```

Services:

- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend API: [http://localhost:8000](http://localhost:8000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Backend without Docker

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
alembic upgrade head
uvicorn main:app --reload
```

### Frontend without Docker

```bash
cd frontend
npm install
npm run dev
```

## Environment

Backend uses the following environment variables:

- `DATABASE_URL`
- `REDIS_URL`
- `APP_ENV`
- `ESI_CLIENT_ID`
- `ESI_CLIENT_SECRET`
- `ESI_CALLBACK_URL`
- `FRONTEND_URL`
- `ESI_COMPATIBILITY_DATE`
- `A4E_USER_AGENT`

Real EVE SSO is scaffolded, but external clients stay mock-friendly for local development and tests until the live integration phase is filled out.

## Migrations

```bash
cd backend
alembic upgrade head
```

## Testing

### Backend

```bash
cd backend
pytest
```

### Frontend

```bash
cd frontend
npm test
```

## Notes

- Business formulas live in the domain layer and are unit-tested first.
- Heavy opportunity computation is designed to run in worker/services, not in request handlers.
- TODO markers only remain where live SSO/ESI/Adam4EVE integration details still need implementation.
