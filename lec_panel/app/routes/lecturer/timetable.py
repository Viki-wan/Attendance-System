# app/routes/lecturer/timetable.py
"""
Routes for timetable management and automated session scheduling.
Allows instructors to define recurring class schedules.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.timetable import Timetable
from app.models.classes import Class
from app.services.scheduling_service import SchedulingService
from app.middleware.activity_logger import ActivityLogger
from app.decorators.auth import active_account_required
from app.extensions import db
from datetime import datetime, timedelta

timetable_bp = Blueprint('timetable', __name__, url_prefix='/lecturer/timetable')


@timetable_bp.route('/')
@login_required
@active_account_required
def index():
    """Display timetable overview."""
    from app.models.class_instructors import ClassInstructor
    
    # Get instructor's classes
    class_assignments = ClassInstructor.query.filter_by(
        instructor_id=current_user.instructor_id
    ).all()
    
    class_ids = [ca.class_id for ca in class_assignments]
    
    # Get timetable entries for these classes
    timetables = Timetable.query.filter(
        Timetable.class_id.in_(class_ids),
        Timetable.is_active == True
    ).order_by(
        Timetable.day_of_week,
        Timetable.start_time
    ).all()
    
    # Group by day of week
    schedule_by_day = {}
    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    for i in range(7):
        schedule_by_day[i] = {
            'name': day_names[i],
            'entries': []
        }
    
    for entry in timetables:
        class_obj = Class.query.get(entry.class_id)
        schedule_by_day[entry.day_of_week]['entries'].append({
            'timetable_entry': entry,
            'class': class_obj
        })
    
    return render_template(
        'lecturer/timetable.html',
        schedule_by_day=schedule_by_day,
        day_names=day_names
    )


@timetable_bp.route('/create', methods=['GET', 'POST'])
@login_required
@active_account_required
def create():
    """Create new timetable entry."""
    from app.models.class_instructors import ClassInstructor
    
    if request.method == 'GET':
        # Get instructor's classes
        class_assignments = ClassInstructor.query.filter_by(
            instructor_id=current_user.instructor_id
        ).all()
        
        classes = [Class.query.get(ca.class_id) for ca in class_assignments]
        
        return render_template(
            'lecturer/create_timetable.html',
            classes=classes
        )
    
    try:
        class_id = request.form.get('class_id')
        day_of_week = int(request.form.get('day_of_week'))
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        effective_from = request.form.get('effective_from', datetime.now().date().strftime('%Y-%m-%d'))
        effective_to = request.form.get('effective_to')
        
        # Validate
        if not all([class_id, day_of_week is not None, start_time, end_time]):
            flash('All required fields must be filled', 'error')
            return redirect(url_for('timetable.create'))
        
        # Check for conflicts
        conflicts = Timetable.query.filter(
            Timetable.class_id == class_id,
            Timetable.day_of_week == day_of_week,
            Timetable.is_active == True
        ).all()
        
        for conflict in conflicts:
            if SchedulingService._times_overlap(start_time, end_time, conflict.start_time, conflict.end_time):
                flash(f'Time conflict with existing entry at {conflict.start_time}', 'error')
                return redirect(url_for('timetable.create'))
        
        # Create entry
        entry = Timetable(
            class_id=class_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            is_active=True,
            effective_from=effective_from,
            effective_to=effective_to if effective_to else None
        )
        
        db.session.add(entry)
        db.session.commit()
        
        # Log activity
        ActivityLogger.log_current_user(
            'timetable_create',
            description=f"Created timetable entry for {class_id}",
            class_id=class_id
        )
        
        flash('Timetable entry created successfully', 'success')
        return redirect(url_for('timetable.index'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to create timetable entry: {str(e)}', 'error')
        return redirect(url_for('timetable.create'))


@timetable_bp.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
@active_account_required
def edit(entry_id):
    """Edit timetable entry."""
    entry = Timetable.query.get_or_404(entry_id)
    
    # Verify ownership
    from app.models.class_instructors import ClassInstructor
    ownership = ClassInstructor.query.filter_by(
        class_id=entry.class_id,
        instructor_id=current_user.instructor_id
    ).first()
    
    if not ownership:
        flash('Unauthorized access', 'error')
        return redirect(url_for('timetable.index'))
    
    if request.method == 'GET':
        return render_template(
            'lecturer/edit_timetable.html',
            entry=entry
        )
    
    try:
        entry.day_of_week = int(request.form.get('day_of_week', entry.day_of_week))
        entry.start_time = request.form.get('start_time', entry.start_time)
        entry.end_time = request.form.get('end_time', entry.end_time)
        entry.effective_from = request.form.get('effective_from', entry.effective_from)
        entry.effective_to = request.form.get('effective_to') or None
        
        db.session.commit()
        
        ActivityLogger.log_current_user(
            'timetable_update',
            description=f"Updated timetable entry {entry_id}"
        )
        
        flash('Timetable entry updated successfully', 'success')
        return redirect(url_for('timetable.index'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to update timetable entry: {str(e)}', 'error')
        return redirect(url_for('timetable.edit', entry_id=entry_id))


@timetable_bp.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
@active_account_required
def delete(entry_id):
    """Delete timetable entry."""
    entry = Timetable.query.get_or_404(entry_id)
    
    # Verify ownership
    from app.models.class_instructors import ClassInstructor
    ownership = ClassInstructor.query.filter_by(
        class_id=entry.class_id,
        instructor_id=current_user.instructor_id
    ).first()
    
    if not ownership:
        return jsonify({
            'success': False,
            'error': 'Unauthorized'
        }), 403
    
    try:
        # Soft delete by marking as inactive
        entry.is_active = False
        db.session.commit()
        
        ActivityLogger.log_current_user(
            'timetable_delete',
            description=f"Deleted timetable entry {entry_id}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Timetable entry deleted'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@timetable_bp.route('/generate-sessions', methods=['GET', 'POST'])
@login_required
@active_account_required
def generate_sessions():
    """Generate sessions from timetable for a date range."""
    from app.models.class_instructors import ClassInstructor
    
    if request.method == 'GET':
        class_assignments = ClassInstructor.query.filter_by(
            instructor_id=current_user.instructor_id
        ).all()
        
        classes = [Class.query.get(ca.class_id) for ca in class_assignments]
        
        return render_template(
            'lecturer/generate_sessions.html',
            classes=classes
        )
    
    try:
        class_id = request.form.get('class_id')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        
        if end_date < start_date:
            flash('End date must be after start date', 'error')
            return redirect(url_for('timetable.generate_sessions'))
        
        # Generate sessions
        sessions_created, conflicts = SchedulingService.create_sessions_from_timetable(
            class_id,
            start_date,
            end_date,
            current_user.instructor_id
        )
        
        # Log activity
        ActivityLogger.log_current_user(
            'sessions_bulk_create',
            description=f"Generated {len(sessions_created)} sessions from timetable",
            class_id=class_id
        )
        
        if conflicts:
            flash(f'Created {len(sessions_created)} sessions. {len(conflicts)} conflicts found.', 'warning')
        else:
            flash(f'Successfully created {len(sessions_created)} sessions', 'success')
        
        return redirect(url_for('sessions.index'))
        
    except Exception as e:
        flash(f'Failed to generate sessions: {str(e)}', 'error')
        return redirect(url_for('timetable.generate_sessions'))


@timetable_bp.route('/api/class/<class_id>')
@login_required
@active_account_required
def get_class_timetable(class_id):
    """Get timetable for a specific class (API endpoint)."""
    # Verify ownership
    from app.models.class_instructors import ClassInstructor
    ownership = ClassInstructor.query.filter_by(
        class_id=class_id,
        instructor_id=current_user.instructor_id
    ).first()
    
    if not ownership:
        return jsonify({
            'success': False,
            'error': 'Unauthorized'
        }), 403
    
    entries = Timetable.query.filter_by(
        class_id=class_id,
        is_active=True
    ).order_by(
        Timetable.day_of_week,
        Timetable.start_time
    ).all()
    
    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    result = []
    for entry in entries:
        result.append({
            'id': entry.id,
            'day_of_week': entry.day_of_week,
            'day_name': day_names[entry.day_of_week],
            'start_time': entry.start_time,
            'end_time': entry.end_time,
            'effective_from': entry.effective_from.strftime('%Y-%m-%d') if entry.effective_from else None,
            'effective_to': entry.effective_to.strftime('%Y-%m-%d') if entry.effective_to else None
        })
    
    return jsonify({
        'success': True,
        'timetable': result
    })


@timetable_bp.route('/api/next-session/<class_id>')
@login_required
@active_account_required
def get_next_session(class_id):
    """Get next scheduled session time based on timetable."""
    next_session = SchedulingService.get_next_session_time(class_id)
    
    if next_session:
        return jsonify({
            'success': True,
            'next_session': {
                'date': next_session['date'].strftime('%Y-%m-%d'),
                'start_time': next_session['start_time'],
                'end_time': next_session['end_time'],
                'datetime': next_session['datetime'].isoformat()
            }
        })
    else:
        return jsonify({
            'success': True,
            'next_session': None,
            'message': 'No upcoming sessions in timetable'
        })


@timetable_bp.route('/api/weekly-view')
@login_required
@active_account_required
def weekly_view():
    """Get weekly timetable view for instructor."""
    from app.models.class_instructors import ClassInstructor
    
    class_assignments = ClassInstructor.query.filter_by(
        instructor_id=current_user.instructor_id
    ).all()
    
    class_ids = [ca.class_id for ca in class_assignments]
    
    entries = Timetable.query.filter(
        Timetable.class_id.in_(class_ids),
        Timetable.is_active == True
    ).all()
    
    weekly_schedule = {}
    for i in range(7):
        weekly_schedule[i] = []
    
    for entry in entries:
        class_obj = Class.query.get(entry.class_id)
        weekly_schedule[entry.day_of_week].append({
            'class_id': entry.class_id,
            'class_name': class_obj.class_name,
            'start_time': entry.start_time,
            'end_time': entry.end_time
        })
    
    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    return jsonify({
        'success': True,
        'schedule': [
            {
                'day': i,
                'day_name': day_names[i],
                'classes': weekly_schedule[i]
            }
            for i in range(7)
        ]
    })