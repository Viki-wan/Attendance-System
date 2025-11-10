"""
Session Management Routes for Lecturers
Handles all session CRUD operations, filtering, and lifecycle management
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app.services.session_service import SessionService
from app.decorators.auth import active_account_required, owns_session
from app.utils.response import success_response, error_response
from app import db


sessions_bp = Blueprint('lecturer_sessions', __name__, url_prefix='/lecturer/sessions')
session_service = SessionService()


# ==================== SESSION LISTING & FILTERING ====================

@sessions_bp.route('/')
@login_required
@active_account_required
def list_sessions():
    """Display all sessions for the instructor with filters - semester aware"""
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', None)
    class_id = request.args.get('class_id', None)
    date_from = request.args.get('date_from', None)
    date_to = request.args.get('date_to', None)
    
    # Build filters
    filters = {}
    if status:
        filters['status'] = status
    if class_id:
        filters['class_id'] = class_id
    if date_from:
        filters['date_from'] = date_from
    if date_to:
        filters['date_to'] = date_to
    
    # Get sessions (now automatically filtered by current semester)
    sessions, total_count = session_service.get_instructor_sessions(
        instructor_id=current_user.instructor_id,
        filters=filters,
        page=page,
        per_page=per_page
    )
    
    # Get instructor's classes for current semester only
    instructor_classes = session_service.get_instructor_classes_for_current_semester(
        current_user.instructor_id
    )
    
    # Get current semester info
    current_semester = session_service.get_current_semester()
    is_in_semester = session_service.is_in_semester()
    
    # Calculate pagination
    total_pages = (total_count + per_page - 1) // per_page
    
    return render_template(
        'lecturer/sessions.html',
        sessions=sessions,
        instructor_classes=instructor_classes,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_count=total_count,
        current_semester=current_semester,
        is_in_semester=is_in_semester,
        filters={
            'status': status,
            'class_id': class_id,
            'date_from': date_from,
            'date_to': date_to
        }
    )



@sessions_bp.route('/upcoming')
@login_required
@active_account_required
def upcoming_sessions():
    """Get upcoming sessions for quick view"""
    days_ahead = request.args.get('days', 7, type=int)
    
    sessions = session_service.get_upcoming_sessions(
        instructor_id=current_user.instructor_id,
        days_ahead=days_ahead
    )
    
    # Group sessions by date
    from collections import defaultdict
    sessions_by_date = defaultdict(list)
    for session in sessions:
        # Handle both date objects and date strings
        if hasattr(session.date, 'isoformat'):
            date_str = session.date.isoformat()
        else:
            date_str = str(session.date)
        sessions_by_date[date_str].append(session)
    
    # Sort dates
    sorted_dates = sorted(sessions_by_date.keys())
    
    return render_template(
        'lecturer/upcoming_sessions.html',
        sessions=sessions,
        sessions_by_date=dict(sessions_by_date),
        sorted_dates=sorted_dates,
        days_ahead=days_ahead
    )

@sessions_bp.route('/debug/upcoming')
@login_required
@active_account_required
def debug_upcoming():
    """Debug route to check upcoming sessions"""
    from datetime import datetime, timedelta
    from sqlalchemy import text
    
    today = datetime.now().date()
    end_date = today + timedelta(days=7)
    current_semester = SessionService.get_current_semester()
    
    # Test 1: Raw query WITHOUT semester filter
    raw_all = db.session.execute(
        text("""
            SELECT 
                s.session_id, 
                s.class_id, 
                s.date, 
                s.start_time, 
                s.status,
                c.semester,
                c.class_name
            FROM class_sessions s
            JOIN classes c ON s.class_id = c.class_id
            JOIN class_instructors ci ON c.class_id = ci.class_id
            WHERE ci.instructor_id = :instructor_id
            AND s.date >= :today
            AND s.date <= :end_date
            ORDER BY s.date, s.start_time
        """),
        {
            'instructor_id': current_user.instructor_id,
            'today': today.isoformat(),
            'end_date': end_date.isoformat()
        }
    ).fetchall()
    
    # Test 2: Raw query WITH semester filter
    raw_semester = db.session.execute(
        text("""
            SELECT 
                s.session_id, 
                s.class_id, 
                s.date, 
                s.start_time, 
                s.status,
                c.semester,
                c.class_name
            FROM class_sessions s
            JOIN classes c ON s.class_id = c.class_id
            JOIN class_instructors ci ON c.class_id = ci.class_id
            WHERE ci.instructor_id = :instructor_id
            AND s.date >= :today
            AND s.date <= :end_date
            AND c.semester = :semester
            ORDER BY s.date, s.start_time
        """),
        {
            'instructor_id': current_user.instructor_id,
            'today': today.isoformat(),
            'end_date': end_date.isoformat(),
            'semester': current_semester
        }
    ).fetchall()
    
    # Test 3: Check all sessions for instructor (no date filter)
    all_instructor_sessions = db.session.execute(
        text("""
            SELECT 
                s.session_id, 
                s.date, 
                s.status,
                c.semester,
                c.class_name
            FROM class_sessions s
            JOIN classes c ON s.class_id = c.class_id
            JOIN class_instructors ci ON c.class_id = ci.class_id
            WHERE ci.instructor_id = :instructor_id
            ORDER BY s.date DESC
            LIMIT 20
        """),
        {'instructor_id': current_user.instructor_id}
    ).fetchall()
    
    # Test 4: Get sessions through service
    sessions = session_service.get_upcoming_sessions(
        instructor_id=current_user.instructor_id,
        days_ahead=7
    )
    
    debug_info = {
        'current_user_id': current_user.instructor_id,
        'current_semester': current_semester,
        'current_month': datetime.now().month,
        'is_in_semester': SessionService.is_in_semester(),
        'today': today.isoformat(),
        'end_date': end_date.isoformat(),
        'counts': {
            'raw_all_sessions': len(raw_all),
            'raw_semester_filtered': len(raw_semester),
            'all_instructor_sessions': len(all_instructor_sessions),
            'service_sessions': len(sessions)
        },
        'raw_all_sessions': [
            {
                'id': r[0],
                'class': r[1],
                'date': str(r[2]),
                'time': str(r[3]),
                'status': r[4],
                'semester': r[5],
                'class_name': r[6]
            } for r in raw_all
        ],
        'raw_semester_sessions': [
            {
                'id': r[0],
                'class': r[1],
                'date': str(r[2]),
                'time': str(r[3]),
                'status': r[4],
                'semester': r[5],
                'class_name': r[6]
            } for r in raw_semester
        ],
        'all_instructor_sessions_sample': [
            {
                'id': r[0],
                'date': str(r[1]),
                'status': r[2],
                'semester': r[3],
                'class_name': r[4]
            } for r in all_instructor_sessions
        ],
        'service_sessions': [
            {
                'id': s.session_id,
                'class': s.class_id,
                'date': str(s.date),
                'status': s.status,
                'semester': s.class_.semester if hasattr(s, 'class_') and s.class_ else 'N/A'
            } for s in sessions
        ]
    }
    
    return jsonify(debug_info)
    
@sessions_bp.route('/today')
@login_required
@active_account_required
def todays_sessions():
    """Get today's sessions"""
    sessions = session_service.get_todays_sessions(current_user.instructor_id)
    
    # Add eligibility status to each session
    for session in sessions:
        session.eligibility = session_service.get_session_eligibility_status(
            session.session_id
        )
    
    return render_template(
        'lecturer/todays_session.html',
        sessions=sessions
    )


