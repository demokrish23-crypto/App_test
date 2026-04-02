import os
import sys
import io
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, db
from models.question_bank import Question
from models.paper import Paper, PaperQuestion


@pytest.fixture(autouse=True)
def setup_database():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def test_paper_generation_and_export():
    client = app.test_client()

    login_response = client.post(
        "/login",
        data={"email": "krishsharma23oct@gmail.com", "password": "123456", "role": "faculty"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    response = client.post(
        "/faculty/paper-generator",
        data={
            "subject": "Data Structures",
            "syllabus": "1. Arrays\n2. Linked List",
            "marks": ["2", "4"],
            "difficulty": "2"
        },
        follow_redirects=False
    )

    assert response.status_code == 302
    assert "/faculty/paper-review" in response.headers["Location"]

    review_url = response.headers["Location"]
    response = client.get(review_url)
    assert response.status_code == 200
    assert b"Review & Select Questions" in response.data

    # Pick first two generated question IDs from hidden request values
    # Simple parser: every checkbox has value=QID
    ids = []
    for line in response.data.splitlines():
        if b"select_question" in line and b"value=" in line:
            chunk = line.decode("utf-8")
            start = chunk.find('value="') + len('value="')
            end = chunk.find('"', start)
            ids.append(chunk[start:end])
            if len(ids) >= 2:
                break

    assert len(ids) >= 1
    response = client.post(review_url, data={"select_question": ids}, follow_redirects=False)
    assert response.status_code == 302
    assert "/export/" in response.headers["Location"]

    export_url = response.headers["Location"]
    response = client.get(export_url)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"


def test_question_bank_crud():
    client = app.test_client()

    login_response = client.post(
        "/login",
        data={"email": "krishsharma23oct@gmail.com", "password": "123456", "role": "faculty"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    # add question
    response = client.post(
        "/faculty/question-bank/add",
        data={"subject": "Physics", "topic": "Motion", "text": "Describe motion.", "marks": "4", "difficulty": "Medium"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Question added to bank" in response.data

    with app.app_context():
        question = Question.query.filter_by(topic="Motion").first()
        assert question is not None
        assert question.bloom_level is None or hasattr(question, 'bloom_level')
        assert question.co_level is None or hasattr(question, 'co_level')

    # edit question
    q_id = question.id
    response = client.post(
        f"/faculty/question-bank/edit/{q_id}",
        data={"subject": "Physics", "topic": "Kinematics", "text": "Describe kinematics.", "marks": "4", "difficulty": "Medium"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Question updated" in response.data

    with app.app_context():
        updated = Question.query.get(q_id)
        assert updated.topic == "Kinematics"

    # delete question
    response = client.post(f"/faculty/question-bank/delete/{q_id}", follow_redirects=True)
    assert response.status_code == 200
    assert b"Question deleted" in response.data

    with app.app_context():
        assert Question.query.get(q_id) is None


def test_advanced_question_generation_profile():
    from services.bloom_engine import generate_question

    used = set()
    question_text, bloom_level, co_level = generate_question("Machine Learning", 8, used, difficulty=5, index=0)

    assert "Machine Learning" in question_text
    assert bloom_level in {"Analyzing", "Evaluating", "Creating"}
    assert co_level.startswith("CO")
    assert len(used) == 1


def test_review_questions_filter_by_bloom_level():
    client = app.test_client()

    login_response = client.post(
        "/login",
        data={"email": "krishsharma23oct@gmail.com", "password": "123456", "role": "faculty"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    response = client.post(
        "/faculty/paper-generator",
        data={
            "subject": "Algorithms",
            "syllabus": "1. Sorting\n2. Searching",
            "marks": ["2", "4"],
            "difficulty": "2"
        },
        follow_redirects=False
    )
    assert response.status_code == 302

    with app.app_context():
        paper = Paper.query.filter_by(subject="Algorithms").first()
        assert paper is not None
        question = PaperQuestion.query.filter_by(paper_id=paper.id).first()
        assert question is not None
        bloom = question.bloom_level or "Remembering"

    response = client.get(f"/faculty/paper-review/{paper.id}?bloom={bloom}")
    assert response.status_code == 200
    assert f"value=\"{bloom}\" selected".encode() in response.data

    response_json = client.get(f"/faculty/paper-review/{paper.id}/questions?bloom={bloom}")
    assert response_json.status_code == 200
    data = response_json.get_json()
    for q in data.get("questions", []):
        assert q.get("bloom_level") == bloom

