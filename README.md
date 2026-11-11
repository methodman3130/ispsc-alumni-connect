# ISPSC Alumni Connect

A responsive alumni community platform for finding classmates, seeing where graduates are working, and keeping alumni records current.

## Stack
- **Frontend:** React 18, Vite, Tailwind CSS, Lucide icons
- **Backend:** FastAPI, SQLAlchemy, PostgreSQL / Neon
- **Deployment:** GitHub, Vercel, Neon

## Run locally

```bash
npm install
npm run dev
```

For the API, create `api/.env` from `api/.env.example`, then:

```bash
cd api
python -m venv .venv
source .venv/bin/activate # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Set `VITE_API_URL=http://localhost:8000/api` in `.env.local` for local development.

## Deploy

1. Create a PostgreSQL database in Neon and add its connection string as `DATABASE_URL` in Vercel.
2. Add a long random `JWT_SECRET` environment variable.
3. Import this repository in Vercel. The included `vercel.json` exposes FastAPI under `/api` and builds the React app.
4. For a separate frontend deployment, set `VITE_API_URL` to your published API URL.

The first backend request automatically creates the database tables. For production teams, use Alembic migrations before launch.

## Access control

Registration and sign-in use the FastAPI service. The alumni directory is populated from the database for authenticated users; it is not a static demo list. An administrator account can be created by updating a user's role in the database to `admin`.

## Sample accounts

For development, run `python api/seed.py` after configuring `DATABASE_URL`. This creates one administrator and four graduate accounts, all with the temporary password `ChangeMe2026!`. See [DEPLOYMENT.md](DEPLOYMENT.md) for the full GitHub, Neon, and Vercel deployment guide.
