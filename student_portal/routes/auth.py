from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, current_user
from flask_bcrypt import Bcrypt
from student_portal.models.student import Student, get_db
import sqlite3
import hashlib
import re
import time
from datetime import datetime, timedelta
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

bp = Blueprint('auth', __name__)
bcrypt = Bcrypt()

# Simple in-memory login attempt tracking
# In production, use Redis or another persistent store
login_attempts = {}
lockout_duration = 300  # 5 minutes lockout

def log_activity(user_id, activity_type):
    """Log user activity to activity_log table"""
    try:
        db = get_db()
        db.execute(
            'INSERT INTO activity_log (user_id, activity_type, timestamp) VALUES (?, ?, datetime("now"))',
            (user_id, activity_type)
        )
        db.commit()
    except sqlite3.Error as e:
        print(f"Error logging activity: {e}")

class PasswordStrengthChecker:
    """Utility class to check and score password strength"""
    
    @staticmethod
    def check_strength(password):
        """
        Returns a score from 0-100 based on password strength
        and a color indicator (red, yellow, green)
        """
        score = 0
        feedback = []
        
        # Length check (up to 40 points)
        if len(password) >= 8:
            score += 20
            if len(password) >= 12:
                score += 20
        else:
            feedback.append("Password should be at least 8 characters")
            
        # Complexity checks (60 points total)
        if re.search(r'[A-Z]', password):  # Uppercase
            score += 15
        else:
            feedback.append("Add uppercase letters")
            
        if re.search(r'[a-z]', password):  # Lowercase
            score += 15
        else:
            feedback.append("Add lowercase letters")
            
        if re.search(r'[0-9]', password):  # Numbers
            score += 15
        else:
            feedback.append("Add numbers")
            
        if re.search(r'[^A-Za-z0-9]', password):  # Special chars
            score += 15
        else:
            feedback.append("Add special characters (!@#$%^&*)")
        
        # Determine color
        if score < 50:
            color = "red"
        elif score < 80:
            color = "orange"
        else:
            color = "green"
            
        return score, color, feedback

def is_locked_out(student_id):
    """Check if user is currently locked out"""
    if student_id not in login_attempts:
        return False
        
    attempts, lockout_time = login_attempts[student_id]
    
    if attempts < 3:
        return False
        
    # Check if lockout period has expired
    if lockout_time and datetime.now() > lockout_time + timedelta(seconds=lockout_duration):
        # Reset attempts after lockout period
        login_attempts[student_id] = (0, None)
        return False
        
    return True

def record_failed_attempt(student_id):
    """Record a failed login attempt"""
    if student_id not in login_attempts:
        login_attempts[student_id] = (1, None)
    else:
        attempts, _ = login_attempts[student_id]
        attempts += 1
        
        # If this is the 3rd attempt, set lockout time
        if attempts >= 3:
            login_attempts[student_id] = (attempts, datetime.now())
        else:
            login_attempts[student_id] = (attempts, None)
            
    return login_attempts[student_id]

def reset_attempts(student_id):
    """Reset failed login attempts counter"""
    if student_id in login_attempts:
        login_attempts[student_id] = (0, None)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        student_id = request.form['student_id'].strip()
        password = request.form['password'].strip()
        
        # Input validation
        if not student_id or not password:
            flash('Please enter both student ID and password', 'error')
            return render_template('auth/login.html')
            
        # Check for lockout
        if is_locked_out(student_id):
            flash('Too many failed attempts. Please try again later or reset your password.', 'error')
            log_activity(student_id, 'login_attempt_locked')
            return render_template('auth/login.html')
            
        # Get the student record
        db = get_db()
        student = db.execute('''
            SELECT s.*, sc.course_code, sc.semester 
            FROM students s
            LEFT JOIN student_courses sc ON s.student_id = sc.student_id 
            WHERE s.student_id = ? AND (sc.status = 'Active' OR sc.status IS NULL)
        ''', (student_id,)).fetchone()
        
        if student is None:
            flash('Invalid student ID or password', 'error')
            log_activity(student_id, 'login_failed_invalid_id')
            record_failed_attempt(student_id)
            return render_template('auth/login.html')
            
        stored_password = student['password']
        
        # First-time login handling
        if not stored_password or (stored_password == hashlib.sha256(student_id.encode()).hexdigest()):
            session['student_id_for_setup'] = student_id
            log_activity(student_id, 'first_time_login_attempt')
            return redirect(url_for('auth.first_time_setup'))
            
        # Regular password check
        auth_success = False
        
        if stored_password and (isinstance(stored_password, bytes) or 
                               (isinstance(stored_password, str) and stored_password.startswith('$2b$'))):
            # Bcrypt password
            if isinstance(stored_password, str):
                stored_password = stored_password.encode('utf-8')
            auth_success = bcrypt.check_password_hash(stored_password, password)
        else:
            # Legacy SHA-256 password
            hashed_input = hashlib.sha256(password.encode()).hexdigest()
            auth_success = stored_password == hashed_input
            
            # Migrate to bcrypt if successful
            if auth_success:
                try:
                    new_hash = bcrypt.generate_password_hash(password).decode('utf-8')
                    db.execute(
                        'UPDATE students SET password = ? WHERE student_id = ?',
                        (new_hash, student_id)
                    )
                    db.commit()
                except:
                    pass
                    
        if auth_success:
            user = Student.get(student_id)
            login_user(user)
            reset_attempts(student_id)
            session.permanent = True
            log_activity(student_id, 'login_successful')
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash('Invalid student ID or password', 'error')
            log_activity(student_id, 'login_failed_invalid_password')
            record_failed_attempt(student_id)
            
    return render_template('auth/login.html')

