from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db
from models.question_bank import Question
from models.paper import PaperQuestion

question_bank_bp = Blueprint("qb", __name__)

def _infer_difficulty_from_bloom(bloom_level):
    """Infer difficulty from Bloom taxonomy level"""
    if not bloom_level:
        return "Medium"
    bloom_lower = bloom_level.lower()
    if bloom_lower in ["remembering", "understanding"]:
        return "Easy"
    elif bloom_lower in ["applying", "analyzing"]:
        return "Medium"
    else:  # evaluating, creating
        return "Hard"

@question_bank_bp.before_request
def check_faculty_access():
    """Ensure faculty routes are faculty-only"""
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    if user.get("role") == "admin":
        flash("Admins cannot access faculty features", "error")
        return redirect(url_for("admin.dashboard"))

@question_bank_bp.route("/faculty/save-to-bank/<int:paper_id>", methods=["POST"])
def save_to_bank(paper_id):
    user = session.get("user")

    selected_ids = [int(q) for q in request.form.getlist("selected_question") if q.isdigit()]
    user_email = user.get("email")

    if selected_ids:
        # update paper question selection based on form
        PaperQuestion.query.filter_by(paper_id=paper_id).update({"is_selected": False})
        PaperQuestion.query.filter(PaperQuestion.id.in_(selected_ids)).update({"is_selected": True}, synchronize_session=False)
        db.session.commit()

    selected = PaperQuestion.query.filter_by(paper_id=paper_id, is_selected=True).all()
    if not selected:
        flash("No selected questions in paper to save", "warning")
        return redirect(url_for("paper.review_questions", paper_id=paper_id))

    for pq in selected:
        inferred_difficulty = _infer_difficulty_from_bloom(pq.bloom_level)
        question = Question(
            subject=pq.paper.subject if pq.paper else "General",
            topic=pq.topic,
            text=pq.text,
            marks=pq.marks,
            difficulty=inferred_difficulty,
            bloom_level=pq.bloom_level,
            co_level=pq.co_level,
            owner_email=user_email
        )
        db.session.add(question)

    db.session.commit()
    flash(f"{len(selected)} question(s) saved to bank", "success")
    return redirect(url_for("qb.view_bank"))


@question_bank_bp.route("/faculty/question-bank")
def view_bank():
    user = session.get("user")
    user_email = user.get("email")
    sort_by = request.args.get("sort_by", "subject")
    sort_order = request.args.get("sort_order", "asc")

    valid_sorts = ["subject", "topic", "marks", "difficulty", "bloom_level", "co_level"]
    if sort_by not in valid_sorts:
        sort_by = "subject"
    if sort_order not in ["asc", "desc"]:
        sort_order = "asc"

    from sqlalchemy.exc import OperationalError
    try:
        query = Question.query.filter_by(owner_email=user_email)
        subjects = db.session.query(Question.subject).filter(Question.owner_email == user_email).distinct().all()

        subjects = [s[0] for s in subjects]

        if sort_order == "desc":
            questions = query.order_by(getattr(Question, sort_by).desc()).all()
        else:
            questions = query.order_by(getattr(Question, sort_by).asc()).all()
    except OperationalError:
        db.create_all()
        query = Question.query.filter_by(owner_email=user_email)
        subjects = db.session.query(Question.subject).filter(Question.owner_email == user_email).distinct().all()

        subjects = [s[0] for s in subjects]

        if sort_order == "desc":
            questions = query.order_by(getattr(Question, sort_by).desc()).all()
        else:
            questions = query.order_by(getattr(Question, sort_by).asc()).all()

    # Get duplicates information
    duplicates_map = _get_all_duplicates_dict(questions)
    has_duplicates = len(duplicates_map) > 0
    # Count total duplicate questions to be deleted (not counting originals)
    total_duplicates = sum(info['count'] for info in duplicates_map.values())

    return render_template("faculty/faculty_question_bank.html", 
                         questions=questions, 
                         sort_by=sort_by, 
                         sort_order=sort_order, 
                         subjects=subjects,
                         duplicates_map=duplicates_map,
                         has_duplicates=has_duplicates,
                         total_duplicates=total_duplicates)


