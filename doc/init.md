## Backend

All commands run from the `Backend/` directory. The FastAPI app lives in `app/main.py`;
`main.py` re-exports it, so either module path below starts the same server.

### One-time setup

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

(Windows: `.venv\Scripts\activate`, then `pip install -r requirements.txt`.)

### Database

The default `database_url` in `app/config.py` points at PostgreSQL. If Postgres isn't
running, use SQLite instead — set this in the **same shell** you start uvicorn from, or every
auth/template route returns a bare `500`:

```bash
export FLUX_DATABASE_URL="sqlite+aiosqlite:///./flux_dev.db"
.venv/bin/alembic upgrade head
```

This creates `flux_dev.db` (already in `.gitignore`). To reset it, delete the file and run
`alembic upgrade head` again. For PostgreSQL, create the database and point
`FLUX_DATABASE_URL` at it instead — the same migration works on both dialects.

### Start the server

```bash
.venv/bin/uvicorn app.main:app --reload
```

- API browser: http://localhost:8000/docs
- The frontend expects port 8000 (`Frontend/src/api/executionApi.js`); override with
  `VITE_API_BASE_URL`.
- CORS is restricted to `http://localhost:5173` in development (`app/config.py`).

### Run the tests

```bash
.venv/bin/python -m pytest
```

### Deactivate the virtual environment

```bash
deactivate
```

## Frontend

```bash
cd Frontend
npm install
npm run dev
```
