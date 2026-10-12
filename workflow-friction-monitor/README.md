# Workflow Friction Monitor

A full-stack workflow analytics demo with a **React + Vite frontend** and a **FastAPI backend**. It reuses the original project's weighted friction score, bottleneck ranking, and rule-based recommendations.

## Features

- Overview dashboard with task count, high-friction count, average friction, and bottleneck indicators.
- Workflow-stage friction chart and low/moderate/high risk distribution.
- Searchable, filterable bottleneck table with recommended actions.
- Task scoring form backed by the FastAPI `/api/score` endpoint.
- CSV import (validated before replacing the active dataset) and CSV export.
- Sample data generator for 30 projects × 7 workflow stages (210 synthetic rows).
- Interactive API documentation at `/docs` and health endpoint at `/health`.

## Project structure

```text
workflow-friction-monitor/
├── backend/
│   ├── app/main.py
│   ├── data/                  # sample CSV is created on first startup
│   ├── requirements.txt
│   ├── Procfile
│   └── render.yaml
├── frontend/
│   ├── src/main.jsx
│   ├── src/styles.css
│   ├── package.json
│   └── .env.example
├── .gitignore
└── README.md
```

## Run locally (Windows PowerShell)

Open two terminals in the project root.

### 1. Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Test `http://127.0.0.1:8000/health`. API docs: `http://127.0.0.1:8000/docs`.

### 2. Frontend

In a second terminal from the project root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open the local URL Vite prints (usually `http://localhost:5173`). `VITE_API_URL` defaults to `http://localhost:8000`.

## Dataset columns

CSV import requires these columns:

- `project_id`
- `task_id`
- `task_name`
- `planned_days`
- `actual_days`
- `response_delay`
- `rework_count`
- `dependency_count`
- `team_workload`

Optional columns such as `task_status` are retained in the uploaded CSV.

## Scoring logic

The existing project's weighted friction formula is retained:

- Delay score: 30%
- Response-delay score: 20%
- Rework score: 15%
- Dependency score: 15%
- Team-workload score: 20%

```text
friction_score =
    0.30 × delay_score
  + 0.20 × response_score
  + 0.15 × rework_score
  + 0.15 × dependency_score
  + 0.20 × team_workload
```

Friction level is `Low` below 30, `Moderate` from 30 to below 60, and `High` at 60 or above. Bottleneck ranking remains:

```text
bottleneck_score = 0.70 × friction_score
                 + 0.30 × dependency_count × 10
```

Recommendations use the original priority rules: response delay, rework, dependencies, workload, actual-vs-planned delay, then monitoring.

**Model transparency:** this version does not claim a trained model is producing validated predictions. It uses the project's deterministic scoring and rule-based recommendations. The included generated sample data is synthetic and should not be presented as real customer data or evidence of real-world model accuracy.

## Deploy

### Backend — Render

1. Push this repository to GitHub.
2. In Render, create a **New Web Service** and connect the repository.
3. Set **Root Directory** to `backend`.
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. After deployment, verify `/health` and `/docs`. Copy the deployed API base URL.

A `backend/render.yaml` is included as a starting point. For a public demo, configure `CORS_ORIGINS` to your deployed frontend origin rather than `*`.

### Frontend — Vercel

1. Import the same GitHub repository into Vercel.
2. Set **Root Directory** to `frontend`.
3. Add environment variable `VITE_API_URL` with the deployed backend base URL, for example `https://your-api.onrender.com`.
4. Deploy, then verify that the dashboard loads data and task scoring works.

The frontend is a static Vite app; the backend is a separate Python web service. Deploying one does not deploy the other.

## GitHub

From the project root:

```powershell
git init
git add .
git commit -m "Build Workflow Friction Monitor full stack"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Replace the URL with your own repository URL. Do not commit `.env`, `.venv`, or `node_modules`.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | API info |
| GET | `/health` | Health check |
| GET | `/api/summary` | Dashboard metrics |
| GET | `/api/tasks` | Ranked tasks, optional `level`, `search`, `limit` |
| POST | `/api/score` | Score one task |
| POST | `/api/upload-csv` | Validate and import CSV |
| POST | `/api/reset-sample` | Restore generated sample data |
