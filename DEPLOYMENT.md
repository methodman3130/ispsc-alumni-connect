# Deployment guide

This project deploys as one Vercel application: the Vite site is served from `dist`, and the FastAPI service is available at `/api`. The browser calls the same origin, so no database credential is ever exposed to users.

## 1. Publish the repository to GitHub

Create a **private** GitHub repository named `ispsc-alumni-connect` under `methodman3130`. Do not ask GitHub to create a README or `.gitignore`.

From the project directory, run:

```powershell
git add -A
git commit -m "Prepare ISPSC Alumni Connect for deployment"
git branch -M main
git remote add origin https://github.com/methodman3130/ispsc-alumni-connect.git
git push -u origin main
```

GitHub Actions will run the checked-in verification workflow for every pull request and push to `main`.

## 2. Provision Neon

In the Neon organization, create a project named `ispsc-alumni-connect` in the nearest available region. Use the default production branch, then create a child branch named `preview`.

For each branch, copy the **pooled** connection string from **Connect**. Change the scheme from `postgresql://` to `postgresql+psycopg://`, preserving `?sslmode=require`.

Use the production URL only for Vercel Production. Use the preview-branch URL only for Vercel Preview deployments.

## 3. Configure Vercel

In the `vitruvius-john-barayugas-projects` Vercel team, import `methodman3130/ispsc-alumni-connect`. Keep the detected Vite settings:

- Build command: `npm run build`
- Output directory: `dist`

Create these variables. Mark database URLs and secrets as **Secret** values.

| Variable | Production | Preview |
| --- | --- | --- |
| `DATABASE_URL` | Neon production pooled URL | Neon `preview` branch pooled URL |
| `JWT_SECRET` | unique 32+ character random value | a different random value |
| `FRONTEND_ORIGIN` | production Vercel URL | optional |
| `ENVIRONMENT` | `production` | `preview` |
| `VITE_API_URL` | `/api` | `/api` |

Generate each `JWT_SECRET` locally and paste it directly into Vercel; never commit or share it:

```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
```

Deploy a preview first. Confirm the following endpoint responds with `{"status":"ok"}`:

```text
https://YOUR-PREVIEW-URL/api/health
```

Test registration, sign-in, and the directory before merging to `main`. A push to `main` creates the production deployment.

## 4. Optional sample data

Only for a non-public test database, create `api/.env` from `api/.env.example`, insert that branch's database URL, then run:

```powershell
.\.venv\Scripts\python.exe api\seed.py
```

The seed accounts use known temporary passwords. Do not seed a public production database unless you immediately replace or remove those accounts.

## Launch checklist

- GitHub repository is private and Actions passes.
- Vercel Preview and Production have separate Neon URLs.
- `JWT_SECRET` values are unique and never committed.
- `/api/health`, registration, sign-in, and directory search work in Preview.
- Sample users are removed or their passwords are changed before public launch.
- Add email verification, password reset, privacy notice, and managed schema migrations before opening public registration.
