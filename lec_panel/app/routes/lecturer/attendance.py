"""
Attendance Control Routes for Lecturers
Handles live attendance capture, manual marking, and corrections
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from datetime import datetime

from app import db
from app.models.attendance import Attendance
from app.models.student import Student
from app.services.session_service import SessionService
from app.decorators.auth import active_account_required, owns_session
from app.utils.response import success_response, error_response
from app.tasks.face_processing import preload_class_faces_task

from config.config import Config

attendance_bp = Blueprint('lecturer_attendance', __name__, url_prefix='/lecturer/attendance')
session_service = SessionService()


# ==================== LIVE ATTENDANCE ====================

@attendance_bp.route('/<int:session_id>/live')
@login_required
@active_account_required
@owns_session
def live_attendance(session_id):
    """Live attendance capture interface"""
    session = session_service.get_session_by_id(session_id)
    if not session:
        flash('Session not found', 'error')
        return redirect(url_for('lecturer_sessions.list_sessions'))
    
    if session.status != 'ongoing':
        flash('Session is not ongoing', 'error')
        return redirect(url_for('lecturer_sessions.view_session', session_id=session_id))
    
    # Get expected students
    expected_students = session_service.get_expected_students(session_id)
    
    # Get statistics
    stats = session_service.calculate_session_statistics(session_id)
    
    if Config.ENABLE_CELERY:
        try:
            from app.tasks.face_processing import preload_class_faces_task
            preload_class_faces_task.delay(session.class_id)
        except Exception as e:
            # Log error but don't break the page
            print(f"Warning: Could not queue face preloading task: {e}")
            print("Face encodings will be loaded on-demand instead")
    
    return render_template(
        'lecturer/live_attendance.html',
        session=session,
        expected_students=expected_students,
        stats=stats
    )


@attendance_bp.route('/<int:session_id>/start-capture', methods=['POST'])
@login_required
@active_account_required
@owns_session
def start_capture(session_id):
    """Start face recognition capture"""
    session = session_service.get_session_by_id(session_id)
    if not session:
        return jsonify(error_response('Session not found')), 404
    
    if session.status != 'ongoing':
        return jsonify(error_response('Session is not ongoing')), 400
    
    # Register session for camera service
    from app.services.camera_service import CameraService
    camera_service = CameraService()
    
    success = camera_service.register_session(
        session_id=session_id,
        user_id=current_user.instructor_id
    )
    
    if success:
        return jsonify(success_response(
            message='Face recognition started',
            data={'session_id': session_id}
        ))
    else:
        return jsonify(error_response('Failed to start capture')), 500


@attendance_bp.route('/<int:session_id>/stop-capture', methods=['POST'])
@login_required
@active_account_required
@owns_session
def stop_capture(session_id):
    """Stop face recognition capture"""
    from app.services.camera_service import CameraService
    camera_service = CameraService()
    
    camera_service.unregister_session(session_id)
    
    return jsonify(success_response(message='Face recognition stopped'))

# ==================== SESSION MANAGEMENT ====================

@attendance_bp.route('/<int:session_id>/end', methods=['POST'])
@login_required
@active_account_required
@owns_session
def end_session(session_id):
    """End an attendance session and finalize attendance records"""
    try:
        session = session_service.get_session_by_id(session_id)
        if not session:
            flash('Session not found', 'error')
            return redirect(url_for('lecturer_sessions.list_sessions'))
        
        # Validate session status
        if session.status == 'completed':
            flash('Session already completed', 'info')
            return redirect(url_for('lecturer_sessions.view_session', session_id=session_id))
        
        # Get optional notes from form
        notes = request.form.get('notes', '')
        
        # Mark all unmarked students as absent
        expected_students = session_service.get_expected_students(session_id)
        unmarked_count = 0
        
        for student in expected_students:
            if student['attendance_status'] == 'Absent' and not student.get('attendance_time'):
                # Student was never marked, ensure they have an attendance record
                attendance = Attendance.query.filter_by(
                    session_id=session_id,
                    student_id=student['student_id']
                ).first()
                
                if not attendance:
                    attendance = Attendance(
                        session_id=session_id,
                        student_id=student['student_id'],
                        status='Absent',
                        marked_by=current_user.instructor_id,
                        method='auto',
                        timestamp=datetime.now()
                    )
                    db.session.add(attendance)
                    unmarked_count += 1
        
        # Update session status
        session.status = 'completed'
        session.actual_end_time = datetime.now()
        
        if notes:
            if session.notes:
                session.notes += f'\n{notes}'
            else:
                session.notes = notes
        
        db.session.commit()
        
        # Log activity
        from app.models.activity_log import ActivityLog
        log = ActivityLog(
            user_id=current_user.instructor_id,
            user_type='instructor',
            activity_type='session_ended',
            description=f'Ended session {session_id}. {unmarked_count} students auto-marked as absent.'
        )
        db.session.add(log)
        db.session.commit()
        
        # Stop camera service if active
        try:
            from app.services.camera_service import CameraService
            camera_service = CameraService()
            camera_service.unregister_session(session_id)
        except Exception as e:
            print(f"Warning: Could not unregister camera service: {e}")
        
        flash(f'Session ended successfully. {unmarked_count} students marked as absent.', 'success')
        return redirect(url_for('lecturer_sessions.view_session', session_id=session_id))
        
    except Exception as e:
        db.session.rollback()
        print(f'Error ending session: {str(e)}')
        flash('Failed to end session', 'error')
        return redirect(url_for('lecturer_attendance.live_attendance', session_id=session_id))


@attendance_bp.route('/<int:session_id>/sync', methods=['GET'])
@login_required
@active_account_required
@owns_session
def sync_data(session_id):
    """Sync and return current session statistics"""
    try:
        stats = session_service.calculate_session_statistics(session_id)
        return jsonify(success_response(data=stats))
    except Exception as e:
        return jsonify(error_response(str(e))), 500


@attendance_bp.route('/<int:session_id>/mark-unmarked-absent', methods=['POST'])
@login_required
@active_account_required
@owns_session
def mark_unmarked_absent(session_id):
    """Mark all unmarked students as absent"""
    try:
        expected_students = session_service.get_expected_students(session_id)
        count = 0
        
        for student in expected_students:
            if student['attendance_status'] == 'Absent' and not student.get('attendance_time'):
                attendance = Attendance.query.filter_by(
                    session_id=session_id,
                    student_id=student['student_id']
                ).first()
                
                if not attendance:
                    attendance = Attendance(
                        session_id=session_id,
                        student_id=student['student_id'],
                        status='Absent',
                        marked_by=current_user.instructor_id,
                        method='manual',
                        timestamp=datetime.now()
                    )
                    db.session.add(attendance)
                    count += 1
        
        db.session.commit()
        
        # Update statistics
        stats = session_service.calculate_session_statistics(session_id)
        
        return jsonify(success_response(
            message=f'{count} students marked as absent',
            data={'count': count, 'stats': stats}
        ))
        
    except Exception as e:
        db.session.rollback()
        return jsonify(error_response(str(e))), 500


@attendance_bp.route('/<int:session_id>/export')
@login_required
@active_account_required
@owns_session
def export_attendance(session_id):
    """Export attendance data (supports multiple formats)"""
    format_type = request.args.get('format', 'csv').lower()
    
    if format_type == 'csv':
        return export_csv(session_id)
    else:
        flash('Invalid export format', 'error')
        return redirect(url_for('lecturer_attendance.live_attendance', session_id=session_id))

@attendance_bp.route('/mark/<int:session_id>', methods=['POST'])
@login_required
@active_account_required
@owns_session
def mark_attendance(session_id):
    """Mark attendance (alias for manual_mark for backward compatibility)"""
    data = request.get_json()
    
    student_id = data.get('student_id')
    status = data.get('status')
    notes = data.get('notes', '')
    method = data.get('method', 'manual')
    
    if not student_id or not status:
        return jsonify(error_response('Missing required fields')), 400
    
    if status not in ['Present', 'Absent', 'Late', 'Excused']:
        return jsonify(error_response('Invalid status')), 400
    
    # Get student name for response
    student = Student.query.get(student_id)
    if not student:
        return jsonify(error_response('Student not found')), 404
    
    # Get or create attendance record
    attendance = Attendance.query.filter_by(
        session_id=session_id,
        student_id=student_id
    ).first()
    
    if not attendance:
        attendance = Attendance(
            session_id=session_id,
            student_id=student_id
        )
        db.session.add(attendance)
    
    # Update attendance
    attendance.status = status
    attendance.marked_by = current_user.instructor_id
    attendance.method = method
    attendance.timestamp = datetime.now()
    
    if notes:
        attendance.notes = notes
    
    try:
        db.session.commit()
        
        # Update statistics
        stats = session_service.calculate_session_statistics(session_id)
        
        return jsonify(success_response(
            message=f'{student.fname} {student.lname} marked as {status}',
            data={
                'success': True,
                'student_id': student_id,
                'student_name': f'{student.fname} {student.lname}',
                'status': status,
                'method': method,
                'stats': stats
            }
        ))
    except Exception as e:
        db.session.rollback()
        return jsonify(error_response(f'Failed to mark attendance: {str(e)}')), 500


# ==================== MANUAL ATTENDANCE MARKING ====================

@attendance_bp.route('/<int:session_id>/manual-mark', methods=['POST'])
@login_required
@active_account_required
@owns_session
def manual_mark(session_id):
    """Manually mark attendance for a student"""
    data = request.get_json()
    
    student_id = data.get('student_id')
    status = data.get('status')  # 'Present', 'Absent', 'Late', 'Excused'
    notes = data.get('notes', '')
    
    if not student_id or not status:
        return jsonify(error_response('Missing required fields')), 400
    
    if status not in ['Present', 'Absent', 'Late', 'Excused']:
        return jsonify(error_response('Invalid status')), 400
    
    # Get or create attendance record
    attendance = Attendance.query.filter_by(
        session_id=session_id,
        student_id=student_id
    ).first()
    
    if not attendance:
        attendance = Attendance(
            session_id=session_id,
            student_id=student_id
        )
        db.session.add(attendance)
    
    # Update attendance
    old_status = attendance.status
    attendance.status = status
    attendance.marked_by = current_user.instructor_id
    attendance.method = 'manual'
    attendance.timestamp = datetime.now()
    
    if notes:
        attendance.notes = notes
    
    try:
        db.session.commit()
        
        # Log activity
        from app.models.activity_log import ActivityLog
        log = ActivityLog(
            user_id=current_user.instructor_id,
            user_type='instructor',
            activity_type='attendance_manual_mark',
            description=f'Manually marked {student_id} as {status} for session {session_id}'
        )
        db.session.add(log)
        db.session.commit()
        
        # Update session statistics
        stats = session_service.calculate_session_statistics(session_id)
        
        return jsonify(success_response(
            message=f'Student marked as {status}',
            data={
                'student_id': student_id,
                'status': status,
                'old_status': old_status,
                'stats': stats
            }
        ))
    except Exception as e:
        db.session.rollback()
        return jsonify(error_response(f'Failed to mark attendance: {str(e)}')), 500


@attendance_bp.route('/<int:session_id>/bulk-mark', methods=['POST'])
@login_required
@active_account_required
@owns_session
def bulk_mark(session_id):
    """Bulk mark multiple students"""
    data = request.get_json()
    
    student_ids = data.get('student_ids', [])
    status = data.get('status')
    notes = data.get('notes', '')
    
    if not student_ids or not status:
        return jsonify(error_response('Missing required fields')), 400
    
    if status not in ['Present', 'Absent', 'Late', 'Excused']:
        return jsonify(error_response('Invalid status')), 400
    
    updated_count = 0
    errors = []
    
    for student_id in student_ids:
        # Get or create attendance record
        attendance = Attendance.query.filter_by(
            session_id=session_id,
            student_id=student_id
        ).first()
        
        if not attendance:
            attendance = Attendance(
                session_id=session_id,
                student_id=student_id
            )
            db.session.add(attendance)
        
        attendance.status = status
        attendance.marked_by = current_user.instructor_id
        attendance.method = 'manual_bulk'
        attendance.timestamp = datetime.now()
        
        if notes:
            attendance.notes = notes
        
        updated_count += 1
    
    try:
        db.session.commit()
        
        # Log activity
        from app.models.activity_log import ActivityLog
        log = ActivityLog(
            user_id=current_user.instructor_id,
            user_type='instructor',
            activity_type='attendance_bulk_mark',
            description=f'Bulk marked {updated_count} students as {status} for session {session_id}'
        )
        db.session.add(log)
        db.session.commit()
        
        # Update statistics
        stats = session_service.calculate_session_statistics(session_id)
        
        return jsonify(success_response(
            message=f'Successfully marked {updated_count} students as {status}',
            data={'updated_count': updated_count, 'stats': stats}
        ))
    except Exception as e:
        db.session.rollback()
        return jsonify(error_response(f'Failed to bulk mark: {str(e)}')), 500


# ==================== ATTENDANCE CORRECTIONS ====================

@attendance_bp.route('/<int:session_id>/correct', methods=['GET', 'POST'])
@login_required
@active_account_required
@owns_session
def correct_attendance(session_id):
    """Correct attendance records after session"""
    session = session_service.get_session_by_id(session_id)
    if not session:
        flash('Session not found', 'error')
        return redirect(url_for('lecturer_sessions.list_sessions'))
    
    if request.method == 'GET':
        # Display correction interface
        expected_students = session_service.get_expected_students(session_id)
        stats = session_service.calculate_session_statistics(session_id)
        
        return render_template(
            'lecturer/correct_attendance.html',
            session=session,
            expected_students=expected_students,
            stats=stats
        )
    
    # POST - Save corrections
    corrections = request.form.getlist('corrections')  # Format: "student_id:status"
    
    corrected_count = 0
    
    for correction in corrections:
        try:
            student_id, status = correction.split(':')
            
            attendance = Attendance.query.filter_by(
                session_id=session_id,
                student_id=student_id
            ).first()
            
            if attendance and attendance.status != status:
                attendance.status = status
                attendance.marked_by = current_user.instructor_id
                attendance.method = 'correction'
                if not attendance.notes:
                    attendance.notes = ''
                attendance.notes += f'\n[Corrected on {datetime.now()}]'
                corrected_count += 1
        except ValueError:
            continue
    
    try:
        db.session.commit()
        
        # Log activity
        from app.models.activity_log import ActivityLog
        log = ActivityLog(
            user_id=current_user.instructor_id,
            user_type='instructor',
            activity_type='attendance_corrected',
            description=f'Corrected {corrected_count} attendance records for session {session_id}'
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Successfully corrected {corrected_count} attendance records', 'success')
        return redirect(url_for('lecturer_sessions.view_session', session_id=session_id))
    except Exception as e:
        db.session.rollback()
        flash('Failed to save corrections', 'error')
        return redirect(url_for('lecturer_attendance.correct_attendance', session_id=session_id))


@attendance_bp.route('/<int:session_id>/add-note', methods=['POST'])
@login_required
@active_account_required
@owns_session
def add_note(session_id):
    """Add note to attendance record"""
    data = request.get_json()
    
    student_id = data.get('student_id')
    note = data.get('note')
    
    if not student_id or not note:
        return jsonify(error_response('Missing required fields')), 400
    
    attendance = Attendance.query.filter_by(
        session_id=session_id,
        student_id=student_id
    ).first()
    
    if not attendance:
        return jsonify(error_response('Attendance record not found')), 404
    
    # Append note
    if attendance.notes:
        attendance.notes += f'\n{note}'
    else:
        attendance.notes = note
    
    try:
        db.session.commit()
        return jsonify(success_response(
            message='Note added successfully',
            data={'notes': attendance.notes}
        ))
    except Exception as e:
        db.session.rollback()
        return jsonify(error_response(f'Failed to add note: {str(e)}')), 500


# ==================== ATTENDANCE STATISTICS ====================

@attendance_bp.route('/<int:session_id>/stats')
@login_required
@active_account_required
@owns_session
def get_stats(session_id):
    """Get real-time attendance statistics"""
    stats = session_service.calculate_session_statistics(session_id)
    return jsonify(success_response(data=stats))


@attendance_bp.route('/<int:session_id>/students-status')
@login_required
@active_account_required
@owns_session
def get_students_status(session_id):
    """Get current status of all expected students"""
    expected_students = session_service.get_expected_students(session_id)
    
    return jsonify(success_response(data={
        'students': expected_students,
        'total': len(expected_students),
        'timestamp': datetime.now().isoformat()
    }))


@attendance_bp.route('/<int:session_id>/absent-students')
@login_required
@active_account_required
@owns_session
def get_absent_students(session_id):
    """Get list of absent students"""
    expected_students = session_service.get_expected_students(session_id)
    absent = [s for s in expected_students if s['attendance_status'] == 'Absent']
    
    return jsonify(success_response(data={
        'absent_students': absent,
        'count': len(absent)
    }))


@attendance_bp.route('/<int:session_id>/present-students')
@login_required
@active_account_required
@owns_session
def get_present_students(session_id):
    """Get list of present/late students"""
    expected_students = session_service.get_expected_students(session_id)
    present = [s for s in expected_students if s['attendance_status'] in ['Present', 'Late']]
    
    return jsonify(success_response(data={
        'present_students': present,
        'count': len(present)
    }))


# ==================== STUDENT INFORMATION ====================

@attendance_bp.route('/student/<string:student_id>/info')
@login_required
@active_account_required
def get_student_info(student_id):
    """Get detailed student information"""
    student = Student.query.get(student_id)
    if not student:
        return jsonify(error_response('Student not found')), 404
    
    # Get student's attendance history
    from sqlalchemy import func
    attendance_stats = db.session.query(
        func.count(Attendance.id).label('total_sessions'),
        func.sum(
            db.case((Attendance.status.in_(['Present', 'Late']), 1), else_=0)
        ).label('attended'),
        func.sum(
            db.case((Attendance.status == 'Present', 1), else_=0)
        ).label('on_time'),
        func.sum(
            db.case((Attendance.status == 'Late', 1), else_=0)
        ).label('late')
    ).filter(
        Attendance.student_id == student_id
    ).first()
    
    return jsonify(success_response(data={
        'student_id': student.student_id,
        'name': f'{student.fname} {student.lname}',
        'email': student.email,
        'phone': student.phone,
        'course': student.course,
        'year_of_study': student.year_of_study,
        'image_path': student.image_path,
        'has_face_encoding': student.face_encoding is not None,
        'stats': {
            'total_sessions': attendance_stats.total_sessions or 0,
            'attended': attendance_stats.attended or 0,
            'on_time': attendance_stats.on_time or 0,
            'late': attendance_stats.late or 0,
            'attendance_rate': round(
                (attendance_stats.attended / attendance_stats.total_sessions * 100) 
                if attendance_stats.total_sessions else 0, 
                2
            )
        }
    }))


@attendance_bp.route('/<int:session_id>/mark-all-present', methods=['POST'])
@login_required
@active_account_required
@owns_session
def mark_all_present(session_id):
    """Quick action: Mark all students as present"""
    expected_students = session_service.get_expected_students(session_id)
    student_ids = [s['student_id'] for s in expected_students]
    
    return bulk_mark(session_id)  # Reuse bulk_mark logic


@attendance_bp.route('/<int:session_id>/mark-all-absent', methods=['POST'])
@login_required
@active_account_required
@owns_session
def mark_all_absent(session_id):
    """Quick action: Mark all students as absent"""
    # This is typically used when cancelling a session
    db.session.execute(
        db.text("""
            UPDATE attendance 
            SET status = 'Absent', 
                method = 'manual_bulk',
                marked_by = :instructor_id,
                timestamp = CURRENT_TIMESTAMP
            WHERE session_id = :session_id
        """),
        {
            'session_id': session_id,
            'instructor_id': current_user.instructor_id
        }
    )
    
    try:
        db.session.commit()
        
        # Update statistics
        stats = session_service.calculate_session_statistics(session_id)
        
        return jsonify(success_response(
            message='All students marked as absent',
            data={'stats': stats}
        ))
    except Exception as e:
        db.session.rollback()
        return jsonify(error_response(f'Failed to mark all absent: {str(e)}')), 500


# ==================== EXPORT ====================

@attendance_bp.route('/<int:session_id>/export-csv')
@login_required
@active_account_required
@owns_session
def export_csv(session_id):
    """Export session attendance as CSV"""
    import csv
    from io import StringIO
    from flask import make_response
    
    session = session_service.get_session_by_id(session_id)
    if not session:
        flash('Session not found', 'error')
        return redirect(url_for('lecturer_sessions.list_sessions'))
    
    expected_students = session_service.get_expected_students(session_id)
    
    # Generate CSV
    si = StringIO()
    writer = csv.writer(si)
    
    # Header
    writer.writerow([
        'Student ID', 'Name', 'Email', 'Status', 
        'Time Marked', 'Method', 'Confidence Score', 'Notes'
    ])
    
    # Data rows
    for student in expected_students:
        writer.writerow([
            student['student_id'],
            student['name'],
            student['email'],
            student['attendance_status'],
            student['attendance_time'] or 'N/A',
            'Face Recognition' if student['confidence_score'] else 'Manual',
            student['confidence_score'] or 'N/A',
            ''  # Notes can be added from attendance record if needed
        ])
    
    # Create response
    output = make_response(si.getvalue())
    output.headers['Content-Disposition'] = f'attachment; filename=session_{session_id}_attendance.csv'
    output.headers['Content-type'] = 'text/csv'
    
    return output