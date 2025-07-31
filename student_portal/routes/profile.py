from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from student_portal.models.db import get_db
import os
from werkzeug.utils import secure_filename
import re

bp = Blueprint('profile', __name__, url_prefix='/profile')

def validate_phone(phone):
    # Remove any non-digit characters
    phone = re.sub(r'\D', '', phone)
    # Check if it's a valid Kenyan phone number
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    return bool(re.match(r'^254[7-9][0-9]{8}$', phone))

def validate_email(email):
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

@bp.route('/')
@login_required
def index():
    db = get_db()
    
    # Get student information with course details
    student_info = db.execute('''
        SELECT s.*, 
               GROUP_CONCAT(DISTINCT sc.course_code) as enrolled_courses
        FROM students s
        LEFT JOIN student_courses sc ON s.student_id = sc.student_id 
            AND sc.status = 'Active'
        WHERE s.student_id = ?
        GROUP BY s.student_id
    ''', (current_user.id,)).fetchone()
    
    return render_template('profile/index.html', student=student_info)

@bp.route('/update', methods=['POST'])
@login_required
def update():
    email = request.form.get('email')
    phone = request.form.get('phone')
    
    # Validate email
    if not validate_email(email):
        flash('Please enter a valid email address', 'error')
        return redirect(url_for('profile.index'))
    
    # Validate phone number
    if not validate_phone(phone):
        flash('Please enter a valid Kenyan phone number', 'error')
        return redirect(url_for('profile.index'))
    
    # Format phone number to standard format (254XXXXXXXXX)
    phone = re.sub(r'\D', '', phone)
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    
    db = get_db()
    
    # Update profile information
    db.execute(
        'UPDATE students SET email = ?, phone = ? WHERE student_id = ?',
        (email, phone, current_user.id)
    )
    db.commit()
    
    flash('Profile updated successfully', 'success')
    return redirect(url_for('profile.index'))

@bp.route('/update_photo', methods=['POST'])
@login_required
def update_photo():
    if 'photo' not in request.files:
        flash('No photo uploaded', 'error')
        return redirect(url_for('profile.index'))
    
    photo = request.files['photo']
    if photo.filename == '':
        flash('No photo selected', 'error')
        return redirect(url_for('profile.index'))
    
    if photo:
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profile_photos')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate secure filename with extension
        filename = secure_filename(f"student_{current_user.id}_{photo.filename}")
        filepath = os.path.join(upload_dir, filename)
        
        # Save the file
        photo.save(filepath)
        
        # Store the path relative to static directory for URL generation
        relative_path = f"uploads/profile_photos/{filename}"
        
        db = get_db()
        db.execute(
            'UPDATE students SET image_path = ? WHERE student_id = ?',
            (relative_path, current_user.id)
        )
        db.commit()
        
        flash('Profile photo updated successfully', 'success')
    
    return redirect(url_for('profile.index'))