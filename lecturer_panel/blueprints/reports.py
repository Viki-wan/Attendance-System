from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request
from lecturer_panel.services.database_service import DatabaseService
from datetime import datetime

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')
db_service = DatabaseService()

@reports_bp.route('/view_attendance', methods=['GET', 'POST'])
def view_attendance():
    if 'instructor_id' not in session:
        return redirect(url_for('auth.login'))
    instructor_id = session['instructor_id']
    filters = {
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'end_date': datetime.now().strftime('%Y-%m-%d')
    }
    if request.method == 'POST':
        filters['start_date'] = request.form.get('start_date')
        filters['end_date'] = request.form.get('end_date')
    records = db_service.get_lecturer_attendance_report(instructor_id, filters)
    stats = {
        'total': len(records),
        'present': 0,
        'absent': 0,
        'rate': 0.0
    }
    if records:
        stats['present'] = sum(1 for r in records if r['status'] == 'Present')
        stats['absent'] = stats['total'] - stats['present']
        if stats['total'] > 0:
            stats['rate'] = (stats['present'] / stats['total']) * 100
    return render_template('reports/attendance_report.html', records=records, filters=filters, stats=stats)

@reports_bp.route('/session/report/<int:session_id>')
def session_report(session_id):
    if 'instructor_id' not in session:
        return redirect(url_for('auth.login'))
    sessions_today = db_service.get_instructor_sessions_today(session['instructor_id'])
    session_details = next((s for s in sessions_today if s['session_id'] == session_id), None)
    if not session_details:
        all_sessions = db_service.get_instructor_sessions_today(session['instructor_id'])
        session_details = next((s for s in all_sessions if s['session_id'] == session_id), None)
    if not session_details:
        return "Session not found or not assigned to you.", 404
    students = db_service.get_session_students(session_id)
    attendance = db_service.get_session_attendance(session_id)
    present_ids = {r['student_id'] for r in attendance if r['status'] == 'Present'}
    absent_ids = {s['student_id'] for s in students if s['student_id'] not in present_ids}
    present_students = [s for s in students if s['student_id'] in present_ids]
    absent_students = [s for s in students if s['student_id'] in absent_ids]
    return render_template('reports/session_report.html', session_details=session_details, present_students=present_students, absent_students=absent_students, attendance=attendance)

@reports_bp.route('/api/attendance/<int:session_id>')
def api_get_attendance(session_id):
    if 'instructor_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    attendance_records = db_service.get_session_attendance(session_id)
    return jsonify(attendance_records) 