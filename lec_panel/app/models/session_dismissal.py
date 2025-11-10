"""
Session Dismissal Model
Tracks dismissed/cancelled sessions with rescheduling information
"""

from datetime import datetime
from app import db


class SessionDismissal(db.Model):
    __tablename__ = 'session_dismissals'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_sessions.session_id'), nullable=False)
    instructor_id = db.Column(db.String, db.ForeignKey('instructors.instructor_id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    dismissal_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    rescheduled_to = db.Column(db.Date, nullable=True)
    rescheduled_time = db.Column(db.String, nullable=True)
    notes = db.Column(db.Text)
    status = db.Column(db.String, default='dismissed')  # 'dismissed', 'rescheduled', 'cancelled'
    
    # Relationships
    session = db.relationship(
        'ClassSession', 
        back_populates='dismissal'  # Use singular, not plural
    )
    
    instructor = db.relationship(
        'Instructor', 
        back_populates='session_dismissals'
    )
    
    def __repr__(self):
        return f'<SessionDismissal session_id={self.session_id} status={self.status}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'instructor_id': self.instructor_id,
            'reason': self.reason,
            'dismissal_time': self.dismissal_time.isoformat() if self.dismissal_time else None,
            'rescheduled_to': self.rescheduled_to.isoformat() if self.rescheduled_to else None,
            'rescheduled_time': self.rescheduled_time,
            'notes': self.notes,
            'status': self.status
        }