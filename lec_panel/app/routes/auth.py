"""
Authentication Routes
Handles login, logout, profile management, and first-time setup for instructors
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash
from app.services.auth_service import AuthService
from app.models.user import Instructor
from app.models.activity_log import ActivityLog
from app.models.class_model import Class
from app import db
import logging

# Initialize blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
logger = logging.getLogger(__name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login route for instructors
    Supports login via instructor_id, email, or phone
    Redirects to first-time setup if password hasn't been changed
    """
    # Redirect if already logged in
    if current_user.is_authenticated:
        if hasattr(current_user, 'requires_password_change') and current_user.requires_password_change():
            return redirect(url_for('auth.first_time_setup'))
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        try:
            identifier = request.form.get('identifier', '').strip()
            password = request.form.get('password', '')
            # FIX: Properly handle checkbox value
            remember_me = request.form.get('remember_me') in ['on', 'true', True]
            if not remember_me:
                remember_me = request.form.get('remember') in ['on', 'true', True]
            
            # Validate inputs
            if not identifier or not password:
                flash('Please provide both identifier and password.', 'error')
                return render_template('auth/login.html')
            
            # Attempt login - handle 4 return values
            success, message, instructor, is_first_time = AuthService.login(
                identifier, password, remember_me
            )
            
            if success and instructor:
                # Login successful
                logger.info(f"Instructor {instructor.instructor_id} logged in successfully")
                
                # Check if first-time setup is required
                if is_first_time:
                    flash('Please complete your profile setup and change your password.', 'info')
                    return redirect(url_for('auth.first_time_setup'))
                
                # Handle next parameter for redirect after login
                next_page = request.args.get('next')
                if next_page and urlparse(next_page).netloc == '':
                    return redirect(next_page)
                
                flash(f'Welcome back, {instructor.instructor_name}!', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                # Login failed
                logger.warning(f"Failed login attempt for identifier: {identifier}")
                flash(message or 'Invalid credentials. Please try again.', 'error')
        
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            flash('An error occurred during login. Please try again.', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """
    Logout route
    Clears session and logs activity
    """
    instructor_id = current_user.instructor_id
    instructor_name = current_user.instructor_name
    
    # Log activity before logout
    try:
        AuthService.log_activity(
            user_id=instructor_id,
            user_type='instructor',
            activity_type='logout',
            description='User logged out'
        )
    except Exception as e:
        logger.error(f"Error logging logout activity: {str(e)}")
    
    logger.info(f"Instructor {instructor_id} logged out")
    
    logout_user()
    session.clear()
    
    flash(f'Goodbye, {instructor_name}! You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/first-time-setup', methods=['GET', 'POST'])
@login_required
def first_time_setup():
    """
    First-time setup route
    Forces instructors to change their default password and complete profile
    """
    # Redirect if password already changed
    if hasattr(current_user, 'requires_password_change') and not current_user.requires_password_change():
        flash('Your account is already set up.', 'info')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        try:
            current_password = request.form.get('current_password', '').strip()
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            
            # Validate current password
            if not current_password:
                flash('Current password is required.', 'error')
                return render_template('auth/first_time_setup.html')
            
            # Verify current password
            if not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'error')
                return render_template('auth/first_time_setup.html')
            
            # Validate password match
            if new_password != confirm_password:
                flash('Passwords do not match. Please try again.', 'error')
                return render_template('auth/first_time_setup.html')
            
            # Validate new password is different from current
            if current_user.check_password(new_password):
                flash('New password cannot be the same as your current password.', 'error')
                return render_template('auth/first_time_setup.html')
            
            # Validate password strength
            if len(new_password) < 8:
                flash('Password must be at least 8 characters long.', 'error')
                return render_template('auth/first_time_setup.html')
            
            if not any(c.isalpha() for c in new_password):
                flash('Password must contain at least one letter.', 'error')
                return render_template('auth/first_time_setup.html')
            
            if not any(c.isdigit() for c in new_password):
                flash('Password must contain at least one number.', 'error')
                return render_template('auth/first_time_setup.html')
            
            # Use the complete_first_time_setup service method
            success, message = AuthService.complete_first_time_setup(
                instructor_id=current_user.instructor_id,
                new_password=new_password,
                email=email if email else None,
                phone=phone if phone else None
            )
            
            if not success:
                flash(message or 'Failed to complete setup. Please try again.', 'error')
                return render_template('auth/first_time_setup.html')
            
            # Log activity
            AuthService.log_activity(
                user_id=current_user.instructor_id,
                user_type='instructor',
                activity_type='first_time_setup',
                description='Completed first-time setup and password change'
            )
            
            logger.info(f"Instructor {current_user.instructor_id} completed first-time setup")
            
            flash('Your account has been set up successfully! Welcome to the system.', 'success')
            return redirect(url_for('dashboard.index'))
        
        except Exception as e:
            logger.error(f"First-time setup error: {str(e)}")
            flash('An error occurred during setup. Please try again.', 'error')
    
    return render_template('auth/first_time_setup.html')

@auth_bp.route('/profile')
@login_required
def profile():
    """Display user profile page"""
    try:
        # Get instructor's classes
        classes = Class.get_by_instructor(current_user.instructor_id)
        
        # Get recent activity
        recent_activity = ActivityLog.get_user_activities(
            current_user.instructor_id,
            limit=10
        )
        
        # Get login history
        login_history = ActivityLog.get_login_history(
            current_user.instructor_id,
            limit=5
        )
        
        return render_template(
            'auth/profile.html',
            instructor=current_user,
            classes=classes,
            recent_activity=recent_activity,
            login_history=login_history
        )
    except Exception as e:
        logger.error(f"Profile page error: {str(e)}")
        flash('An error occurred while loading your profile.', 'error')
        return redirect(url_for('dashboard.index'))


@auth_bp.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    """Update user profile information"""
    try:
        # Get form data
        instructor_name = request.form.get('instructor_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        faculty = request.form.get('faculty', '').strip()
        
        # Validate unique constraints
        if email and email != current_user.email:
            existing = Instructor.get_by_email(email)
            if existing:
                flash('Email already in use by another instructor.', 'error')
                return redirect(url_for('auth.profile'))
        
        if phone and phone != current_user.phone:
            existing = Instructor.get_by_phone(phone)
            if existing:
                flash('Phone number already in use by another instructor.', 'error')
                return redirect(url_for('auth.profile'))
        
        # Update profile
        update_data = {}
        if instructor_name:
            update_data['instructor_name'] = instructor_name
        if email:
            update_data['email'] = email
        if phone:
            update_data['phone'] = phone
        if faculty:
            update_data['faculty'] = faculty
        
        if update_data:
            success, error = AuthService.update_profile(
                instructor=current_user,
                **update_data
            )
            
            if success:
                # Log activity
                AuthService.log_activity(
                    user_id=current_user.instructor_id,
                    user_type='instructor',
                    activity_type='profile_update',
                    description='Updated profile information'
                )
                flash('Profile updated successfully!', 'success')
            else:
                flash(f'Failed to update profile: {error}', 'error')
        else:
            flash('No changes were made.', 'info')
        
        return redirect(url_for('auth.profile'))
        
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        flash('An error occurred while updating your profile.', 'error')
        return redirect(url_for('auth.profile'))


@auth_bp.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    try:
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate inputs
        if not all([current_password, new_password, confirm_password]):
            flash('All password fields are required.', 'error')
            return redirect(url_for('auth.profile'))
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('auth.profile'))
        
        if len(new_password) < 8:
            flash('New password must be at least 8 characters long.', 'error')
            return redirect(url_for('auth.profile'))
        
        # Change password
        success, message = AuthService.change_password(
            instructor_id=current_user,
            old_password=current_password,
            new_password=new_password
        )
        
        if success:
            # Log activity
            AuthService.log_activity(
                user_id=current_user.instructor_id,
                user_type='instructor',
                activity_type='password_change',
                description='Changed password'
            )
            flash('Password changed successfully!', 'success')
        else:
            flash(message or 'Failed to change password.', 'error')
        
        return redirect(url_for('auth.profile'))
        
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        flash('An error occurred while changing your password.', 'error')
        return redirect(url_for('auth.profile'))


@auth_bp.route('/profile/activity')
@login_required
def profile_activity():
    """Display user activity log"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Get paginated activity logs
        activities = ActivityLog.query.filter_by(
            user_id=current_user.instructor_id,
            user_type='instructor'
        ).order_by(
            ActivityLog.timestamp.desc()
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return render_template(
            'auth/activity.html',
            activities=activities
        )
    except Exception as e:
        logger.error(f"Activity page error: {str(e)}")
        flash('An error occurred while loading activity logs.', 'error')
        return redirect(url_for('auth.profile'))


@auth_bp.route('/profile/deactivate', methods=['POST'])
@login_required
def deactivate_account():
    """Deactivate user account (soft delete)"""
    try:
        password = request.form.get('password', '')
        
        # Verify password
        if not current_user.check_password(password):
            return jsonify({
                'success': False,
                'message': 'Incorrect password'
            }), 401
        
        # Deactivate account
        current_user.deactivate()
        
        # Log activity
        AuthService.log_activity(
            user_id=current_user.instructor_id,
            user_type='instructor',
            activity_type='account_deactivation',
            description='Account deactivated by user'
        )
        
        # Logout
        logout_user()
        session.clear()
        
        flash('Your account has been deactivated.', 'info')
        return jsonify({
            'success': True,
            'redirect': url_for('auth.login')
        })
        
    except Exception as e:
        logger.error(f"Error deactivating account: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred'
        }), 500


@auth_bp.before_request
def check_account_status():
    """
    Middleware to check if instructor account is active
    Runs before every request to auth blueprint
    """
    if current_user.is_authenticated and hasattr(current_user, 'is_active') and not current_user.is_active:
        logout_user()
        session.clear()
        flash('Your account has been deactivated. Please contact the administrator.', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.errorhandler(401)
def unauthorized(error):
    """
    Custom handler for 401 Unauthorized errors
    """
    flash('Please log in to access this page.', 'warning')
    return redirect(url_for('auth.login'))


@auth_bp.errorhandler(403)
def forbidden(error):
    """
    Custom handler for 403 Forbidden errors
    """
    flash('You do not have permission to access this resource.', 'error')
    return redirect(url_for('dashboard.index'))