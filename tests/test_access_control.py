import pytest
from app import app, db
from models.question_bank import Question
from models.paper import Paper

@pytest.fixture
def client():
    """Create test client with clean database"""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    
    with app.app_context():
        db.create_all()
        yield app.test_client()

def login_as_faculty(client):
    """Login as faculty user"""
    response = client.post("/login", data=dict(
        email="faculty1@gmail.com",
        password="1234",
        role="faculty"
    ), follow_redirects=False)  # Don't follow redirects
    # Manually follow the redirect to set session
    if response.status_code == 302:
        redirect_url = response.headers.get('Location')
        client.get(redirect_url, follow_redirects=True)
    return response

def login_as_admin(client):
    """Login as admin user"""
    response = client.post("/login", data=dict(
        email="abcd@gmail.com",
        password="1234",
        role="admin"
    ), follow_redirects=False)  # Don't follow redirects
    # Manually follow the redirect to set session
    if response.status_code == 302:
        redirect_url = response.headers.get('Location')
        client.get(redirect_url, follow_redirects=True)
    return response

def test_faculty_cannot_access_admin_routes(client):
    """Faculty attempting to access admin routes should be redirected"""
    # Login as faculty
    login_as_faculty(client)
    
    # Try to access admin dashboard
    response = client.get("/admin/dashboard", follow_redirects=False)
    assert response.status_code in [302, 404]  # Should redirect or not found
    print(f"Faculty accessing admin dashboard (no redirect): {response.status_code}")
    
    # Check if redirect happens
    response = client.get("/admin/dashboard", follow_redirects=True)
    assert "admin" not in response.request.path.lower() or response.status_code != 200
    print(f"Faculty accessing admin dashboard (with redirect): {response.status_code}")

def test_admin_cannot_access_faculty_routes(client):
    """Admin attempting to access faculty routes should be redirected"""
    # Login as admin
    login_as_admin(client)
    
    # Try to access faculty question bank
    response = client.get("/faculty/question-bank", follow_redirects=False)
    assert response.status_code in [302, 404]  # Should redirect or not found
    print(f"Admin accessing faculty question-bank (no redirect): {response.status_code}")

def test_faculty_can_access_faculty_routes(client):
    """Faculty should be able to access faculty routes"""
    # Login as faculty
    login_as_faculty(client)
    
    # Try to access faculty question bank
    response = client.get("/faculty/question-bank", follow_redirects=True)
    assert response.status_code == 200
    print(f"Faculty accessing faculty question-bank: {response.status_code}")

def test_admin_can_access_admin_routes(client):
    """Admin should be able to access admin routes"""
    # Login as admin
    login_as_admin(client)
    
    # Try to access admin dashboard
    response = client.get("/admin/dashboard", follow_redirects=True)
    assert response.status_code == 200
    print(f"Admin accessing admin dashboard: {response.status_code}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
