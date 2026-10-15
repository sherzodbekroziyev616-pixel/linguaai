# LinguaAI

LinguaAI is a full-stack AI translation workspace built with React + TypeScript on the frontend and FastAPI + SQLAlchemy on the backend.

## Stack

- Frontend: React, TypeScript, Vite, React Router
- Backend: FastAPI, SQLAlchemy, Pydantic, Alembic
- Database: SQLite for local development, PostgreSQL-ready configuration
- AI: Google Gemini via the official Google GenAI SDK

## Quick start

### 1) Backend

```powershell
cd Backend_2
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

### 2) Frontend

```powershell
cd Backend_2\frontend
npm install
npm run dev
```

### Single-service Render deployment

The root `render.yaml` provisions the web service and PostgreSQL database. Render builds `frontend/dist` and the FastAPI app serves the SPA, assets, and API from one origin.

1. Push the repository to a Git provider and create a Render Blueprint from it.
2. Set the unsynchronized `GEMINI_API_KEY` environment variable if Gemini is enabled. The translation fallback remains available when the key/provider is unavailable.
3. Deploy. The Render service uses `/api/health` as its health check.

For local production-serving verification, run `bash build.sh` from the repository root, then start Uvicorn from the repository root. Configure `VITE_API_BASE_URL` only when the API is intentionally hosted on a separate origin.

### 3) Environment configuration

Copy `.env.example` to `backend\.env` and set `GEMINI_API_KEY` to a valid Google AI API key.

```powershell
Copy-Item .env.example backend\.env
```

The backend loads settings from `backend\.env` with `python-dotenv`. Gemini uses the configured `GEMINI_MODEL`; AQ-prefixed Vertex AI Express keys use the Vertex AI Express `generateContent` endpoint with a `gemini-2.0-flash` retry if the configured model returns 404. If Gemini is unavailable, translation uses Google Translate and explanations provide a structured Uzbek analysis.

## Features

- Uzbek-first UI in Latin script
- Translation between Uzbek, English, Korean, and Turkish
- Auth flows with JWT and local SQLite persistence
- Translation history and favorites
- Theme switching with saved preference
- AI assistant endpoint
- Automated API tests

## Available routes

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Gemini translation: `POST /api/v1/translations`
- Uzbek explanation: `POST /api/v1/translations/explain`
- Registration: `POST /api/v1/auth/register`
- Login: `POST /api/v1/auth/login`
- One-time recovery reset: `POST /api/v1/auth/reset-password`

## Testing

```powershell
cd Backend_2
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
npm run test -- --run
```

## Notes

- The default database is SQLite for local use.
- PostgreSQL support is configured in code for production deployments.
- Translation supports Uzbek, English, Korean, and Turkish, automatic source detection, and Oddiy, Rasmiy, and Professional styles.
- Explanations are returned in Uzbek Latin script.
- Gemini translation is attempted first; on provider errors 403, 404, 429, or 503, translation falls back to Google Translate and the explanation uses a local Uzbek style guide.
- The assistant offers word/grammar analysis, style comparison, pronunciation, alternatives, and free questions, and can load the latest translation.
- Registration and password recovery use nickname/password and a one-time `LNG-XXXX-XXXX` recovery code. Only a hash is stored; each successful reset rotates the code.
- Startup creates missing tables and safely adds missing mapped columns to existing tables.
- Production hosting may set `FRONTEND_ORIGIN`; CORS also permits HTTPS origins on `*.onrender.com` and `*.vercel.app`.
