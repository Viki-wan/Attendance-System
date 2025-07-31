from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from student_portal.models.db import get_db
from datetime import datetime

bp = Blueprint('courses', __name__, url_prefix='/courses')

@bp.route('/')
@login_required
def index():
    db = get_db()
    
    # Get enrolled classes with detailed information
    enrolled_classes = db.execute('''
        SELECT DISTINCT
            cl.class_id, 
            cl.class_name,
            c.course_code, 
            c.course_name,
            sc.semester
        FROM student_courses sc
        JOIN courses c ON sc.course_code = c.course_code
        JOIN class_courses cc ON c.course_code = cc.course_code
        JOIN classes cl ON cc.class_id = cl.class_id AND cl.semester = sc.semester
        WHERE sc.student_id = ? 
        AND sc.status = 'Active'
        ORDER BY sc.semester DESC, cl.class_name
    ''', (current_user.id,)).fetchall()
    
    return render_template('courses/index.html', classes=enrolled_classes)