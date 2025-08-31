# Fleet Maintenance Prototype (Flask + SQLite)

A simple prototype web app that demonstrates:
- Vehicle database (preloaded with 10 vehicles)
- Generate maintenance tasks for the upcoming month (one click)
- Smart task assignment to technicians (max 3 active tasks, depot proximity, workload balancing)
- Technician task execution (before/after photos, parts used, completion + signature)
- Dashboard with overdue tasks, technician workload distribution, and completed task gallery

## Quick Start

```bash
# 1) Create a virtual environment (optional but recommended)
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Run the app
export FLASK_APP=app.py  # Windows PowerShell: $env:FLASK_APP="app.py"
flask run
# App runs at http://127.0.0.1:5000
```

## Default Data
- 10 vehicles across depots A/B/Field
- 4 technicians mapped to depots

## Features to Demo
- Click **Generate Tasks** to create next-month tasks.
- Click **Auto Assign** to distribute tasks to technicians (max 3 active each, prefer same depot).
- Open **Technicians → View Tasks** to complete a task (upload photos, select parts, sign).
- **Dashboard** shows overdue counts, workload distribution chart, and completed gallery.

> This is a **prototype**, not production-ready. Uses SQLite and a simple file upload folder under `uploads/`.
