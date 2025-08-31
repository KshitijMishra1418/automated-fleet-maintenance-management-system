
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import sqlite3, os
from datetime import datetime, timedelta, date

app = Flask(__name__)
app.secret_key = "dev-secret"
DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png","jpg","jpeg","gif","webp"}

PARTS = ["Oil filter", "Brake pads", "Tires", "Air filter", "Spark plugs", "Coolant", "Engine oil"]

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = get_db()
    cur = con.cursor()
    # Tables
    cur.executescript(\"\"\"
    CREATE TABLE IF NOT EXISTS vehicles(
        id TEXT PRIMARY KEY,
        vtype TEXT,
        depot TEXT,
        mileage INTEGER,
        last_service DATE,
        interval TEXT
    );
    CREATE TABLE IF NOT EXISTS technicians(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        depot TEXT
    );
    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT,
        scheduled_date DATE,
        assigned_tech_id INTEGER,
        depot TEXT,
        status TEXT DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME,
        signature TEXT,
        FOREIGN KEY(vehicle_id) REFERENCES vehicles(id),
        FOREIGN KEY(assigned_tech_id) REFERENCES technicians(id)
    );
    CREATE TABLE IF NOT EXISTS task_parts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        part_name TEXT,
        qty INTEGER,
        FOREIGN KEY(task_id) REFERENCES tasks(id)
    );
    CREATE TABLE IF NOT EXISTS task_photos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        kind TEXT, -- 'before' or 'after'
        filename TEXT,
        FOREIGN KEY(task_id) REFERENCES tasks(id)
    );
    \"\"\")
    con.commit()

    # Seed vehicles and technicians if empty
    vcount = cur.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
    if vcount == 0:
        vehicles = [
            ("TRK-001","Truck","Depot A", 125000, "2025-08-01","Weekly"),
            ("VAN-205","Van","Depot A", 78000, "2025-08-10","Bi-weekly"),
            ("MOTO-011","Motorcycle","Depot B", 15000, "2025-08-05","Monthly"),
            ("CAR-078","Car","Depot B", 64000, "2025-08-12","Weekly"),
            ("TRK-009","Truck","Depot A", 220000, "2025-08-07","Monthly"),
            ("VAN-112","Van","Field Office", 54000, "2025-08-03","Bi-weekly"),
            ("CAR-222","Car","Field Office", 33000, "2025-08-15","Weekly"),
            ("TRK-104","Truck","Depot B", 98000, "2025-08-09","Monthly"),
            ("MOTO-044","Motorcycle","Depot A", 8000, "2025-08-13","Bi-weekly"),
            ("CAR-305","Car","Depot B", 45500, "2025-08-02","Monthly"),
        ]
        cur.executemany("INSERT INTO vehicles(id,vtype,depot,mileage,last_service,interval) VALUES(?,?,?,?,?,?)", vehicles)

    tcount = cur.execute("SELECT COUNT(*) FROM technicians").fetchone()[0]
    if tcount == 0:
        techs = [
            ("Aarav","Depot A"),
            ("Isha","Depot A"),
            ("Vihaan","Depot B"),
            ("Sara","Field Office"),
        ]
        cur.executemany("INSERT INTO technicians(name,depot) VALUES(?,?)", techs)

    con.commit()
    con.close()

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

def interval_to_days(interval):
    m = {"Weekly":7, "Bi-weekly":14, "Monthly":30}
    return m.get(interval, 30)

