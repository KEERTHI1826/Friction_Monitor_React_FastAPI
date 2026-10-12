
from pathlib import Path
import html
import json
import re

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware


# --------------------------------------------------
# APP AND FILE PATHS
# --------------------------------------------------

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR.parent / "data"
DATA_PATH = DATA_DIR / "AI_Workflow_Optimization_Dataset_2500_Rows_v1.csv"

DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Workflow Friction Monitor API",
    version="1.0.0",
    description="Workflow analysis and friction scoring API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# These are the standard columns used internally by the scoring system.
REQUIRED_COLUMNS = [
    "project_id",
    "task_id",
    "task_name",
    "planned_days",
    "actual_days",
    "response_delay",
    "rework_count",
    "dependency_count",
    "team_workload",
]


# --------------------------------------------------
# SAMPLE DATA
# --------------------------------------------------

def generate_sample_data():
    """Create sample data only when explicitly requested."""

    rows = []

    for project in range(1, 6):
        for task in range(1, 7):
            planned = 2 + (task % 3)
            actual = planned + (task % 2)

            rows.append({
                "project_id": f"P{project:03d}",
                "task_id": f"T{task:03d}",
                "task_name": f"Sample Task {task}",
                "planned_days": planned,
                "actual_days": actual,
                "response_delay": task % 3,
                "rework_count": task % 2,
                "dependency_count": task % 3,
                "team_workload": 30 + task * 10,
            })

    return pd.DataFrame(rows)


# --------------------------------------------------
# COLUMN CLEANING AND DATA CONVERSION
# --------------------------------------------------

def clean_column_name(column):
    """Handle spaces, leading asterisks and HTML entities."""

    column = html.unescape(str(column)).strip()
    column = column.lstrip("*# ").strip()
    column = column.replace("\ufeff", "")

    return re.sub(r"[^a-z0-9]", "", column.lower())


