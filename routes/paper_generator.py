from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify
import random

from models import db
from models.paper import Paper, PaperQuestion
from services.syllabus_parser import parse_syllabus
from services.bloom_engine import generate_question

paper_bp = Blueprint("paper", __name__)

@paper_bp.before_request
def check_faculty_access():
    """Ensure faculty routes are faculty-only"""
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    if user.get("role") == "admin":
        flash("Admins cannot access faculty features", "error")
        return redirect(url_for("admin.dashboard"))

@paper_bp.route("/faculty/paper-generator", methods=["GET", "POST"])
def paper_generator():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        syllabus_text = request.form.get("syllabus", "").strip()
        marks_selected = [int(m) for m in request.form.getlist("marks") if m.isdigit() and int(m) in (2, 4, 8)]

        try:
            duration = int(request.form.get("duration", 120))
            if duration < 30 or duration > 240:
                duration = 120
        except (TypeError, ValueError):
            duration = 120

        try:
            difficulty = int(request.form.get("difficulty", 2))
        except ValueError:
            difficulty = 2

        if not subject or not syllabus_text or not marks_selected:
            flash("All fields are required", "error")
            return render_template("faculty/faculty_paper_generator.html")

        topics = parse_syllabus(syllabus_text)
        if not topics:
            flash("Invalid syllabus text: no topics found", "error")
            return render_template("faculty/faculty_paper_generator.html")

        user = session.get("user")
        paper = Paper(subject=subject, difficulty=difficulty, owner_email=user.get("email"))
        # stash duration in session; not persisted in model for now
        session["current_paper_duration"] = duration

        db.session.add(paper)
        db.session.commit()

        used_questions = set()
        # strength: more topics + higher difficulty => more questions
        question_count = min(60, max(5, len(topics) * difficulty + len(marks_selected) * 2))

        for i in range(question_count):
            topic = random.choice(topics)
            marks = random.choice(marks_selected)
            question_text, bloom_level, co_level = generate_question(topic, marks, used_questions, difficulty=difficulty, index=i)

            q_item = PaperQuestion(
                paper_id=paper.id,
                topic=topic,
                marks=marks,
                text=question_text,
                bloom_level=bloom_level,
                co_level=co_level,
                is_selected=False
            )
            db.session.add(q_item)

        db.session.commit()

        session["current_paper_id"] = paper.id
        return redirect(url_for("paper.review_questions", paper_id=paper.id))

    return render_template("faculty/faculty_paper_generator.html")


ITEMS_PER_PAGE = 10

@paper_bp.route("/faculty/paper-review/<int:paper_id>", methods=["GET", "POST"])
def review_questions(paper_id):
    paper = Paper.query.get_or_404(paper_id)
    page = request.args.get("page", 1, type=int)
    bloom_filter = request.args.get("bloom", "all").strip()

    if request.method == "POST":
        selected_ids = [int(q_id) for q_id in request.form.getlist("select_question") if q_id.isdigit()]
        bloom_filter = request.form.get("bloom", bloom_filter).strip()

        if not selected_ids:
            flash("Select at least one question", "error")
            query = PaperQuestion.query.filter_by(paper_id=paper_id)
            if bloom_filter and bloom_filter.lower() != "all":
                query = query.filter(PaperQuestion.bloom_level.ilike(bloom_filter))
            questions = query.order_by(PaperQuestion.id).limit(ITEMS_PER_PAGE).all()
            total = query.count()
            has_more = total > len(questions)
            duration = session.get("current_paper_duration", 120)
            return render_template("faculty/faculty_review_questions.html", questions=questions, paper=paper, has_more=has_more, duration=duration, bloom_filter=bloom_filter)

        PaperQuestion.query.filter_by(paper_id=paper_id).update({"is_selected": False})
        PaperQuestion.query.filter(PaperQuestion.id.in_(selected_ids)).update({"is_selected": True}, synchronize_session=False)
        db.session.commit()

        return redirect(url_for("paper.export_paper", paper_id=paper_id))

    query = PaperQuestion.query.filter_by(paper_id=paper_id)
    if bloom_filter and bloom_filter.lower() != "all":
        query = query.filter(PaperQuestion.bloom_level.ilike(bloom_filter))

    questions = query.order_by(PaperQuestion.id).limit(ITEMS_PER_PAGE).all()
    total = query.count()
    has_more = total > len(questions)
    duration = session.get("current_paper_duration", 120)

    return render_template("faculty/faculty_review_questions.html", questions=questions, paper=paper, has_more=has_more, duration=duration, bloom_filter=bloom_filter)


@paper_bp.route("/faculty/paper-review/<int:paper_id>/questions")
def review_questions_page(paper_id):
    paper = Paper.query.get_or_404(paper_id)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", ITEMS_PER_PAGE, type=int)
    bloom_filter = request.args.get("bloom", "all").strip()

    query = PaperQuestion.query.filter_by(paper_id=paper_id)
    if bloom_filter and bloom_filter.lower() != "all":
        query = query.filter(PaperQuestion.bloom_level.ilike(bloom_filter))

    query = query.order_by(PaperQuestion.id)
    total = query.count()
    questions = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "paper_id": paper_id,
        "page": page,
        "per_page": per_page,
        "total": total,
        "has_more": (page * per_page) < total,
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "marks": q.marks,
                "topic": q.topic,
                "bloom_level": q.bloom_level,
                "co_level": q.co_level,
                "is_selected": q.is_selected,
            }
            for q in questions
        ],
    })


@paper_bp.route("/export/<int:paper_id>")
def export_paper(paper_id):
    paper = Paper.query.get_or_404(paper_id)
    selected_questions = PaperQuestion.query.filter_by(paper_id=paper_id, is_selected=True).all()

    if not selected_questions:
        return "No questions selected for export. Go back to review and choose questions.", 400

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import inch
    except ImportError:
        return "reportlab package not found. Install with pip install reportlab.", 500

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Question Paper: {paper.subject}", styles["Title"]))
    story.append(Paragraph(f"Date: {paper.created_at.strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))

    for idx, q in enumerate(selected_questions, start=1):
        story.append(Paragraph(f"{idx}. ({q.marks} Marks) {q.text}", styles["BodyText"]))
        story.append(Spacer(1, 0.1 * inch))

    doc.build(story)
    buffer.seek(0)

    file_name = f"{paper.subject.replace(' ', '_')}_paper_{paper.id}.pdf"
    return send_file(buffer, as_attachment=True, download_name=file_name, mimetype="application/pdf")
