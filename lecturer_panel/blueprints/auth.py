from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from lecturer_panel.services.auth_service import AuthService
from lecturer_panel.forms.auth_forms import LoginForm

auth_bp = Blueprint('auth', __name__)
auth_service = AuthService()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.lecturer_id.data.strip()
        password = form.password.data
        remember_me = form.remember_me.data

        # Allow login with either Lecturer ID or email
        result = auth_service.authenticate_instructor(username, password)
        if result['success']:
            user = result['user']
            session['user_id'] = user['id']
            session['instructor_id'] = user['id']  # Ensure compatibility with login_required
            session['logged_in'] = True            # Ensure compatibility with login_required
            session['username'] = user['username']
            session['is_admin'] = user.get('is_admin', False)
            session['instructor_name'] = user['instructor_name']
            # Set instructor initials for avatar
            name_parts = user['instructor_name'].split()
            initials = ''.join([part[0] for part in name_parts if part]).upper()
            session['instructor_initials'] = initials
            session['email'] = user.get('email')
            session.permanent = bool(remember_me)
            if not user.get('last_login'):
                # First time login, redirect to setup (do NOT update last_login yet)
                return redirect(url_for('auth.first_time_setup'))
            # Now update last_login since it's not first time
            auth_service.update_last_login(user['id'])
            flash(f"Welcome back, {user['instructor_name']}!", 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash(result['message'], 'error')
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
def logout():
    """Handle user logout"""
    if 'user_id' in session:
        auth_service.log_activity(session['user_id'], 'logout', 'User logged out')
        session.clear()
        flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/first-time-setup', methods=['GET', 'POST'])
def first_time_setup():
    """Handle first-time setup for new lecturers"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    # Fetch instructor info from DB
    instructor = auth_service.get_user_by_id(session['user_id'])
    if not instructor:
        flash('Instructor not found.', 'error')
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        # Only allow password change (and optionally phone/email if you want)
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        # Optionally allow phone/email update:
        # email = request.form.get('email', '').strip()
        # phone = request.form.get('phone', '').strip()
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/first_time_setup.html', instructor=instructor)
        # Update password only
        result = auth_service.change_password(session['user_id'], None, password, skip_current=True)
        if result['success']:
            # After successful setup, update last_login
            auth_service.update_last_login(session['user_id'])
            flash('Account setup complete! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(result['message'], 'error')
    return render_template('auth/first_time_setup.html', instructor=instructor)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    """Handle password change for existing users"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('auth/change_password.html')
        result = auth_service.change_password(session['user_id'], current_password, new_password)
        if result['success']:
            flash('Password changed successfully!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash(result['message'], 'error')
    return render_template('auth/change_password.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle password reset request"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash('Email address is required.', 'error')
            return render_template('auth/forgot_password.html')
        result = auth_service.reset_password(email)
        if result['success']:
            flash('Password reset instructions have been sent to your email.', 'info')
            return redirect(url_for('auth.login'))
        else:
            flash(result['message'], 'error')
    return render_template('auth/forgot_password.html')

@auth_bp.route('/check-session')
def check_session():
    """API endpoint to check if user session is valid"""
    if 'user_id' in session:
        return {'valid': True, 'user': session['username']}
    return {'valid': False}

@auth_bp.route('/extend-session', methods=['POST'])
def extend_session():
    """API endpoint to extend user session"""
    if 'user_id' in session:
        session.permanent = True
        return {'success': True}
    return {'success': False}