@app.route("/")
def dashboard():
    con = get_db()
    cur = con.cursor()
    # Counts
    total_tasks = cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    completed_tasks = cur.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
    pending_tasks = cur.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'").fetchone()[0]
    today = date.today().isoformat()
    overdue = cur.execute("SELECT COUNT(*) FROM tasks WHERE status!='completed' AND date(scheduled_date) < date(?)", (today,)).fetchone()[0]

    # Workload distribution
    workload = cur.execute(\"\"\"
        SELECT technicians.name, COUNT(tasks.id) as active
        FROM technicians
        LEFT JOIN tasks ON tasks.assigned_tech_id=technicians.id AND tasks.status!='completed'
        GROUP BY technicians.id
        ORDER BY technicians.name
    \"\"\").fetchall()

    # Completed gallery (latest 8)
    gallery = cur.execute(\"\"\"
        SELECT t.id as task_id, v.id as vehicle_id, tp.filename
        FROM tasks t
        JOIN vehicles v ON v.id = t.vehicle_id
        JOIN task_photos tp ON tp.task_id = t.id AND tp.kind='after'
        WHERE t.status='completed'
        ORDER BY t.completed_at DESC
        LIMIT 8
    \"\"\").fetchall()

    con.close()
    return render_template("index.html",
                           total_tasks=total_tasks,
                           completed_tasks=completed_tasks,
                           pending_tasks=pending_tasks,
                           overdue=overdue,
                           workload=workload,
                           gallery=gallery)

@app.route("/vehicles")
def vehicles():
    con = get_db()
    rows = con.execute("SELECT * FROM vehicles ORDER BY id").fetchall()
    con.close()
    return render_template("vehicles.html", vehicles=rows)

@app.route("/tasks")
def tasks():
    con = get_db()
    rows = con.execute(\"\"\"
        SELECT t.*, v.vtype, v.depot as vdepot, technicians.name as tech_name
        FROM tasks t
        JOIN vehicles v ON v.id = t.vehicle_id
        LEFT JOIN technicians ON technicians.id = t.assigned_tech_id
        ORDER BY t.scheduled_date DESC, t.id DESC
    \"\"\").fetchall()
    con.close()
    return render_template("tasks.html", tasks=rows)

@app.route("/technicians")
def technicians():
    con = get_db()
    techs = con.execute("SELECT * FROM technicians ORDER BY name").fetchall()
    # Count active tasks for each
    active_map = {t["id"]: con.execute("SELECT COUNT(*) FROM tasks WHERE assigned_tech_id=? AND status!='completed'", (t["id"],)).fetchone()[0] for t in techs}
    con.close()
    return render_template("technicians.html", techs=techs, active_map=active_map)

@app.route("/tech/<int:tech_id>/tasks")
def tech_tasks(tech_id):
    con = get_db()
    tech = con.execute("SELECT * FROM technicians WHERE id=?", (tech_id,)).fetchone()
    rows = con.execute(\"\"\"
        SELECT t.*, v.vtype, v.depot as vdepot
        FROM tasks t
        JOIN vehicles v ON v.id = t.vehicle_id
        WHERE t.assigned_tech_id=? AND t.status!='completed'
        ORDER BY t.scheduled_date ASC
    \"\"\", (tech_id,)).fetchall()
    con.close()
    return render_template("tech_tasks.html", tech=tech, tasks=rows)

@app.route("/task/<int:task_id>/complete", methods=["GET","POST"])
def complete_task(task_id):
    con = get_db()
    task = con.execute(\"\"\"
        SELECT t.*, v.vtype, v.depot AS vdepot, v.id AS vehicle_id
        FROM tasks t JOIN vehicles v ON v.id=t.vehicle_id
        WHERE t.id=?
    \"\"\",(task_id,)).fetchone()
    if not task:
        con.close()
        flash("Task not found","danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        signature = request.form.get("signature","").strip()
        status = request.form.get("status","completed")
        # parts
        selected_parts = request.form.getlist("parts")
        # quantities by part name
        parts_qty = {}
        for p in selected_parts:
            qty_field = f"qty_{p.replace(' ','_')}"
            try:
                qv = int(request.form.get(qty_field,"1"))
            except:
                qv = 1
            parts_qty[p] = max(1, qv)

        # photos
        for kind in ["before","after"]:
            file = request.files.get(kind)
            if file and allowed_file(file.filename):
                fname = f"task{task_id}_{kind}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file.filename.rsplit('.',1)[1].lower()}"
                path = os.path.join(UPLOAD_FOLDER, fname)
                file.save(path)
                con.execute("INSERT INTO task_photos(task_id, kind, filename) VALUES(?,?,?)",(task_id, kind, fname))

        # save parts
        con.execute("DELETE FROM task_parts WHERE task_id=?", (task_id,))
        for name, qty in parts_qty.items():
            con.execute("INSERT INTO task_parts(task_id, part_name, qty) VALUES(?,?,?)",(task_id, name, qty))

        # update task
        con.execute("UPDATE tasks SET status=?, completed_at=?, signature=? WHERE id=?",
                    (status, datetime.now().isoformat(timespec="seconds"), signature, task_id))
        con.commit()
        con.close()
        flash("Task updated successfully","success")
        return redirect(url_for("tasks"))

    # GET
    parts = PARTS
    con.close()
    return render_template("complete_task.html", task=task, parts=parts)

@app.route("/generate_tasks", methods=["POST"])
def generate_tasks():
    \"\"\"Generate tasks for next 30 days based on last_service + interval.\"\"\"
    con = get_db()
    cur = con.cursor()
    vehicles = cur.execute("SELECT * FROM vehicles").fetchall()
    today = datetime.today().date()
    end_date = today + timedelta(days=30)

    created = 0
    for v in vehicles:
        last = datetime.strptime(v["last_service"], "%Y-%m-%d").date()
        step = timedelta(days=interval_to_days(v["interval"]))
        next_due = last + step
        # create 1 task if next_due is within the next month and not already created
        if today <= next_due <= end_date:
            # check if a task already exists for that vehicle on that date
            exists = cur.execute(\"\"\"
                SELECT COUNT(*) FROM tasks WHERE vehicle_id=? AND date(scheduled_date)=date(?)
            \"\"\",(v["id"], next_due.isoformat())).fetchone()[0]
            if exists == 0:
                cur.execute(\"\"\"
                    INSERT INTO tasks(vehicle_id, scheduled_date, depot, status)
                    VALUES(?,?,?, 'pending')
                \"\"\",(v["id"], next_due.isoformat(), v["depot"]))
                created += 1

    con.commit()
    con.close()
    flash(f"Generated {created} task(s) for the upcoming month.","success")
    return redirect(url_for("tasks"))

@app.route("/auto_assign", methods=["POST"])
def auto_assign():
    con = get_db()
    cur = con.cursor()
    # pull unassigned tasks
    tasks = cur.execute("SELECT * FROM tasks WHERE assigned_tech_id IS NULL AND status!='completed'").fetchall()
    techs = cur.execute("SELECT * FROM technicians").fetchall()

    # helper: count active tasks
    def active_count(tech_id):
        return cur.execute("SELECT COUNT(*) FROM tasks WHERE assigned_tech_id=? AND status!='completed'", (tech_id,)).fetchone()[0]

    assigned = 0
    for t in tasks:
        # prefer techs from same depot with capacity (<3 active), choose least load
        same_depot = [tech for tech in techs if tech["depot"] == t["depot"] and active_count(tech["id"]) < 3]
        pool = same_depot if same_depot else [tech for tech in techs if active_count(tech["id"]) < 3]
        if not pool:
            continue
        # choose tech with least workload
        pool_sorted = sorted(pool, key=lambda te: active_count(te["id"]))
        chosen = pool_sorted[0]
        cur.execute("UPDATE tasks SET assigned_tech_id=? WHERE id=?", (chosen["id"], t["id"]))
        assigned += 1

    con.commit()
    con.close()
    flash(f"Auto-assigned {assigned} task(s).","success")
    return redirect(url_for("tasks"))

@app.context_processor
def inject_globals():
    return dict(PARTS=PARTS)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
