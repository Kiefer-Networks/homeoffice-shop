# Home Office Shop

Internal home office equipment shop for employees. Employees receive a configurable budget and can order equipment within their allowance. Admins manage the product catalog, review orders, and handle budget adjustments.

## Tech Stack

- **Frontend:** React 18, TypeScript, Vite, TailwindCSS, shadcn/ui, zustand
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.x (async), Alembic
- **Database:** PostgreSQL 16
- **Auth:** Google OAuth 2.0, JWT (Access + Refresh tokens)
- **Integrations:** HiBob (HRIS), Icecat Open Catalog (product data)
- **Notifications:** SMTP email + Slack webhooks

## Quick Start

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials

# Start all services
docker compose up --build
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Production Deployment

### Reverse Proxy

Place nginx or Caddy in front of backend + frontend for:
- TLS termination (Let's Encrypt)
- HTTP/2
- Static file serving for uploaded images
- Rate limiting at edge

### Environment

- Generate secrets: `openssl rand -hex 32` for JWT_SECRET_KEY and SECRET_KEY
- Set CORS_ALLOWED_ORIGINS to production domain
- Set BACKEND_URL and FRONTEND_URL to production URLs
- Configure SMTP for production mail server

### Database

- Use managed PostgreSQL (e.g., Cloud SQL, RDS) for production
- Enable automated backups
- The included postgresql.conf is tuned for Docker dev; adjust for production hardware

### Uploads

- Mount a persistent volume or object storage (S3-compatible) for /app/uploads
- Configure backup for upload volume

### Monitoring

- GET /api/health for uptime monitoring
- pg_stat_statements for query analysis
- Structured logs (JSON) for log aggregation