# ==================== SESSION DETAILS ====================

@sessions_bp.route('/<int:session_id>')
@login_required
@active_account_required
@owns_session
def view_session(session_id):
    """View detailed session information"""
    session = session_service.get_session_by_id(session_id)
    if not session:
        flash('Session not found', 'error')
        return redirect(url_for('lecturer_sessions.list_sessions'))
    
    # Get statistics
    stats = session_service.calculate_session_statistics(session_id)
    
    # Get expected students
    expected_students = session_service.get_expected_students(session_id)
    
    # Get eligibility status
    eligibility = session_service.get_session_eligibility_status(session_id)
    
    # Get dismissal info if dismissed
    dismissal = None
    if session.status == 'dismissed':
        from app.models.session_dismissal import SessionDismissal
        dismissal = SessionDismissal.query.filter_by(
            session_id=session_id
        ).order_by(SessionDismissal.dismissal_time.desc()).first()
    
    return render_template(
        'lecturer/session_detail.html',
        session=session,
        stats=stats,
        expected_students=expected_students,
        eligibility=eligibility,
        dismissal=dismissal
    )


# ==================== SESSION CREATION ====================


@sessions_bp.route('/bulk-create', methods=['GET', 'POST'])
@login_required
@active_account_required
def bulk_create_sessions():
    """Auto-generate sessions from timetable for current semester"""
    if request.method == 'GET':
        # Get instructor's classes for current semester
        instructor_classes = session_service.get_instructor_classes_for_current_semester(
            current_user.instructor_id
        )
        
        current_semester = session_service.get_current_semester()
        is_in_semester = session_service.is_in_semester()
        
        return render_template(
            'lecturer/bulk_create_sessions.html',
            instructor_classes=instructor_classes,
            current_semester=current_semester,
            is_in_semester=is_in_semester
        )
    
    # POST - Generate sessions
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    class_id = request.form.get('class_id')  # Optional - None = all classes
    
    if not start_date or not end_date:
        flash('Start and end dates are required', 'error')
        return redirect(url_for('lecturer_sessions.bulk_create_sessions'))
    
    # Parse dates
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format', 'error')
        return redirect(url_for('lecturer_sessions.bulk_create_sessions'))
    
    # Validate dates are in active semester periods
    if not session_service.is_in_semester(start) or not session_service.is_in_semester(end):
        flash('Date range includes holiday period (May-August). Sessions will only be created for active semester periods.', 'warning')
    
    # Generate sessions (will automatically skip holiday periods)
    created_count, errors = session_service.create_sessions_from_timetable(
        start_date=start,
        end_date=end,
        class_id=class_id if class_id else None,
        instructor_id=current_user.instructor_id
    )
    
    if created_count > 0:
        flash(f'Successfully created {created_count} sessions', 'success')
    
    if errors:
        for error in errors[:5]:  # Show first 5 errors
            flash(error, 'warning')
    
    if created_count == 0 and not errors:
        flash('No sessions were created. Check your timetable and date range.', 'info')
    
    return redirect(url_for('lecturer_sessions.list_sessions'))


