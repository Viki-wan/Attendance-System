"""
Authentication Service - FIXED VERSION
Handles all authentication-related business logic
"""
from datetime import datetime
from flask import current_app, session
from flask_login import login_user, logout_user, current_user
from app import db
from app.models.user import Instructor
from config.constants import USER_TYPES, ACTIVITY_TYPES
import re


class AuthService:
    """Service class for authentication operations"""
    
    @staticmethod
    def login(identifier, password, remember=False):
        """
        Authenticate an instructor and create a session.
        Checks if first-time login and requires setup.
        
        Args:
            identifier (str): Email, phone, or instructor_id
            password (str): Plain text password
            remember (bool): Whether to remember the user
            
        Returns:
            tuple: (success: bool, message: str, instructor: Instructor or None, first_time: bool)
        """
        # Find instructor by identifier (could be email, phone, or ID)
        instructor = AuthService._find_instructor(identifier)
        
        if not instructor:
            current_app.logger.warning(f"Login attempt with unknown identifier: {identifier}")
            return False, "Invalid credentials", None, False
        
        # Check if account is active
        if not instructor.is_active:
            current_app.logger.warning(f"Login attempt on inactive account: {instructor.instructor_id}")
            return False, "Account is deactivated. Please contact administrator.", None, False
        
        # Verify password
        if not instructor.check_password(password):
            current_app.logger.warning(f"Failed login attempt for: {instructor.instructor_id}")
            AuthService._log_activity(
                instructor.instructor_id,
                ACTIVITY_TYPES.get('LOGIN_FAILED', 'login_failed'),
                f"Failed login attempt from identifier: {identifier}"
            )
            return False, "Invalid credentials", None, False
        
        # FIXED: Check if first-time login
        # First-time means: never logged in before
        is_first_time = instructor.last_login is None
        
        # Login successful
        login_user(instructor, remember=remember)
        
        if not is_first_time:
            # Normal login - update timestamp
            instructor.update_last_login()
        
        # Log successful login
        AuthService._log_activity(
            instructor.instructor_id,
            ACTIVITY_TYPES.get('LOGIN', 'login'),
            f"Successful login from identifier: {identifier}" + (" (First-time setup required)" if is_first_time else "")
        )
        
        current_app.logger.info(f"Successful login: {instructor.instructor_id}" + (" - First-time" if is_first_time else ""))
        
        return True, "Login successful", instructor, is_first_time
    
    @staticmethod
    def logout():
        """
        Logout the current user and clear session.
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if current_user.is_authenticated:
            instructor_id = current_user.instructor_id
            
            # Log logout activity
            AuthService._log_activity(
                instructor_id,
                ACTIVITY_TYPES.get('LOGOUT', 'logout'),
                "User logged out"
            )
            
            current_app.logger.info(f"User logged out: {instructor_id}")
            logout_user()
            session.clear()
            
            return True, "Logged out successfully"
        
        return False, "No active session"
    
    @staticmethod
    def log_activity(user_id, user_type, activity_type, description):
        """Public wrapper for logging activity"""
        return AuthService._log_activity(user_id, activity_type, description)
    
    @staticmethod
    def create_instructor(instructor_id, instructor_name, phone, email=None, faculty=None, created_by_admin=True):
        """
        Create a new instructor (Admin function).
        Sets default password as instructor_id, requires first-time setup.
        
        Args:
            instructor_id (str): Unique instructor ID
            instructor_name (str): Full name
            phone (str): Phone number
            email (str, optional): Email address
            faculty (str, optional): Faculty name
            created_by_admin (bool): Whether created by admin
            
        Returns:
            tuple: (success: bool, message: str, instructor: Instructor or None)
        """
        # Validate inputs
        is_valid, validation_message = AuthService._validate_instructor_creation(
            instructor_id, instructor_name, phone, email
        )
        
        if not is_valid:
            return False, validation_message, None
        
        # Check if instructor already exists
        if Instructor.query.get(instructor_id):
            return False, f"Instructor ID '{instructor_id}' already exists", None
        
        if Instructor.get_by_phone(phone):
            return False, f"Phone number '{phone}' is already registered", None
        
        if email and Instructor.get_by_email(email):
            return False, f"Email '{email}' is already registered", None
        
        try:
            # Create new instructor with default password (instructor_id)
            instructor = Instructor(
                instructor_id=instructor_id,
                instructor_name=instructor_name,
                phone=phone,
                email=email,
                faculty=faculty,
                is_active=1  # FIXED: Ensure active
            )
            # Set default password as instructor_id
            instructor.set_password(instructor_id)
            
            db.session.add(instructor)
            db.session.commit()
            
            # Log instructor creation
            AuthService._log_activity(
                instructor_id,
                ACTIVITY_TYPES.get('ACCOUNT_CREATED', 'account_created'),
                f"New instructor created by {'admin' if created_by_admin else 'system'}: {instructor_name}"
            )
            
            current_app.logger.info(f"New instructor created: {instructor_id}")
            
            return True, "Instructor created successfully. Default password is the instructor ID.", instructor
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Instructor creation error: {str(e)}")
            return False, f"Instructor creation failed: {str(e)}", None
    
    @staticmethod
    def complete_first_time_setup(instructor_id, new_password, email=None, phone=None):
        """
        Complete first-time account setup.
        Requires new password and allows updating email/phone.
        
        Args:
            instructor_id (str): Instructor ID
            new_password (str): New password (must be different from default)
            email (str, optional): Updated email
            phone (str, optional): Updated phone
            
        Returns:
            tuple: (success: bool, message: str)
        """
        instructor = Instructor.query.get(instructor_id)
        
        if not instructor:
            return False, "Instructor not found"
        
        # Validate new password
        if not AuthService._validate_password(new_password):
            return False, "Password must be at least 8 characters with letters and numbers"
        
        # FIXED: Check if new password is same as old password
        if instructor.check_password(new_password):
            return False, "New password must be different from your current password"
        
        try:
            # Update password
            instructor.set_password(new_password)
            
            # Update email if provided
            if email and email.strip():
                if not AuthService._validate_email(email):
                    return False, "Invalid email format"
                
                # Check if email is already used
                existing = Instructor.get_by_email(email)
                if existing and existing.instructor_id != instructor_id:
                    return False, "Email already in use"
                
                instructor.email = email
            
            # Update phone if provided
            if phone and phone.strip():
                if not AuthService._validate_phone(phone):
                    return False, "Invalid phone number format"
                
                # Check if phone is already used
                existing = Instructor.get_by_phone(phone)
                if existing and existing.instructor_id != instructor_id:
                    return False, "Phone number already in use"
                
                instructor.phone = phone
            
            # Mark first login - IMPORTANT!
            instructor.update_last_login()
            instructor.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Log setup completion
            AuthService._log_activity(
                instructor_id,
                ACTIVITY_TYPES.get('PROFILE_UPDATED', 'profile_updated'),
                "First-time account setup completed"
            )
            
            current_app.logger.info(f"First-time setup completed for: {instructor_id}")
            
            return True, "Account setup completed successfully"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"First-time setup error: {str(e)}")
            return False, f"Setup failed: {str(e)}"

    @staticmethod
    def change_password(instructor_id, old_password, new_password):
        """
        Change instructor password with verification.
        
        Args:
            instructor_id (str): Instructor ID
            old_password (str): Current password
            new_password (str): New password
            
        Returns:
            tuple: (success: bool, message: str)
        """
        instructor = Instructor.query.get(instructor_id)
        
        if not instructor:
            return False, "Instructor not found"
        
        # Validate new password
        if not AuthService._validate_password(new_password):
            return False, "Password must be at least 8 characters with letters and numbers"
        
        # Change password
        success, message = instructor.change_password(old_password, new_password)
        
        if success:
            # Log password change
            AuthService._log_activity(
                instructor_id,
                ACTIVITY_TYPES.get('PASSWORD_CHANGED', 'password_changed'),
                "Password changed successfully"
            )
            current_app.logger.info(f"Password changed for: {instructor_id}")
        
        return success, message

    
    @staticmethod
    def reset_password(instructor_id, new_password):
        """
        Admin reset of instructor password (no old password required).
        
        Args:
            instructor_id (str): Instructor ID
            new_password (str): New password
            
        Returns:
            tuple: (success: bool, message: str)
        """
        instructor = Instructor.query.get(instructor_id)
        
        if not instructor:
            return False, "Instructor not found"
        
        # Validate new password
        if not AuthService._validate_password(new_password):
            return False, "Password must be at least 8 characters with letters and numbers"
        
        try:
            instructor.set_password(new_password)
            instructor.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Log password reset
            AuthService._log_activity(
                instructor_id,
                ACTIVITY_TYPES.get('PASSWORD_RESET', 'password_reset'),
                "Password reset by administrator"
            )
            
            current_app.logger.info(f"Password reset for: {instructor_id}")
            
            return True, "Password reset successfully"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Password reset error: {str(e)}")
            return False, "Password reset failed"
    
    @staticmethod
    def update_profile(instructor, **kwargs):
        """
        Update instructor profile information.
        
        Args:
            instructor: Instructor object or instructor_id string
            **kwargs: Fields to update
            
        Returns:
            tuple: (success: bool, message: str)
        """
        # Handle both instructor object and instructor_id
        if isinstance(instructor, str):
            instructor_obj = Instructor.query.get(instructor)
        else:
            instructor_obj = instructor
        
        if not instructor_obj:
            return False, "Instructor not found"
        
        try:
            # Validate email if provided
            if 'email' in kwargs and kwargs['email']:
                if not AuthService._validate_email(kwargs['email']):
                    return False, "Invalid email format"
                
                # Check if email is already used by another instructor
                existing = Instructor.get_by_email(kwargs['email'])
                if existing and existing.instructor_id != instructor_obj.instructor_id:
                    return False, "Email already in use"
            
            # Validate phone if provided
            if 'phone' in kwargs and kwargs['phone']:
                if not AuthService._validate_phone(kwargs['phone']):
                    return False, "Invalid phone number format"
                
                # Check if phone is already used by another instructor
                existing = Instructor.get_by_phone(kwargs['phone'])
                if existing and existing.instructor_id != instructor_obj.instructor_id:
                    return False, "Phone number already in use"
            
            instructor_obj.update_profile(**kwargs)
            
            # Log profile update
            AuthService._log_activity(
                instructor_obj.instructor_id,
                ACTIVITY_TYPES.get('PROFILE_UPDATED', 'profile_updated'),
                f"Profile updated: {', '.join(kwargs.keys())}"
            )
            
            return True, "Profile updated successfully"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Profile update error: {str(e)}")
            return False, "Profile update failed"
    
    @staticmethod
    def deactivate_account(instructor_id, reason=None):
        """
        Deactivate an instructor account.
        
        Args:
            instructor_id (str): Instructor ID
            reason (str, optional): Reason for deactivation
            
        Returns:
            tuple: (success: bool, message: str)
        """
        instructor = Instructor.query.get(instructor_id)
        
        if not instructor:
            return False, "Instructor not found"
        
        try:
            instructor.deactivate()
            
            # Log deactivation
            description = f"Account deactivated"
            if reason:
                description += f": {reason}"
            
            AuthService._log_activity(
                instructor_id,
                ACTIVITY_TYPES.get('ACCOUNT_DEACTIVATED', 'account_deactivated'),
                description
            )
            
            current_app.logger.info(f"Account deactivated: {instructor_id}")
            return True, "Account deactivated successfully"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Deactivation error: {str(e)}")
            return False, "Account deactivation failed"
    
    @staticmethod
    def activate_account(instructor_id):
        """
        Activate an instructor account.
        
        Args:
            instructor_id (str): Instructor ID
            
        Returns:
            tuple: (success: bool, message: str)
        """
        instructor = Instructor.query.get(instructor_id)
        
        if not instructor:
            return False, "Instructor not found"
        
        try:
            instructor.activate()
            
            # Log activation
            AuthService._log_activity(
                instructor_id,
                ACTIVITY_TYPES.get('ACCOUNT_ACTIVATED', 'account_activated'),
                "Account activated"
            )
            
            current_app.logger.info(f"Account activated: {instructor_id}")
            return True, "Account activated successfully"
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Activation error: {str(e)}")
            return False, "Account activation failed"
    
    # Private helper methods
    
    @staticmethod
    def _find_instructor(identifier):
        """
        Find instructor by ID, email, or phone.
        
        Args:
            identifier (str): Instructor ID, email, or phone
            
        Returns:
            Instructor: Instructor object or None
        """
        if not identifier:
            return None
            
        identifier = identifier.strip()
        
        # Try by ID first
        instructor = Instructor.query.get(identifier)
        if instructor:
            return instructor
        
        # Try by email
        if '@' in identifier:
            instructor = Instructor.get_by_email(identifier)
            if instructor:
                return instructor
        
        # Try by phone (remove spaces and dashes)
        clean_phone = re.sub(r'[\s\-\(\)]', '', identifier)
        instructor = Instructor.get_by_phone(clean_phone)
        if instructor:
            return instructor
            
        # Try original identifier as phone
        instructor = Instructor.get_by_phone(identifier)
        return instructor
    
    @staticmethod
    def _validate_instructor_creation(instructor_id, instructor_name, phone, email):
        """Validate instructor creation inputs"""
        
        # Validate instructor_id
        if not instructor_id or len(instructor_id.strip()) == 0:
            return False, "Instructor ID is required"
        
        if len(instructor_id) > 50:
            return False, "Instructor ID must be 50 characters or less"
        
        # Validate name
        if not instructor_name or len(instructor_name.strip()) == 0:
            return False, "Instructor name is required"
        
        if len(instructor_name) > 200:
            return False, "Instructor name must be 200 characters or less"
        
        # Validate phone
        if not AuthService._validate_phone(phone):
            return False, "Invalid phone number format"
        
        # Validate email if provided
        if email and not AuthService._validate_email(email):
            return False, "Invalid email format"
        
        return True, "Validation passed"
    
    @staticmethod
    def _validate_email(email):
        """Validate email format"""
        if not email:
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def _validate_phone(phone):
        """Validate phone number format"""
        if not phone:
            return False
        
        # Remove common separators
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Check if it's 10-15 digits
        return len(cleaned) >= 10 and len(cleaned) <= 15 and cleaned.isdigit()
    
    @staticmethod
    def _validate_password(password):
        """
        Validate password strength.
        Must be at least 8 characters with letters and numbers.
        """
        if not password or len(password) < 8:
            return False
        
        # Check for at least one letter and one number
        has_letter = any(c.isalpha() for c in password)
        has_number = any(c.isdigit() for c in password)
        
        return has_letter and has_number
    
    @staticmethod
    def _log_activity(user_id, activity_type, description):
        """
        Log user activity to database.
        
        Args:
            user_id (str): User ID
            activity_type (str): Activity type constant
            description (str): Activity description
        """
        try:
            from app.models.activity_log import ActivityLog
            
            log_entry = ActivityLog(
                user_id=user_id,
                user_type=USER_TYPES.get('INSTRUCTOR', 'instructor'),
                activity_type=activity_type,
                description=description,
                timestamp=datetime.utcnow()
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            # Don't fail the main operation if logging fails
            current_app.logger.error(f"Activity logging error: {str(e)}")
            try:
                db.session.rollback()
            except:
                pass