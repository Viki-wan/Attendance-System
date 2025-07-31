from flask import Flask, render_template, redirect, url_for, flash, session, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import bcrypt
from flask_bcrypt import Bcrypt
import sqlite3
import os
from datetime import datetime, timedelta
from flask_mail import Mail

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['DATABASE'] = 'attendance.db'  # Update this path
app.config['STUDENT_IMAGES_PATH'] = 'student_images'  # Update this path
app.permanent_session_lifetime = timedelta(hours=2)  # Session timeout

# Flask-Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'victorwanguya@gmail.com'
app.config['MAIL_PASSWORD'] = 'cewv spyf tvbp tekn'  # Replace with your Gmail app password

# Initialize extensions
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)

# Import routes after app creation to avoid circular imports
from student_portal.models.student import Student
from student_portal.routes import auth, dashboard, attendance, profile, courses

# Register blueprints
app.register_blueprint(auth.bp)
app.register_blueprint(dashboard.bp)
app.register_blueprint(attendance.bp)
app.register_blueprint(profile.bp)
app.register_blueprint(courses.bp)

@login_manager.user_loader
def load_user(user_id):
    return Student.get(user_id)

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=True)