def read_source_data():
    """Read the CSV and convert its columns for scoring."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}. "
            "Place your CSV in the backend/data folder."
        )

    frame = pd.read_csv(DATA_PATH, encoding="utf-8-sig")

    if frame.empty:
        raise ValueError("The dataset CSV is empty.")

    # Match columns even if the CSV contains unusual formatting.
    source_columns = {
        clean_column_name(column): column
        for column in frame.columns
    }

    column_mapping = {
        "workflowid": "project_id",
        "projectid": "project_id",
        "taskid": "task_id",
        "processname": "task_name",
        "taskname": "task_name",
        "estimatedtimeminutes": "planned_days",
        "planneddays": "planned_days",
        "actualtimeminutes": "actual_days",
        "actualdays": "actual_days",
        "employeeworkload": "team_workload",
        "teamworkload": "team_workload",
        "delayflag": "Delay_Flag",
        "tasktype": "Task_Type",
        "prioritylevel": "Priority_Level",
        "department": "Department",
        "assignedemployeeid": "Assigned_Employee_ID",
        "taskstarttime": "Task_Start_Time",
        "taskendtime": "Task_End_Time",
        "approvallevel": "Approval_Level",
        "costpertask": "Cost_Per_Task",
    }

    rename_mapping = {}

    for cleaned_name, original_name in source_columns.items():
        if cleaned_name in column_mapping:
            rename_mapping[original_name] = column_mapping[cleaned_name]

    frame = frame.rename(columns=rename_mapping)

    # Ensure the required source fields are available.
    required_source = [
        "project_id",
        "task_id",
        "task_name",
        "planned_days",
        "actual_days",
        "team_workload",
    ]

    missing_source = [
        column for column in required_source
        if column not in frame.columns
    ]

    if missing_source:
        raise ValueError(
            "CSV is missing required fields: "
            + ", ".join(missing_source)
            + ". Check the CSV column names."
        )

    # The dataset measures duration in minutes.
    frame["planned_days"] = pd.to_numeric(
        frame["planned_days"], errors="coerce"
    ) / 1440.0

    frame["actual_days"] = pd.to_numeric(
        frame["actual_days"], errors="coerce"
    ) / 1440.0

    frame["team_workload"] = pd.to_numeric(
        frame["team_workload"], errors="coerce"
    )

    # The source workload is normally on a 1-10 scale.
    if frame["team_workload"].max() <= 10:
        frame["team_workload"] = frame["team_workload"] * 10

    frame["team_workload"] = frame["team_workload"].clip(0, 100)

    # These fields are not supplied by the source dataset.
    # Zero means unavailable/not measured, not a detected absence.
    for column in ["response_delay", "rework_count", "dependency_count"]:
        if column not in frame.columns:
            frame[column] = 0

        frame[column] = pd.to_numeric(
            frame[column], errors="coerce"
        ).fillna(0)

    # Validate numeric data.
    for column in ["planned_days", "actual_days", "team_workload"]:
        frame[column] = pd.to_numeric(
            frame[column], errors="coerce"
        )

    frame = frame.dropna(
        subset=["planned_days", "actual_days", "team_workload"]
    )

    # Avoid division by zero.
    frame["planned_days"] = frame["planned_days"].clip(lower=1 / 1440)
    frame["actual_days"] = frame["actual_days"].clip(lower=0)

    if frame.empty:
        raise ValueError("No valid task records were found in the CSV.")

    missing_internal = [
        column for column in REQUIRED_COLUMNS
        if column not in frame.columns
    ]

    if missing_internal:
        raise ValueError(
            "Internal data conversion failed. Missing columns: "
            + ", ".join(missing_internal)
        )

    return frame


# --------------------------------------------------
# WORKFLOW FRICTION SCORING
# --------------------------------------------------

def score_records(frame):
    """Calculate rule-based friction and bottleneck scores."""

    if frame is None or frame.empty:
        return pd.DataFrame()

    result = frame.copy()

    # Calculate delay from actual duration compared with estimated duration.
    delay_percentage = (
        (result["actual_days"] - result["planned_days"])
        / result["planned_days"].clip(lower=1 / 1440)
    ) * 100

    result["delay_score"] = delay_percentage.clip(0, 100)

    # Use Delay_Flag as an additional indication of delay, if available.
    if "Delay_Flag" in result.columns:
        delay_flag = pd.to_numeric(
            result["Delay_Flag"], errors="coerce"
        ).fillna(0)

        result["delay_score"] = np.maximum(
            result["delay_score"],
            np.where(delay_flag > 0, 100, 0),
        )

    result["response_score"] = (
        result["response_delay"] / 4 * 100
    ).clip(0, 100)

    result["rework_score"] = (
        result["rework_count"] / 3 * 100
    ).clip(0, 100)

    result["dependency_score"] = (
        result["dependency_count"] / 3 * 100
    ).clip(0, 100)

    result["workload_score"] = result["team_workload"].clip(0, 100)

    # Weighted friction score.
    result["friction_score"] = (
        0.30 * result["delay_score"]
        + 0.20 * result["response_score"]
        + 0.15 * result["rework_score"]
        + 0.15 * result["dependency_score"]
        + 0.20 * result["workload_score"]
    ).round(2)

    result["risk_level"] = np.select(
        [
            result["friction_score"] < 30,
            result["friction_score"] < 60,
        ],
        [
            "Low",
            "Moderate",
        ],
        default="High",
    )

    result["bottleneck_score"] = (
        0.70 * result["friction_score"]
        + 0.30 * result["dependency_count"].clip(0, 10) * 10
    ).round(2)

    # Suggested actions based on the available data.
    result["recommendation"] = np.select(
        [
            result["delay_score"] >= 50,
            result["team_workload"] >= 80,
            result["dependency_count"] >= 2,
            result["friction_score"] >= 60,
        ],
        [
            "Review task estimates and investigate delays",
            "Redistribute workload across team members",
            "Review task dependencies and approval steps",
            "Investigate the task's main friction factors",
        ],
        default="Continue monitoring workflow performance",
    )

    return result


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def get_scored_data():
    source = read_source_data()
    return score_records(source)


def dataframe_to_records(frame):
    """Convert DataFrame values to JSON-safe records."""

    safe_frame = frame.replace({np.nan: None})
    return json.loads(safe_frame.to_json(orient="records"))


# --------------------------------------------------
# BASIC ROUTES
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "name": "Workflow Friction Monitor API",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# --------------------------------------------------
# SUMMARY API
# --------------------------------------------------

@app.get("/api/summary")
def get_summary():
    try:
        frame = get_scored_data()

        total_tasks = int(len(frame))
        high_risk = int((frame["risk_level"] == "High").sum())
        moderate_risk = int((frame["risk_level"] == "Moderate").sum())
        low_risk = int((frame["risk_level"] == "Low").sum())

        average_friction = round(
            float(frame["friction_score"].mean()), 2
        )

        return {
            "total_tasks": total_tasks,
            "total_records": total_tasks,
            "average_friction": average_friction,
            "avg_friction_score": average_friction,
            "high_risk_tasks": high_risk,
            "moderate_risk_tasks": moderate_risk,
            "low_risk_tasks": low_risk,
            "bottleneck_count": int(
                (frame["bottleneck_score"] >= 60).sum()
            ),
            "risk_distribution": {
                "Low": low_risk,
                "Moderate": moderate_risk,
                "High": high_risk,
            },
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# --------------------------------------------------
# TASKS API
# --------------------------------------------------

@app.get("/api/tasks")
def get_tasks(limit: int = 100, offset: int = 0):
    try:
        frame = get_scored_data()

        limit = max(1, min(limit, 2500))
        offset = max(0, offset)

        page = frame.iloc[offset:offset + limit]

        return {
            "total": int(len(frame)),
            "limit": limit,
            "offset": offset,
            "tasks": dataframe_to_records(page),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# --------------------------------------------------
# SCORE API
# --------------------------------------------------

@app.get("/api/score")
def get_scores():
    try:
        frame = get_scored_data()

        return {
            "total": int(len(frame)),
            "scores": dataframe_to_records(frame),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# --------------------------------------------------
# CSV UPLOAD API
# --------------------------------------------------

@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file.",
        )

    try:
        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )

        # Validate the upload before replacing the existing dataset.
        import io

        test_frame = pd.read_csv(
            io.BytesIO(contents), encoding="utf-8-sig"
        )

        if test_frame.empty:
            raise HTTPException(
                status_code=400,
                detail="The uploaded CSV has no records.",
            )

        # Preserve the current dataset if the upload is invalid.
        temporary_path = DATA_DIR / "upload_validation_temp.csv"
        test_frame.to_csv(temporary_path, index=False)

        try:
            global DATA_PATH
            original_path = DATA_PATH
            DATA_PATH = temporary_path

            read_source_data()
        finally:
            DATA_PATH = original_path
            if temporary_path.exists():
                temporary_path.unlink()

        DATA_PATH.write_bytes(contents)

        return {
            "message": "CSV uploaded and validated successfully.",
            "filename": file.filename,
            "rows": int(len(test_frame)),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------
# RESET SAMPLE DATA API
# --------------------------------------------------

@app.post("/api/reset-sample")
def reset_sample():
    try:
        sample = generate_sample_data()
        sample.to_csv(DATA_PATH, index=False)

        return {
            "message": "Sample data generated successfully.",
            "rows": int(len(sample)),
            "warning": (
                "The configured CSV was replaced with sample data."
            ),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