@bp.route('/first_time_setup', methods=['GET', 'POST'])
def first_time_setup():
    if 'student_id_for_setup' not in session:
        return redirect(url_for('auth.login'))
        
    student_id = session['student_id_for_setup']
    
    db = get_db()
    student = db.execute('''
        SELECT s.fname, s.lname 
        FROM students s 
        WHERE s.student_id = ?
    ''', (student_id,)).fetchone()
    
    if student is None:
        flash('Invalid student ID', 'error')
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/first_time_setup.html', 
                                 student_name=f"{student['fname']} {student['lname']}")
            
        score, _, feedback = PasswordStrengthChecker.check_strength(password)
        if score < 50:
            flash('Password is too weak: ' + ', '.join(feedback), 'error')
            return render_template('auth/first_time_setup.html', 
                                 student_name=f"{student['fname']} {student['lname']}")
            
        try:
            password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
            db.execute(
                'UPDATE students SET password = ? WHERE student_id = ?',
                (password_hash, student_id)
            )
            db.commit()
            
            session.pop('student_id_for_setup', None)
            log_activity(student_id, 'password_setup_completed')
            
            flash('Password created successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            log_activity(student_id, 'password_setup_failed')
            
    return render_template('auth/first_time_setup.html', 
                          student_name=f"{student['fname']} {student['lname']}")

@bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        if not email:
            flash('Please enter your email address', 'error')
            return render_template('auth/forgot_password.html')

        db = get_db()
        student = db.execute('''
            SELECT student_id, fname, lname, email 
            FROM students 
            WHERE LOWER(email) = ?
        ''', (email,)).fetchone()

        if student:
            # Generate token
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(student['email'], salt='password-reset-salt')
            reset_url = url_for('auth.reset_password', token=token, _external=True)

            # Send email
            msg = Message(
                subject="Password Reset Request",
                sender=current_app.config['MAIL_USERNAME'],
                recipients=[student['email']],
                body=f"Hi {student['fname']},\n\nTo reset your password, click the link below:\n{reset_url}\n\nIf you did not request this, ignore this email."
            )
            mail = current_app.extensions['mail']
            mail.send(msg)
            log_activity(student['student_id'], 'password_reset_requested')

        flash('If your email is registered, a password reset link will be sent to your email', 'info')
        return render_template('auth/forgot_password.html')

    return render_template('auth/forgot_password.html')

@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)  # 1 hour expiry
    except Exception:
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/reset_password.html')

        # Password strength check (reuse your checker)
        score, _, feedback = PasswordStrengthChecker.check_strength(password)
        if score < 50:
            flash('Password is too weak: ' + ', '.join(feedback), 'error')
            return render_template('auth/reset_password.html')

        db = get_db()
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        db.execute('UPDATE students SET password = ? WHERE LOWER(email) = ?', (password_hash, email.lower()))
        db.commit()
        flash('Your password has been reset. You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html')

@bp.route('/logout')
def logout():
    if current_user.is_authenticated:
        log_activity(current_user.id, 'logout')
    logout_user()
    return redirect(url_for('auth.login'))