# ==================== SESSION LIFECYCLE ====================

@sessions_bp.route('/<int:session_id>/start', methods=['POST'])
@login_required
@active_account_required
@owns_session
def start_session(session_id):
    """Start a session (begin attendance capture)"""
    success, message = session_service.start_session(
        session_id=session_id,
        instructor_id=current_user.instructor_id
    )
    
    if success:
        flash(message, 'success')
        return redirect(url_for('lecturer_attendance.live_attendance', session_id=session_id))
    else:
        flash(message, 'error')
        return redirect(url_for('lecturer_sessions.view_session', session_id=session_id))


@sessions_bp.route('/<int:session_id>/end', methods=['POST'])
@login_required
@active_account_required
@owns_session
def end_session(session_id):
    """End a session and finalize attendance"""
    notes = request.form.get('notes', '')
    
    success, message = session_service.end_session(
        session_id=session_id,
        instructor_id=current_user.instructor_id,
        notes=notes
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if success:
            return jsonify(success_response(message=message))
        else:
            return jsonify(error_response(message)), 400
    
    flash(message, 'success' if success else 'error')
    return redirect(url_for('lecturer_sessions.view_session', session_id=session_id))



@sessions_bp.route('/<int:session_id>/dismiss', methods=['GET', 'POST'])
@login_required
@active_account_required
@owns_session
def dismiss_session(session_id):
    """Dismiss/cancel a session with optional rescheduling"""
    if request.method == 'GET':
        session = session_service.get_session_by_id(session_id)
        if not session:
            flash('Session not found', 'error')
            return redirect(url_for('lecturer_sessions.list_sessions'))
        
        # Get suggested reschedule dates
        suggestions = session_service.suggest_reschedule_dates(session_id)
        
        return render_template(
            'lecturer/dismiss_session.html',
            session=session,
            suggestions=suggestions
        )
    
    # POST - Process dismissal
    reason = request.form.get('reason')
    reschedule_date = request.form.get('reschedule_date')
    reschedule_time = request.form.get('reschedule_time')
    
    if not reason:
        flash('Reason is required', 'error')
        return redirect(url_for('lecturer_sessions.dismiss_session', session_id=session_id))
    
    # Convert time format
    if reschedule_time and len(reschedule_time) == 5:
        reschedule_time += ':00'
    
    success, message = session_service.dismiss_session(
        session_id=session_id,
        instructor_id=current_user.instructor_id,
        reason=reason,
        reschedule_date=reschedule_date if reschedule_date else None,
        reschedule_time=reschedule_time if reschedule_time else None
    )
    
    flash(message, 'success' if success else 'error')
    return redirect(url_for('lecturer_sessions.list_sessions'))


@sessions_bp.route('/<int:session_id>/update', methods=['GET', 'POST'])
@login_required
@active_account_required
@owns_session
def update_session(session_id):
    """Update session details"""
    session = session_service.get_session_by_id(session_id)
    if not session:
        flash('Session not found', 'error')
        return redirect(url_for('lecturer_sessions.list_sessions'))
    
    if session.status in ['completed', 'cancelled']:
        flash(f'Cannot update {session.status} session', 'error')
        return redirect(url_for('lecturer_sessions.view_session', session_id=session_id))
    
    if request.method == 'GET':
        return render_template(
            'lecturer/update_session.html',
            session=session
        )
    
    # POST - Update session
    date = request.form.get('date')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    notes = request.form.get('notes')
    
    # Convert time format
    if start_time and len(start_time) == 5:
        start_time += ':00'
    if end_time and len(end_time) == 5:
        end_time += ':00'
    
    # Check for conflicts if time/date changed
    if date != session.date or start_time != session.start_time or end_time != session.end_time:
        has_conflict, conflict_msg = session_service.check_session_conflicts(
            class_id=session.class_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            instructor_id=current_user.instructor_id,
            exclude_session_id=session_id
        )
        
        if has_conflict:
            flash(conflict_msg, 'error')
            return redirect(url_for('lecturer_sessions.update_session', session_id=session_id))
    
    # Update session
    session.date = date
    session.start_time = start_time
    session.end_time = end_time
    if notes:
        session.session_notes = notes
    
    try:
        from app import db
        db.session.commit()
        flash('Session updated successfully', 'success')
        return redirect(url_for('lecturer_sessions.view_session', session_id=session_id))
    except Exception as e:
        db.session.rollback()
        flash('Failed to update session', 'error')
        return redirect(url_for('lecturer_sessions.update_session', session_id=session_id))


@sessions_bp.route('/<int:session_id>/delete', methods=['POST'])
@login_required
@active_account_required
@owns_session
def delete_session(session_id):
    """Delete a session (soft delete - mark as cancelled)"""
    session = session_service.get_session_by_id(session_id)
    if not session:
        return jsonify(error_response('Session not found')), 404
    
    if session.status in ['ongoing', 'completed']:
        return jsonify(error_response(f'Cannot delete {session.status} session')), 400
    
    # Mark as cancelled
    session.status = 'cancelled'
    
    try:
        from app import db
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success_response(message='Session cancelled successfully'))
        
        flash('Session cancelled successfully', 'success')
        return redirect(url_for('lecturer_sessions.list_sessions'))
    except Exception as e:
        db.session.rollback()
        return jsonify(error_response('Failed to cancel session')), 500


