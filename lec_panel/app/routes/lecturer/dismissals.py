# app/routes/lecturer/dismissals.py
"""
Routes for managing session dismissals and rescheduling.
Allows instructors to dismiss sessions with reasons and reschedule options.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.session_dismissals import SessionDismissal
from app.models.class_session import ClassSession
from app.services.notification_service import NotificationService
from app.services.scheduling_service import SchedulingService
from app.middleware.activity_logger import ActivityLogger
from app.decorators.auth import active_account_required, owns_session
from app.extensions import db
from datetime import datetime

dismissals_bp = Blueprint('dismissals', __name__, url_prefix='/lecturer/dismissals')


@dismissals_bp.route('/session/<int:session_id>/dismiss', methods=['GET', 'POST'])
@login_required
@active_account_required
@owns_session
def dismiss_session(session_id):
    """Dismiss a session with reason and optional rescheduling."""
    session = ClassSession.query.get_or_404(session_id)
    
    if request.method == 'GET':
        # Show dismissal form
        return render_template(
            'lecturer/dismiss_session.html',
            session=session
        )
    
    try:
        reason = request.form.get('reason')
        reschedule = request.form.get('reschedule') == 'yes'
        rescheduled_date = request.form.get('rescheduled_date')
        rescheduled_time = request.form.get('rescheduled_time')
        notes = request.form.get('notes', '')
        
        if not reason:
            flash('Dismissal reason is required', 'error')
            return redirect(url_for('dismissals.dismiss_session', session_id=session_id))
        
        # Create dismissal record
        dismissal = SessionDismissal(
            session_id=session_id,
            instructor_id=current_user.instructor_id,
            reason=reason,
            notes=notes,
            status='dismissed'
        )
        
        # Handle rescheduling
        if reschedule and rescheduled_date and rescheduled_time:
            dismissal.rescheduled_to = rescheduled_date
            dismissal.rescheduled_time = rescheduled_time
            dismissal.status = 'rescheduled'
            
            # Create new session
            new_session = ClassSession(
                class_id=session.class_id,
                date=rescheduled_date,
                start_time=rescheduled_time,
                end_time=session.end_time,  # Keep same duration
                status='scheduled',
                created_by=current_user.instructor_id,
                session_notes=f"Rescheduled from {session.date}"
            )
            db.session.add(new_session)
        
        # Update original session status
        session.status = 'dismissed'
        session.session_notes = f"Dismissed: {reason}"
        
        db.session.add(dismissal)
        db.session.commit()
        
        # Log activity
        ActivityLogger.log_current_user(
            ActivityLogger.SESSION_DISMISS,
            description=f"Dismissed session {session_id}: {reason}",
            session_id=session_id
        )
        
        # Notify relevant parties (could be students, admin, etc.)
        # This is a placeholder for notification logic
        
        flash('Session dismissed successfully', 'success')
        return redirect(url_for('sessions.index'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to dismiss session: {str(e)}', 'error')
        return redirect(url_for('dismissals.dismiss_session', session_id=session_id))


@dismissals_bp.route('/history')
@login_required
@active_account_required
def history():
    """View dismissal history for instructor."""
    dismissals = SessionDismissal.query.filter_by(
        instructor_id=current_user.instructor_id
    ).order_by(
        SessionDismissal.dismissal_time.desc()
    ).limit(50).all()
    
    return render_template(
        'lecturer/dismissal_history.html',
        dismissals=dismissals
    )


@dismissals_bp.route('/api/reasons')
@login_required
@active_account_required
def get_common_reasons():
    """Get common dismissal reasons for quick selection."""
    common_reasons = [
        "Instructor illness",
        "Emergency situation",
        "Technical difficulties",
        "Insufficient attendance",
        "Weather conditions",
        "Facility unavailable",
        "Conflicting appointment",
        "Public holiday",
        "Other (specify in notes)"
    ]
    
    return jsonify({
        'success': True,
        'reasons': common_reasons
    })


@dismissals_bp.route('/api/suggest-reschedule/<int:session_id>')
@login_required
@active_account_required
@owns_session
def suggest_reschedule(session_id):
    """Suggest available times for rescheduling."""
    session = ClassSession.query.get_or_404(session_id)
    
    try:
        # Get suggestions for next 7 days
        from datetime import timedelta
        suggestions = []
        
        for i in range(1, 8):
            date = (datetime.now() + timedelta(days=i)).date()
            available_slots = SchedulingService.suggest_session_time(
                session.class_id,
                date
            )
            
            if available_slots:
                suggestions.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'day_name': date.strftime('%A'),
                    'slots': available_slots
                })
        
        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@dismissals_bp.route('/api/<int:dismissal_id>/details')
@login_required
@active_account_required
def get_dismissal_details(dismissal_id):
    """Get detailed information about a dismissal."""
    dismissal = SessionDismissal.query.filter_by(
        id=dismissal_id,
        instructor_id=current_user.instructor_id
    ).first_or_404()
    
    session = ClassSession.query.get(dismissal.session_id)
    
    return jsonify({
        'success': True,
        'dismissal': {
            'id': dismissal.id,
            'session_id': dismissal.session_id,
            'reason': dismissal.reason,
            'notes': dismissal.notes,
            'dismissal_time': dismissal.dismissal_time.isoformat(),
            'status': dismissal.status,
            'rescheduled_to': dismissal.rescheduled_to,
            'rescheduled_time': dismissal.rescheduled_time
        },
        'session': {
            'class_id': session.class_id,
            'date': session.date,
            'start_time': session.start_time,
            'end_time': session.end_time
        }
    })


@dismissals_bp.route('/statistics')
@login_required
@active_account_required
def statistics():
    """Get dismissal statistics for the instructor."""
    from sqlalchemy import func
    
    # Get dismissals by reason
    dismissal_reasons = db.session.query(
        SessionDismissal.reason,
        func.count(SessionDismissal.id).label('count')
    ).filter(
        SessionDismissal.instructor_id == current_user.instructor_id
    ).group_by(
        SessionDismissal.reason
    ).all()
    
    # Get dismissals by status
    dismissal_status = db.session.query(
        SessionDismissal.status,
        func.count(SessionDismissal.id).label('count')
    ).filter(
        SessionDismissal.instructor_id == current_user.instructor_id
    ).group_by(
        SessionDismissal.status
    ).all()
    
    # Total dismissals
    total_dismissals = SessionDismissal.query.filter_by(
        instructor_id=current_user.instructor_id
    ).count()
    
    # Recent dismissals (last 30 days)
    from datetime import timedelta
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_dismissals = SessionDismissal.query.filter(
        SessionDismissal.instructor_id == current_user.instructor_id,
        SessionDismissal.dismissal_time >= thirty_days_ago
    ).count()
    
    return render_template(
        'lecturer/dismissal_statistics.html',
        dismissal_reasons=dismissal_reasons,
        dismissal_status=dismissal_status,
        total_dismissals=total_dismissals,
        recent_dismissals=recent_dismissals
    )


@dismissals_bp.route('/api/validate-reschedule', methods=['POST'])
@login_required
@active_account_required
def validate_reschedule():
    """Validate if a reschedule time is available."""
    try:
        data = request.get_json()
        class_id = data.get('class_id')
        date = data.get('date')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if not all([class_id, date, start_time, end_time]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        # Check for conflicts
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        conflict = SchedulingService._check_session_conflict(
            class_id, date_obj, start_time, end_time
        )
        
        if conflict:
            return jsonify({
                'success': False,
                'available': False,
                'message': conflict
            })
        
        return jsonify({
            'success': True,
            'available': True,
            'message': 'Time slot is available'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400