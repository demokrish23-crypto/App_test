from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class SessionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100))
    name = db.Column(db.String(100))
    role = db.Column(db.String(20))
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    logout_time = db.Column(db.DateTime, nullable=True)
    session_duration_seconds = db.Column(db.Integer, default=0)
    ip_address = db.Column(db.String(50))
    
    def __repr__(self):
        return f"<SessionLog {self.email} at {self.login_time}>"