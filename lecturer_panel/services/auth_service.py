"""
Authentication service for lecturer panel
Handles user authentication, session management, and security
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from lecturer_panel.services.database_service import DatabaseService
from lecturer_panel.utils.helpers import validate_password_strength, validate_email, validate_phone, log_error

class AuthService:
    def __init__(self):
        self.db_service = DatabaseService()
        self.max_login_attempts = 5
        self.lockout_duration = 30  # minutes
        self.session_timeout = 30  # minutes
    
    def authenticate_instructor(self, username, password):
        """
        Authenticate instructor by username/email and password
        Returns user data if successful, None if failed
        """
        try:
            # Check if user is locked out
            if self.is_user_locked_out(username):
                return {
                    'success': False,
                    'message': 'Account is temporarily locked due to multiple failed login attempts.',
                    'locked_until': self.get_lockout_expiry(username)
                }
            # Try to find user by username, lecturer_id, or email
            user = self.get_user_by_username_or_email(username)
            print(f"[DEBUG] User record for '{username}': {user}")  # Debug print
            if not user:
                self.log_failed_attempt(username)
                return {
                    'success': False,
                    'message': 'Invalid username or password.'
                }
            # Check if user account is active
            if not user.get('is_active', 1):
                return {
                    'success': False,
                    'message': 'Account is deactivated. Please contact administrator.'
                }
            # Verify password
            password_ok = self.verify_password(password, user.get('password'))
            print(f"[DEBUG] Password verification for '{username}': {password_ok}")  # Debug print
            if password_ok:
                # Reset failed attempts on successful login
                self.reset_failed_attempts(username)
                # Update last login timestamp
                self.update_last_login(user['instructor_id'])
                # Log successful login
                self.log_activity(user['instructor_id'], 'login', 'Successful login')
                return {
                    'success': True,
                    'user': {
                        'id': user['instructor_id'],
                        'username': user['instructor_name'],
                        'email': user['email'],
                        'instructor_name': user['instructor_name'],
                        'phone': user['phone'],
                        'faculty': user.get('faculty'),
                        'last_login': user.get('last_login'),
                        'is_active': user.get('is_active', 1)
                    }
                }
            else:
                # Log failed attempt
                self.log_failed_attempt(username)
                return {
                    'success': False,
                    'message': 'Invalid username or password.'
                }
        except Exception as e:
            log_error(f"Authentication error for user {username}: {str(e)}", "AUTH_ERROR")
            return {
                'success': False,
                'message': 'An error occurred during authentication. Please try again.'
            }
    
    def create_instructor_account(self, instructor_data):
        """
        Create new instructor account
        Returns success status and user data or error message
        """
        try:
            # Validate required fields
            required_fields = ['instructor_name', 'email', 'phone', 'password']
            for field in required_fields:
                if not instructor_data.get(field):
                    return {
                        'success': False,
                        'message': f'{field.replace("_", " ").title()} is required.'
                    }
            
            # Validate email format
            if not validate_email(instructor_data['email']):
                return {
                    'success': False,
                    'message': 'Please enter a valid email address.'
                }
            
            # Validate phone format
            if not validate_phone(instructor_data['phone']):
                return {
                    'success': False,
                    'message': 'Please enter a valid phone number.'
                }
            
            # Validate password strength
            if not validate_password_strength(instructor_data['password']):
                return {
                    'success': False,
                    'message': 'Password must be at least 8 characters long and contain uppercase, lowercase, and numeric characters.'
                }
            
            # Check for existing instructor with same name, email, or phone
            if self.instructor_exists(instructor_data['instructor_name'], instructor_data['email'], instructor_data['phone']):
                return {
                    'success': False,
                    'message': 'An instructor with this name, email, or phone already exists.'
                }
            
            # Hash password
            password_hash = generate_password_hash(instructor_data['password'])
            
            # Insert instructor
            query = """
                INSERT INTO instructors (instructor_name, email, phone, password, faculty, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            """
            result = self.db_service.execute_query(query, (
                instructor_data['instructor_name'],
                instructor_data['email'],
                instructor_data['phone'],
                password_hash,
                instructor_data.get('faculty', '')
            ))
            
            if result:
                # Get the newly created instructor
                instructor = self.get_user_by_username_or_email(instructor_data['instructor_name'])
                
                # Log account creation
                self.log_activity(instructor['instructor_id'], 'account_created', 'New instructor account created')
                
                return {
                    'success': True,
                    'message': 'Account created successfully!',
                    'user': instructor
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to create account. Please try again.'
                }
                
        except Exception as e:
            log_error(f"Account creation error: {str(e)}", "ACCOUNT_CREATION_ERROR")
            return {
                'success': False,
                'message': 'An error occurred while creating the account. Please try again.'
            }
    
    def change_password(self, user_id, current_password, new_password, skip_current=False):
        """
        Change user password
        Returns success status and message
        If skip_current is True, do not check current password (for first-time setup)
        """
        try:
            # Get current user
            query = "SELECT * FROM instructors WHERE instructor_id = ?"
            user = self.db_service.execute_query(query, (user_id,), fetch='all')
            if user:
                user = user[0]
            else:
                return {
                    'success': False,
                    'message': 'User not found.'
                }
            # If not skipping, verify current password
            if not skip_current:
                if not self.verify_password(current_password, user['password']):
                    return {
                        'success': False,
                        'message': 'Current password is incorrect.'
                    }
            # Validate new password strength
            if not validate_password_strength(new_password):
                return {
                    'success': False,
                    'message': 'New password must be at least 8 characters long and contain uppercase, lowercase, and numeric characters.'
                }
            # Hash new password
            new_password_hash = generate_password_hash(new_password)
            # Update password
            update_query = "UPDATE instructors SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE instructor_id = ?"
            result = self.db_service.execute_query(update_query, (new_password_hash, user_id))
            if result:
                # Log password change
                self.log_activity(user_id, 'password_changed', 'Password changed successfully')
                return {
                    'success': True,
                    'message': 'Password changed successfully!'
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to change password. Please try again.'
                }
        except Exception as e:
            log_error(f"Password change error for user {user_id}: {str(e)}", "PASSWORD_CHANGE_ERROR")
            return {
                'success': False,
                'message': 'An error occurred while changing the password. Please try again.'
            }
    
    def reset_password(self, email):
        """
        Initiate password reset process
        Returns success status and message
        """
        try:
            # Check if email exists
            query = "SELECT * FROM instructors WHERE email = ? AND is_active = 1"
            user = self.db_service.execute_query(query, (email,))
            
            if not user:
                return {
                    'success': False,
                    'message': 'Email address not found.'
                }
            
            user = user[0]
            
            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=24)  # Token expires in 24 hours
            
            # Store reset token (in a real app, you'd have a password_reset_tokens table)
            # For now, we'll just log it
            self.log_activity(user['instructor_id'], 'password_reset_requested', f'Password reset token: {reset_token}')
            
            # In a real application, you would send an email with the reset link
            # For now, we'll just return success
            return {
                'success': True,
                'message': 'Password reset instructions have been sent to your email.',
                'reset_token': reset_token  # Remove this in production
            }
            
        except Exception as e:
            log_error(f"Password reset error for email {email}: {str(e)}", "PASSWORD_RESET_ERROR")
            return {
                'success': False,
                'message': 'An error occurred while processing the password reset. Please try again.'
            }
    
    def get_user_by_username_or_email(self, username_or_email):
        """Get user by lecturer_id, instructor_name, or email"""
        try:
            # Print all instructor IDs, names, emails, and is_active for debugging
            all_users = self.db_service.execute_query("SELECT instructor_id, instructor_name, email, is_active FROM instructors", (), fetch='all')
            print("[DEBUG] All instructors:", all_users)
            query = """
                SELECT * FROM instructors 
                WHERE (instructor_id = ? OR instructor_name = ? OR email = ?) AND is_active = 1
            """
            result = self.db_service.execute_query(query, (username_or_email, username_or_email, username_or_email), fetch='all')
            print(f"[DEBUG] DB lookup for '{username_or_email}': {result}")
            if result:
                return result[0]
            return None
        except Exception as e:
            log_error(f"Error getting user by username/email {username_or_email}: {str(e)}", "USER_LOOKUP_ERROR")
            return None
    
    def instructor_exists(self, instructor_name, email, phone):
        """Check if instructor already exists"""
        try:
            query = """
                SELECT COUNT(*) as count FROM instructors 
                WHERE instructor_name = ? OR email = ? OR phone = ?
            """
            result = self.db_service.execute_query(query, (instructor_name, email, phone), fetch='all')
            if result:
                return result[0]['count'] > 0
            return False
        except Exception as e:
            log_error(f"Error checking instructor existence: {str(e)}", "INSTRUCTOR_CHECK_ERROR")
            return True  # Assume exists to prevent duplicate creation
    
    def verify_password(self, password, stored_hash):
        """Verify password against stored hash"""
        try:
            return check_password_hash(stored_hash, password)
        except Exception as e:
            log_error(f"Password verification error: {str(e)}", "PASSWORD_VERIFICATION_ERROR")
            return False
    
    def is_user_locked_out(self, username):
        """Check if user is locked out due to failed login attempts"""
        try:
            query = """
                SELECT COUNT(*) as attempts, MAX(timestamp) as last_attempt 
                FROM activity_log 
                WHERE user_id = ? AND activity_type = 'failed_login' 
                AND timestamp > datetime('now', '-{} minutes')
            """.format(self.lockout_duration)
            
            result = self.db_service.execute_query(query, (username,))
            
            if result:
                attempts = result[0]['attempts']
                return attempts >= self.max_login_attempts
            
            return False
            
        except Exception as e:
            log_error(f"Error checking lockout status for {username}: {str(e)}", "LOCKOUT_CHECK_ERROR")
            return False
    
    def get_lockout_expiry(self, username):
        """Get when user lockout expires"""
        try:
            query = """
                SELECT MAX(timestamp) as last_attempt 
                FROM activity_log 
                WHERE user_id = ? AND activity_type = 'failed_login'
            """
            
            result = self.db_service.execute_query(query, (username,))
            
            if result and result[0]['last_attempt']:
                last_attempt = datetime.strptime(result[0]['last_attempt'], "%Y-%m-%d %H:%M:%S")
                return last_attempt + timedelta(minutes=self.lockout_duration)
            
            return None
            
        except Exception as e:
            log_error(f"Error getting lockout expiry for {username}: {str(e)}", "LOCKOUT_EXPIRY_ERROR")
            return None
    
    def log_failed_attempt(self, username):
        """Log failed login attempt"""
        try:
            self.log_activity(username, 'failed_login', 'Failed login attempt')
        except Exception as e:
            log_error(f"Error logging failed attempt for {username}: {str(e)}", "FAILED_ATTEMPT_LOG_ERROR")
    
    def reset_failed_attempts(self, username):
        """Reset failed login attempts for user"""
        try:
            # In a real application, you might want to keep a separate table for login attempts
            # For now, we'll just log the successful login
            self.log_activity(username, 'login_success', 'Login successful - attempts reset')
        except Exception as e:
            log_error(f"Error resetting failed attempts for {username}: {str(e)}", "RESET_ATTEMPTS_ERROR")
    
    def update_last_login(self, user_id):
        """Update user's last login timestamp"""
        try:
            query = "UPDATE instructors SET last_login = CURRENT_TIMESTAMP WHERE instructor_id = ?"
            self.db_service.execute_query(query, (user_id,))
        except Exception as e:
            log_error(f"Error updating last login for user {user_id}: {str(e)}", "LAST_LOGIN_UPDATE_ERROR")
    
    def log_activity(self, user_id, activity_type, description=None):
        """Log user activity"""
        try:
            query = """
                INSERT INTO activity_log (user_id, user_type, activity_type, description, timestamp)
                VALUES (?, 'instructor', ?, ?, CURRENT_TIMESTAMP)
            """
            self.db_service.execute_query(query, (str(user_id), activity_type, description))
        except Exception as e:
            log_error(f"Error logging activity for user {user_id}: {str(e)}", "ACTIVITY_LOG_ERROR")
    
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        try:
            query = "SELECT * FROM instructors WHERE instructor_id = ? AND is_active = 1"
            result = self.db_service.execute_query(query, (user_id,), fetch='all')
            if result and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            log_error(f"Error getting user by ID {user_id}: {str(e)}", "USER_BY_ID_ERROR")
            return None
    
    def validate_session(self, user_id):
        """Validate user session"""
        try:
            user = self.get_user_by_id(user_id)
            
            if not user:
                return False
            
            # Check if user is still active
            if not user.get('is_active', 1):
                return False
            
            return True
            
        except Exception as e:
            log_error(f"Error validating session for user {user_id}: {str(e)}", "SESSION_VALIDATION_ERROR")
            return False
    
    def get_user_permissions(self, user_id):
        """Get user permissions (for future role-based access control)"""
        try:
            # For now, all instructors have the same permissions
            # In the future, you might have different roles with different permissions
            return {
                'can_mark_attendance': True,
                'can_view_reports': True,
                'can_manage_sessions': True,
                'can_dismiss_sessions': True,
                'can_export_data': True,
                'can_view_analytics': True
            }
            
        except Exception as e:
            log_error(f"Error getting permissions for user {user_id}: {str(e)}", "PERMISSIONS_ERROR")
            return {}
    
    def deactivate_user(self, user_id):
        """Deactivate user account"""
        try:
            query = "UPDATE instructors SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE instructor_id = ?"
            result = self.db_service.execute_query(query, (user_id,))
            if result:
                self.log_activity(user_id, 'account_deactivated', 'Account deactivated')
                return True
            return False
        except Exception as e:
            log_error(f"Error deactivating user {user_id}: {str(e)}", "DEACTIVATION_ERROR")
            return False
    
    def activate_user(self, user_id):
        """Activate user account"""
        try:
            query = "UPDATE instructors SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE instructor_id = ?"
            result = self.db_service.execute_query(query, (user_id,))
            if result:
                self.log_activity(user_id, 'account_activated', 'Account activated')
                return True
            return False
        except Exception as e:
            log_error(f"Error activating user {user_id}: {str(e)}", "ACTIVATION_ERROR")
            return False