@question_bank_bp.route("/faculty/question-bank/add", methods=["GET", "POST"])
def add_question():
    user = session.get("user")

    if request.method == "POST":
        subject = request.form.get("subject", "General").strip()
        topic = request.form.get("topic", "General").strip()
        text = request.form.get("text", "").strip()
        marks = int(request.form.get("marks", 2))
        difficulty = request.form.get("difficulty", "Medium")

        if not subject or not topic or not text:
            flash("Subject, topic and text are required", "error")
            return redirect(url_for("qb.add_question"))

        bloom_level = request.form.get("bloom_level", "N/A").strip() or None
        co_level = request.form.get("co_level", "N/A").strip() or None

        question = Question(
            subject=subject,
            topic=topic,
            text=text,
            marks=marks,
            difficulty=difficulty,
            bloom_level=bloom_level,
            co_level=co_level,
            owner_email=user.get("email")
        )
        db.session.add(question)
        db.session.commit()
        flash("Question added to bank", "success")
        return redirect(url_for("qb.view_bank"))

    return render_template("faculty/faculty_question_bank_add.html")


@question_bank_bp.route("/faculty/question-bank/edit/<int:q_id>", methods=["GET", "POST"])
def edit_question(q_id):
    user = session.get("user")
    question = Question.query.get_or_404(q_id)
    
    if question.owner_email != user.get("email"):
        flash("Not allowed to edit this question", "error")
        return redirect(url_for("qb.view_bank"))

    if request.method == "POST":
        question.subject = request.form.get("subject", question.subject)
        question.topic = request.form.get("topic", question.topic)
        question.text = request.form.get("text", question.text)
        question.marks = int(request.form.get("marks", question.marks))
        question.difficulty = request.form.get("difficulty", question.difficulty)
        question.bloom_level = request.form.get("bloom_level", question.bloom_level) or question.bloom_level
        question.co_level = request.form.get("co_level", question.co_level) or question.co_level

        db.session.commit()
        flash("Question updated", "success")
        return redirect(url_for("qb.view_bank"))

    return render_template("faculty/faculty_question_bank_edit.html", question=question)


@question_bank_bp.route("/faculty/question-bank/delete/<int:q_id>", methods=["POST"])
def delete_question(q_id):
    user = session.get("user")
    question = Question.query.get_or_404(q_id)
    
    if question.owner_email != user.get("email"):
        flash("Not allowed to delete this question", "error")
        return redirect(url_for("qb.view_bank"))

    db.session.delete(question)
    db.session.commit()
    flash("Question deleted", "success")
    return redirect(url_for("qb.view_bank"))


@question_bank_bp.route("/faculty/create-paper-from-bank", methods=["POST"])
def create_paper_from_bank():
    user = session.get("user")
    question_ids = request.form.getlist("question_ids")
    if not question_ids:
        flash("No questions selected", "error")
        return redirect(url_for("qb.view_bank"))

    question_ids = [int(q_id) for q_id in question_ids if q_id.isdigit()]

    user_email = user.get("email")

    # Create paper with default name based on subjects
    selected_questions = Question.query.filter(Question.id.in_(question_ids)).all()
    
    if not selected_questions:
        flash("Selected questions not found", "error")
        return redirect(url_for("qb.view_bank"))

    subjects = set(q.subject for q in selected_questions)
    paper_subject = ", ".join(subjects) if len(subjects) <= 2 else f"{list(subjects)[0]} (Multiple)"
    
    from models.paper import Paper, PaperQuestion

    paper = Paper(subject=paper_subject, difficulty=3, owner_email=user_email)
    db.session.add(paper)
    db.session.commit()

    # Add selected questions to paper
    for q in selected_questions:
        paper_question = PaperQuestion(
            paper_id=paper.id,
            topic=q.topic,
            marks=q.marks,
            text=q.text,
            bloom_level=q.bloom_level,
            co_level=q.co_level,
            is_selected=True
        )
        db.session.add(paper_question)

    db.session.commit()

    flash(f"Paper created with {len(selected_questions)} questions", "success")
    return redirect(url_for("paper.review_questions", paper_id=paper.id))