# ==================== API ENDPOINTS ====================

@sessions_bp.route('/api/<int:session_id>/eligibility', methods=['GET'])
@login_required
@active_account_required
@owns_session
def check_eligibility(session_id):
    """Check if session can be started (AJAX endpoint)"""
    eligibility = session_service.get_session_eligibility_status(session_id)
    return jsonify(success_response(data=eligibility))


@sessions_bp.route('/api/<int:session_id>/stats', methods=['GET'])
@login_required
@active_account_required
@owns_session
def get_session_stats(session_id):
    """Get session statistics (AJAX endpoint)"""
    stats = session_service.calculate_session_statistics(session_id)
    return jsonify(success_response(data=stats))


@sessions_bp.route('/api/<int:session_id>/students', methods=['GET'])
@login_required
@active_account_required
@owns_session
def get_expected_students(session_id):
    """Get expected students list (AJAX endpoint)"""
    students = session_service.get_expected_students(session_id)
    return jsonify(success_response(data=students))


@sessions_bp.route('/api/<int:session_id>/reschedule-suggestions', methods=['GET'])
@login_required
@active_account_required
@owns_session
def get_reschedule_suggestions(session_id):
    """Get suggested reschedule dates (AJAX endpoint)"""
    days_ahead = request.args.get('days', 14, type=int)
    suggestions = session_service.suggest_reschedule_dates(session_id, days_ahead)
    return jsonify(success_response(data=suggestions))


@sessions_bp.route('/api/check-conflict', methods=['POST'])
@login_required
@active_account_required
def check_conflict():
    """Check for session conflicts (AJAX endpoint for form validation)"""
    data = request.get_json()
    
    class_id = data.get('class_id')
    date = data.get('date')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    exclude_session_id = data.get('exclude_session_id')
    
    if not all([class_id, date, start_time, end_time]):
        return jsonify(error_response('Missing required fields')), 400
    
    # Convert time format
    if len(start_time) == 5:
        start_time += ':00'
    if len(end_time) == 5:
        end_time += ':00'
    
    has_conflict, message = session_service.check_session_conflicts(
        class_id=class_id,
        date=date,
        start_time=start_time,
        end_time=end_time,
        instructor_id=current_user.instructor_id,
        exclude_session_id=exclude_session_id
    )
    
    return jsonify(success_response(data={
        'has_conflict': has_conflict,
        'message': message
    }))


# ==================== ERROR HANDLERS ====================

@sessions_bp.errorhandler(403)
def forbidden(e):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(error_response('Access denied')), 403
    flash('You do not have permission to access this session', 'error')
    return redirect(url_for('lecturer_sessions.list_sessions'))


@sessions_bp.errorhandler(404)
def not_found(e):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(error_response('Session not found')), 404
    flash('Session not found', 'error')
    return redirect(url_for('lecturer_sessions.list_sessions'))