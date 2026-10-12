from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_PATH = DATA_DIR / "customer_onboarding.csv"

TASK_NAMES = [
    "Requirement Collection", "API Integration", "Data Migration",
    "Configuration", "Testing", "Customer Approval", "Deployment"
]
REQUIRED_COLUMNS = [
    "project_id", "task_id", "task_name", "planned_days", "actual_days",
    "response_delay", "rework_count", "dependency_count", "team_workload"
]

app = FastAPI(
    title="Workflow Friction Monitor API",
    description="Scores workflow friction, ranks bottlenecks, and recommends practical actions.",
    version="1.0.0",
)

origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if origins == ["*"] else origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskInput(BaseModel):
    project_id: str = Field(default="P001", max_length=40)
    task_id: str = Field(default="T001", max_length=40)
    task_name: str = Field(default="Requirement Collection", max_length=120)
    planned_days: float = Field(ge=1, le=3650)
    actual_days: float = Field(ge=1, le=3650)
    response_delay: float = Field(ge=0, le=100)
    rework_count: int = Field(ge=0, le=100)
    dependency_count: int = Field(ge=0, le=100)
    team_workload: float = Field(ge=0, le=100)


def score_records(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the project's original weighted friction and bottleneck formulas."""
    df = frame.copy()
    for col in ["planned_days", "actual_days", "response_delay", "rework_count",
                "dependency_count", "team_workload"]:
        df[col] = pd.to_numeric(df[col], errors="raise")
    if (df["planned_days"] <= 0).any():
        raise ValueError("planned_days must be greater than zero.")
    if ((df["team_workload"] < 0) | (df["team_workload"] > 100)).any():
        raise ValueError("team_workload must be between 0 and 100.")

    df["delay_days"] = (df["actual_days"] - df["planned_days"]).clip(lower=0)
    df["delay_score"] = (df["delay_days"] / df["planned_days"] * 100).clip(upper=100)
    response_score = (df["response_delay"] / 4 * 100).clip(upper=100)
    rework_score = (df["rework_count"] / 3 * 100).clip(upper=100)
    dependency_score = (df["dependency_count"] / 3 * 100).clip(upper=100)
    workload_score = df["team_workload"]

    df["friction_score"] = (
        0.30 * df["delay_score"] + 0.20 * response_score
        + 0.15 * rework_score + 0.15 * dependency_score
        + 0.20 * workload_score
    ).round(2)
    df["friction_level"] = df["friction_score"].apply(
        lambda score: "Low" if score < 30 else ("Moderate" if score < 60 else "High")
    )
    df["bottleneck_score"] = (
        df["friction_score"] * 0.7 + df["dependency_count"] * 10 * 0.3
    ).round(2)
    df["recommended_action"] = df.apply(recommend_action, axis=1)
    return df.sort_values("bottleneck_score", ascending=False).reset_index(drop=True)


def recommend_action(row: pd.Series) -> str:
    # Priority order retained from the original recommend_action.py
    if row["response_delay"] >= 3:
        return "Send a customer reminder or escalate the pending response."
    if row["rework_count"] >= 2:
        return "Review task requirements and assign an experienced team member."
    if row["dependency_count"] >= 2:
        return "Prioritize the blocking dependency and coordinate with the dependent team."
    if row["team_workload"] >= 85:
        return "Redistribute workload or reassign the task."
    if row["actual_days"] > row["planned_days"]:
        return "Review task progress and investigate the cause of delay."
    return "Continue monitoring the task."


def generate_sample_data() -> pd.DataFrame:
    # Deterministic sample data: same ranges and 30 projects x 7 workflow stages as source.
    import random
    rng = random.Random(42)
    rows: list[dict[str, Any]] = []
    for p in range(1, 31):
        for idx, name in enumerate(TASK_NAMES, start=1):
            planned = rng.randint(2, 6)
            actual = max(planned + rng.randint(-1, 4), 1)
            if actual > planned + 1:
                status = "Delayed"
            elif actual == planned:
                status = "Completed"
            else:
                status = "In Progress"
            rows.append({
                "project_id": f"P{p:03d}", "task_id": f"T{idx:03d}",
                "task_name": name, "planned_days": planned, "actual_days": actual,
                "response_delay": rng.randint(0, 4), "rework_count": rng.randint(0, 3),
                "dependency_count": rng.randint(0, 3), "team_workload": rng.randint(40, 100),
                "task_status": status,
            })
    return pd.DataFrame(rows)


def read_source_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        generate_sample_data().to_csv(DATA_PATH, index=False)
    frame = pd.read_csv(DATA_PATH)
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError("Dataset is missing required columns: " + ", ".join(missing))
    return frame


@app.on_event("startup")
def ensure_dataset() -> None:
    if not DATA_PATH.exists():
        generate_sample_data().to_csv(DATA_PATH, index=False)


@app.get("/")
def root():
    return {"name": "Workflow Friction Monitor API", "status": "ok", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/summary")
def summary():
    try:
        scored = score_records(read_source_data())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    levels = scored["friction_level"].value_counts().to_dict()
    return {
        "total_tasks": int(len(scored)),
        "high_risk": int((scored["friction_level"] == "High").sum()),
        "average_friction": round(float(scored["friction_score"].mean()), 2),
        "average_bottleneck": round(float(scored["bottleneck_score"].mean()), 2),
        "levels": {key: int(value) for key, value in levels.items()},
    }


@app.get("/api/tasks")
def tasks(limit: int = 100, level: str | None = None, search: str | None = None):
    try:
        scored = score_records(read_source_data())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if level and level.lower() in {"low", "moderate", "high"}:
        scored = scored[scored["friction_level"].str.lower() == level.lower()]
    if search:
        term = search.strip().lower()
        scored = scored[
            scored["project_id"].str.lower().str.contains(term, na=False)
            | scored["task_name"].str.lower().str.contains(term, na=False)
        ]
    return {"items": scored.head(max(1, min(limit, 500))).where(pd.notna(scored), None).to_dict(orient="records"),
            "count": int(len(scored))}


@app.post("/api/score")
def score_one(task: TaskInput):
    frame = pd.DataFrame([task.model_dump()])
    try:
        result = score_records(frame).iloc[0].to_dict()
        # Convert numpy values to JSON-compatible Python values
        return {k: (v.item() if hasattr(v, "item") else v) for k, v in result.items()}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")
    try:
        contents = await file.read()
        frame = pd.read_csv(io.BytesIO(contents))
        missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
        if missing:
            raise HTTPException(status_code=422, detail="CSV missing columns: " + ", ".join(missing))
        # Validate and score before replacing active dataset.
        score_records(frame)
        frame.to_csv(DATA_PATH, index=False)
        return {"message": "Dataset uploaded and validated.", "rows": int(len(frame))}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read CSV: {exc}") from exc


@app.post("/api/reset-sample")
def reset_sample():
    frame = generate_sample_data()
    frame.to_csv(DATA_PATH, index=False)
    return {"message": "Sample dataset restored.", "rows": int(len(frame))}