def _get_duplicates_for_question(question_text, user_email, exclude_id=None):
    """Find duplicate questions based on text (case-insensitive)"""
    query = Question.query.filter(
        Question.owner_email == user_email,
        Question.text.ilike(question_text)
    )
    
    if exclude_id:
        query = query.filter(Question.id != exclude_id)
    
    return query.all()


def _get_all_duplicates_dict(questions):
    """Create a mapping of question IDs to their duplicate lists.
    
    Groups identical questions and marks all but the first (original) as duplicates.
    This prevents counting the same duplicate set multiple times.
    """
    # Group questions by their text (case-insensitive)
    text_groups = {}
    for question in questions:
        text_key = question.text.lower().strip()
        if text_key not in text_groups:
            text_groups[text_key] = []
        text_groups[text_key].append(question)
    
    duplicates_map = {}
    
    # For each group with more than 1 question, map the original question to its duplicates
    for text_key, group in text_groups.items():
        if len(group) > 1:
            # Sort by ID to keep consistent "original" (first created)
            group.sort(key=lambda q: q.id)
            original = group[0]
            duplicate_questions = group[1:]
            
            duplicates_map[original.id] = {
                'count': len(duplicate_questions),
                'ids': [d.id for d in duplicate_questions]
            }
    
    return duplicates_map


@question_bank_bp.route("/faculty/question-bank/duplicates", methods=["GET"])
def get_duplicates():
    """API endpoint to get all duplicates for current user"""
    user = session.get("user")
    user_email = user.get("email")
    
    questions = Question.query.filter_by(owner_email=user_email).all()
    duplicates_map = _get_all_duplicates_dict(questions)
    
    return {"duplicates": duplicates_map, "total_duplicates": len(duplicates_map)}, 200


@question_bank_bp.route("/faculty/question-bank/delete-duplicates/<int:q_id>", methods=["POST"])
def delete_duplicates(q_id):
    """Delete all duplicate questions for a given question ID"""
    user = session.get("user")
    user_email = user.get("email")
    
    # Get the original question
    original = Question.query.get_or_404(q_id)
    
    if original.owner_email != user_email:
        flash("Not allowed to delete these duplicates", "error")
        return redirect(url_for("qb.view_bank"))
    
    # Find all duplicates (excluding the original)
    duplicates = _get_duplicates_for_question(original.text, user_email, exclude_id=q_id)
    
    if not duplicates:
        flash("No duplicates found for this question", "info")
        return redirect(url_for("qb.view_bank"))
    
    # Delete all duplicates
    deleted_count = 0
    for dup in duplicates:
        db.session.delete(dup)
        deleted_count += 1
    
    db.session.commit()
    
    flash(f"Deleted {deleted_count} duplicate question(s)", "success")
    return redirect(url_for("qb.view_bank"))


@question_bank_bp.route("/faculty/question-bank/delete-all-duplicates", methods=["POST"])
def delete_all_duplicates():
    """Delete ALL duplicate questions for the current user"""
    user = session.get("user")
    user_email = user.get("email")
    
    questions = Question.query.filter_by(owner_email=user_email).all()
    duplicates_map = _get_all_duplicates_dict(questions)
    
    if not duplicates_map:
        flash("No duplicate questions found", "info")
        return redirect(url_for("qb.view_bank"))
    
    # Duplicate map values contain IDs to delete (non-original questions)
    ids_to_delete = set()
    for info in duplicates_map.values():
        ids_to_delete.update(info['ids'])

    deleted_count = 0
    for q_id in ids_to_delete:
        q = Question.query.get(q_id)
        if q:
            db.session.delete(q)
            deleted_count += 1
    
    db.session.commit()
    
    flash(f"Deleted {deleted_count} duplicate question(s) in total", "success")
    return redirect(url_for("qb.view_bank"))
