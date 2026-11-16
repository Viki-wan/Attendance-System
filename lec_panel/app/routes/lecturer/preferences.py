# app/routes/lecturer/preferences.py
"""
Routes for instructor preferences management.
Allows customization of UI, notifications, and system behavior.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.services.preferences_service import PreferencesService
from app.middleware.activity_logger import ActivityLogger
from app.models.lecturer_preferences import LecturerPreference
from app.decorators.auth import login_required, active_account_required

preferences_bp = Blueprint('preferences', __name__, url_prefix='/lecturer/preferences')


@preferences_bp.route('/')
@login_required
@active_account_required
def index():
    """Display preferences page."""
    prefs = PreferencesService.get_preferences(current_user.instructor_id)
    notification_settings = PreferencesService.get_notification_settings(current_user.instructor_id)
    
    return render_template(
        'lecturer/preferences.html',
        preferences=prefs,
        notification_settings=notification_settings
    )


@preferences_bp.route('/update', methods=['POST'])
@login_required
@active_account_required
def update():
    """Update preferences."""
    try:
        updates = {
            'theme': request.form.get('theme'),
            'dashboard_layout': request.form.get('dashboard_layout'),
            'auto_refresh_interval': request.form.get('auto_refresh_interval'),
            'default_session_duration': request.form.get('default_session_duration'),
            'timezone': request.form.get('timezone'),
            'language': request.form.get('language')
        }
        
        # Remove None values
        updates = {k: v for k, v in updates.items() if v is not None}
        
        prefs = PreferencesService.update_preferences(
            current_user.instructor_id,
            updates
        )
        
        # Log activity
        ActivityLogger.log_current_user(
            ActivityLogger.PREFERENCES_UPDATE,
            description="Updated user preferences"
        )
        
        flash('Preferences updated successfully', 'success')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Preferences updated'
            })
        
        return redirect(url_for('preferences.index'))
        
    except Exception as e:
        flash(f'Failed to update preferences: {str(e)}', 'error')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@preferences_bp.route('/notifications/update', methods=['POST'])
@login_required
@active_account_required
def update_notifications():
    """Update notification settings."""
    try:
        data = request.get_json()
        
        notification_updates = {
            'email_notifications': data.get('email_notifications', True),
            'push_notifications': data.get('push_notifications', True),
            'attendance_alerts': data.get('attendance_alerts', True),
            'session_reminders': data.get('session_reminders', True),
            'low_attendance_threshold': int(data.get('low_attendance_threshold', 75))
        }
        
        PreferencesService.update_preferences(
            current_user.instructor_id,
            {'notification_settings': notification_updates}
        )
        
        ActivityLogger.log_current_user(
            ActivityLogger.PREFERENCES_UPDATE,
            description="Updated notification settings"
        )
        
        return jsonify({
            'success': True,
            'message': 'Notification settings updated'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@preferences_bp.route('/theme/toggle', methods=['POST'])
@login_required
@active_account_required
def toggle_theme():
    """Quick toggle between light and dark theme."""
    try:
        prefs = PreferencesService.get_preferences(current_user.instructor_id)
        new_theme = 'dark' if prefs.theme == 'light' else 'light'
        
        PreferencesService.update_preferences(
            current_user.instructor_id,
            {'theme': new_theme}
        )
        
        return jsonify({
            'success': True,
            'theme': new_theme
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@preferences_bp.route('/reset', methods=['POST'])
@login_required
@active_account_required
def reset():
    """Reset preferences to default values."""
    try:
        prefs = PreferencesService.reset_to_defaults(current_user.instructor_id)
        
        ActivityLogger.log_current_user(
            ActivityLogger.PREFERENCES_UPDATE,
            description="Reset preferences to defaults"
        )
        
        flash('Preferences reset to defaults', 'info')
        return redirect(url_for('preferences.index'))
        
    except Exception as e:
        flash(f'Failed to reset preferences: {str(e)}', 'error')
        return redirect(url_for('preferences.index'))


@preferences_bp.route('/export', methods=['GET'])
@login_required
@active_account_required
def export():
    """Export preferences as JSON for backup."""
    try:
        prefs = PreferencesService.get_preferences(current_user.instructor_id)
        notification_settings = PreferencesService.get_notification_settings(current_user.instructor_id)
        
        export_data = {
            'theme': prefs.theme,
            'dashboard_layout': prefs.dashboard_layout,
            'auto_refresh_interval': prefs.auto_refresh_interval,
            'default_session_duration': prefs.default_session_duration,
            'timezone': prefs.timezone,
            'language': prefs.language,
            'notification_settings': notification_settings
        }
        
        return jsonify({
            'success': True,
            'data': export_data,
            'instructor_id': current_user.instructor_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@preferences_bp.route('/import', methods=['POST'])
@login_required
@active_account_required
def import_preferences():
    """Import preferences from JSON backup."""
    try:
        data = request.get_json()
        
        if not data or 'data' not in data:
            return jsonify({
                'success': False,
                'error': 'Invalid import data'
            }), 400
        
        import_data = data['data']
        
        # Update preferences
        PreferencesService.update_preferences(
            current_user.instructor_id,
            import_data
        )
        
        ActivityLogger.log_current_user(
            ActivityLogger.PREFERENCES_UPDATE,
            description="Imported preferences from backup"
        )
        
        return jsonify({
            'success': True,
            'message': 'Preferences imported successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400