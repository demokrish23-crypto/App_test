import os
from datetime import timedelta
from flask import Flask, render_template, request, redirect, session, url_for, flash
from sqlalchemy import text
from models import db

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ensure instance folder exists (where SQLite file is created)
os.makedirs(app.instance_path, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(app.instance_path, 'app.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Session configuration - user stays logged in until logout
app.config["SESSION_PERMANENT"] = False  # Session cookie expires on browser/app close
# app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)  # Only needed if you want persistent sessions
app.config["SESSION_COOKIE_SECURE"] = False  # Set True in production with HTTPS
app.config["SESSION_COOKIE_HTTPONLY"] = True  # Prevent JavaScript access
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # CSRF protection

# Initialize db with app first
db.init_app(app)

# Import models to register them with SQLAlchemy metadata
from models.question_bank import Question  # noqa: F401, E402
from models.paper import Paper, PaperQuestion  # noqa: F401, E402
from models import SessionLog  # noqa: F401, E402

def get_ist_now():
    from datetime import datetime, timedelta
    # IST is UTC+5:30
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# Create all tables in app context
with app.app_context():
    db.create_all()
    db.session.commit()

    # ensure extra question fields exist for old question tables
    try:
        with db.engine.begin() as conn:
            check = conn.execute(text("PRAGMA table_info(question)")).fetchall()
            if check and not any(col[1] == "owner_email" for col in check):
                conn.execute(text("ALTER TABLE question ADD COLUMN owner_email VARCHAR(150) NOT NULL DEFAULT 'unknown'"))
            if check and not any(col[1] == "bloom_level" for col in check):
                conn.execute(text("ALTER TABLE question ADD COLUMN bloom_level VARCHAR(80)"))
            if check and not any(col[1] == "co_level" for col in check):
                conn.execute(text("ALTER TABLE question ADD COLUMN co_level VARCHAR(20)"))
    except Exception:
        pass

# Ensure tables still exist before the first request (safety net)
@app.before_request
def ensure_tables_exist():
    if not app.config.get("TABLES_CREATED"):
        from models.question_bank import Question  # noqa: F401
        from models.paper import Paper, PaperQuestion  # noqa: F401
        from models import SessionLog  # noqa: F401
        
        try:
            db.create_all()
            db.session.commit()
            
            with db.engine.begin() as conn:
                check = conn.execute(text("PRAGMA table_info(question)")).fetchall()
                if check and not any(col[1] == "owner_email" for col in check):
                    conn.execute(text("ALTER TABLE question ADD COLUMN owner_email VARCHAR(150) NOT NULL DEFAULT 'unknown'"))
                if check and not any(col[1] == "bloom_level" for col in check):
                    conn.execute(text("ALTER TABLE question ADD COLUMN bloom_level VARCHAR(80)"))
                if check and not any(col[1] == "co_level" for col in check):
                    conn.execute(text("ALTER TABLE question ADD COLUMN co_level VARCHAR(20)"))
        except Exception:
            pass

        app.config["TABLES_CREATED"] = True

from routes.paper_generator import paper_bp  # noqa: E402
from routes.question_bank import question_bank_bp  # noqa: E402
from routes.admin import admin_bp  # noqa: E402

app.register_blueprint(paper_bp)
app.register_blueprint(question_bank_bp)
app.register_blueprint(admin_bp)

def _read_all_users_from_file():
    users = []
    try:
        with open("users.txt", "r") as f:
            for line in f:
                parts = [p.strip() for p in line.strip().split(",", 3)]
                if len(parts) != 4:
                    continue
                role, email, password, name = parts
                users.append({
                    "role": role,
                    "email": email,
                    "password": password,
                    "name": name,
                })
    except FileNotFoundError:
        pass
    return users

def _write_all_users_to_file(users):
    with open("users.txt", "w") as f:
        for u in users:
            f.write(f"{u['role']},{u['email']},{u['password']},{u['name']}\n")

def load_users():
    users = []
    try:
        with open("users.txt") as f:
            for line in f:
                parts = [p.strip() for p in line.strip().split(",", 3)]
                if len(parts) != 4:
                    continue
                role, email, password, name = parts
                users.append({
                    "role": role,
                    "email": email,
                    "password": password,
                    "name": name
                })
    except FileNotFoundError:
        pass
    return users

@app.route("/")
def welcome():
    return render_template("public/welcome.html")

@app.route("/landing")
def landing():
    return render_template("public/landing.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        for user in load_users():
            if user["email"] == email and user["password"] == password and user["role"] == role:
                session.permanent = True  # Mark session as permanent (won't expire until logout)
                session["user"] = user
                # Store start time in IST
                session["_session_start"] = get_ist_now().replace(tzinfo=None)
                
                # Log the session in IST
                from models import SessionLog, db
                try:
                    log = SessionLog(
                        email=email,
                        name=user.get("name", ""),
                        role=role,
                        login_time=get_ist_now(),
                        ip_address=request.remote_addr
                    )
                    db.session.add(log)
                    db.session.commit()
                except Exception as e:
                    print(f"Failed to log session: {e}")
                
                if role == "faculty":
                    return redirect("/faculty/dashboard")
                if role == "admin":
                    return redirect("/admin-dev")

        error = "Invalid credentials"

    return render_template("public/login.html", error=error)

def require_role(required_role):
    """Decorator to ensure user has required role"""
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = session.get("user")
            if not user:
                return redirect("/login")
            if user.get("role") != required_role:
                flash(f"Access denied: {required_role} only", "error")
                if required_role == "admin":
                    return redirect(url_for("faculty_dashboard"))
                else:
                    return redirect(url_for("admin.dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route("/faculty/dashboard")
@require_role("faculty")
def faculty_dashboard():
    user = session.get("user")
    from models.question_bank import Question
    from models.paper import Paper

    user_email = user.get("email")

    try:
        if user.get("role") == "admin":
            total_questions = Question.query.count()
            total_papers = Paper.query.count()
            subjects_list = db.session.query(Question.subject).distinct().count()
            avg_difficulty_result = db.session.query(db.func.avg(db.cast(db.func.substr(Question.difficulty, 1, 1), db.Integer))).scalar() or 0
        else:
            total_questions = Question.query.filter_by(owner_email=user_email).count()
            total_papers = Paper.query.filter_by(owner_email=user_email).count()
            subjects_list = db.session.query(Question.subject).filter(Question.owner_email == user_email).distinct().count()
            avg_difficulty_result = db.session.query(db.func.avg(db.cast(db.func.substr(Question.difficulty, 1, 1), db.Integer))).filter(Question.owner_email == user_email).scalar() or 0
    except Exception:
        total_questions = 0
        total_papers = 0
        subjects_list = 0
        avg_difficulty_result = 0

    return render_template(
        "faculty/faculty_dashboard.html",
        faculty_name=user["name"],
        total_questions=total_questions,
        total_papers=total_papers,
        total_subjects=subjects_list,
        avg_difficulty=round(float(avg_difficulty_result), 1)
    )

# faculty question bank and paper generator routes are handled in blueprints

@app.route("/faculty/analytics")
@require_role("faculty")
def faculty_analytics():
    user = session.get("user")

    from models.question_bank import Question
    from models.paper import Paper

    try:
        if user.get("role") == "admin":
            total_questions = Question.query.count()
            subjects = db.session.query(Question.subject, db.func.count(Question.id)).group_by(Question.subject).all()
            difficulty_dist = db.session.query(Question.difficulty, db.func.count(Question.id)).group_by(Question.difficulty).all()
        else:
            user_email = user.get("email")
            total_questions = Question.query.filter_by(owner_email=user_email).count()
            subjects = db.session.query(Question.subject, db.func.count(Question.id)).filter(Question.owner_email == user_email).group_by(Question.subject).all()
            difficulty_dist = db.session.query(Question.difficulty, db.func.count(Question.id)).filter(Question.owner_email == user_email).group_by(Question.difficulty).all()

        total_papers = Paper.query.count()
    except Exception:
        total_questions = 0
        total_papers = 0
        subjects = []
        difficulty_dist = []

    return render_template(
        "faculty/faculty_analytics.html",
        total_questions=total_questions,
        total_papers=total_papers,
        subjects=subjects,
        difficulty_dist=difficulty_dist
    )

@app.route("/faculty/history")
@require_role("faculty")
def faculty_history():
    user = session.get("user")

    from models.paper import Paper

    if user.get("role") == "admin":
        papers = Paper.query.options(db.joinedload(Paper.questions)).order_by(Paper.created_at.desc()).all()
    else:
        papers = Paper.query.options(db.joinedload(Paper.questions)).filter_by(owner_email=user.get("email")).order_by(Paper.created_at.desc()).all()

    return render_template("faculty/faculty_history.html", papers=papers)

@app.route("/faculty/settings")
@require_role("faculty")
def faculty_settings():
    user = session.get("user")

    return render_template("faculty/faculty_settings.html", user=user)

@app.route("/faculty/settings/update", methods=["POST"])
@require_role("faculty")
def update_settings():
    user = session.get("user")
    original_email = user.get("email")  # Store original email before updating session

    email = request.form.get("email")
    name = request.form.get("name")
    password = request.form.get("password")

    # Update session
    if email:
        session["user"]["email"] = email
    if name:
        session["user"]["name"] = name
    if password:
        session["user"]["password"] = password

    # Persist to users.txt using original email to find the user
    users = _read_all_users_from_file()
    updated = False
    for u in users:
        if u["email"] == original_email:
            if email:
                u["email"] = email
            if name:
                u["name"] = name
            if password:
                u["password"] = password
            updated = True
            break

    if updated:
        _write_all_users_to_file(users)

    session.modified = True
    flash("Settings updated successfully", "success")
    return redirect(url_for("faculty_settings"))


@app.route("/admin-dev")
def admin_dev():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return redirect("/login")
    return redirect(url_for("admin.dashboard"))


@app.context_processor
def inject_user():
    user = session.get("user")
    import datetime
    session_start = session.get('_session_start')
    if session_start:
        # Ensure both datetimes are naive and in UTC for subtraction
        now = datetime.datetime.utcnow()
        if hasattr(session_start, 'replace'):
            # If session_start has timezone info, make it naive
            session_start = session_start.replace(tzinfo=None)
        session_duration = now - session_start
    else:
        session_duration = datetime.timedelta(0)
    
    return {
        "faculty_name": user["name"] if user else "Guest",
        "user_role": user["role"] if user else None,
        "session_duration": session_duration
        # Don't add session here - Flask provides it automatically in templates
    }


@app.route("/logout")
def logout():
    import datetime
    from models import SessionLog, db
    
    # Record session duration before clearing session
    user = session.get("user")
    session_start = session.get('_session_start')
    
    if user and session_start:
        email = user.get("email")
        
        # Calculate session duration using IST
        now = get_ist_now()
        if hasattr(session_start, 'replace'):
            session_start = session_start.replace(tzinfo=None)
        
        duration = now - session_start
        duration_seconds = int(duration.total_seconds())
        
        try:
            # Find and update the most recent session log for this user
            log = SessionLog.query.filter_by(email=email).order_by(SessionLog.login_time.desc()).first()
            if log:
                log.logout_time = now
                log.session_duration_seconds = duration_seconds
                db.session.commit()
        except Exception as e:
            print(f"Error updating session log: {e}")
    
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)