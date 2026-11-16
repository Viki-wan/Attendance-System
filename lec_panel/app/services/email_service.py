"""
Email Service
Comprehensive email handling for Face Recognition Attendance System
Supports notifications, alerts, reports, and bulk emails
"""
from flask import current_app, render_template, url_for
from flask_mail import Mail, Message
from threading import Thread
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

mail = Mail()


class EmailService:
    """Comprehensive email service for attendance system"""
    
    # ==========================================
    # Core Email Functions
    # ==========================================
    
    @staticmethod
    def send_async_email(app, msg):
        """Send email asynchronously in background thread"""
        with app.app_context():
            try:
                mail.send(msg)
                logger.info(f"Email sent successfully to {msg.recipients}")
                return True
            except Exception as e:
                logger.error(f"Failed to send email: {str(e)}")
                return False
    
    @staticmethod
    def send_email(subject: str, 
                   recipients: List[str], 
                   text_body: Optional[str] = None, 
                   html_body: Optional[str] = None,
                   sender: Optional[str] = None,
                   cc: Optional[List[str]] = None,
                   bcc: Optional[List[str]] = None,
                   attachments: Optional[List[Tuple[str, str, bytes]]] = None,
                   sync: bool = False) -> bool:
        """
        Send email with full feature support
        
        Args:
            subject: Email subject line
            recipients: List of recipient email addresses
            text_body: Plain text email body
            html_body: HTML email body
            sender: Sender email (defaults to MAIL_DEFAULT_SENDER)
            cc: Carbon copy recipients
            bcc: Blind carbon copy recipients
            attachments: List of (filename, content_type, data) tuples
            sync: If True, send synchronously (blocks); if False, send async
            
        Returns:
            bool: True if email queued/sent successfully
        """
        try:
            # Filter out None/empty emails
            recipients = [r for r in recipients if r and '@' in r]
            if not recipients:
                logger.warning("No valid recipients provided for email")
                return False
            
            sender = sender or current_app.config.get('MAIL_DEFAULT_SENDER')
            
            msg = Message(
                subject=subject,
                recipients=recipients,
                body=text_body,
                html=html_body,
                sender=sender,
                cc=cc or [],
                bcc=bcc or []
            )
            
            # Add attachments if provided
            if attachments:
                for filename, content_type, data in attachments:
                    msg.attach(filename, content_type, data)
            
            # Send email
            if sync:
                mail.send(msg)
                logger.info(f"Email sent synchronously to {recipients}")
            else:
                app = current_app._get_current_object()
                Thread(target=EmailService.send_async_email, args=(app, msg)).start()
                logger.info(f"Email queued for async delivery to {recipients}")
            
            return True
            
        except Exception as e:
            logger.error(f"Email sending error: {str(e)}")
            return False
    
    @staticmethod
    def send_bulk_email(subject: str, 
                       recipients_data: List[Dict],
                       template: str,
                       sender: Optional[str] = None) -> Dict:
        """
        Send personalized bulk emails
        
        Args:
            subject: Email subject
            recipients_data: List of dicts with 'email' and template variables
            template: Template name (without .html)
            sender: Sender email
            
        Returns:
            dict: {'sent': count, 'failed': count, 'errors': []}
        """
        results = {'sent': 0, 'failed': 0, 'errors': []}
        
        for data in recipients_data:
            try:
                email = data.get('email')
                if not email:
                    continue
                
                html_body = render_template(f'emails/{template}.html', **data)
                text_body = render_template(f'emails/{template}.txt', **data)
                
                success = EmailService.send_email(
                    subject=subject,
                    recipients=[email],
                    text_body=text_body,
                    html_body=html_body,
                    sender=sender
                )
                
                if success:
                    results['sent'] += 1
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"{email}: {str(e)}")
                logger.error(f"Bulk email error for {email}: {str(e)}")
        
        return results
    
    # ==========================================
    # Authentication & Account Management
    # ==========================================
    
    @staticmethod
    def send_welcome_email(instructor) -> bool:
        """Send welcome email to new instructor"""
        if not instructor.email:
            logger.warning(f"No email for instructor {instructor.instructor_id}")
            return False
        
        subject = f"Welcome to {current_app.config['APP_NAME']}"
        
        html_body = render_template(
            'emails/welcome.html',
            instructor=instructor,
            app_name=current_app.config['APP_NAME'],
            login_url=url_for('auth.login', _external=True)
        )
        
        text_body = f"""
Welcome to {current_app.config['APP_NAME']}!

Dear {instructor.instructor_name},

Your instructor account has been created successfully.

Login Credentials:
------------------
Instructor ID: {instructor.instructor_id}
Default Password: {instructor.instructor_id}

⚠️ IMPORTANT: For security reasons, you MUST change your password on first login.

Login at: {url_for('auth.login', _external=True)}

If you have any questions, please contact the system administrator.

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_password_changed_notification(instructor) -> bool:
        """Notify instructor that password was changed"""
        if not instructor.email:
            return False
        
        subject = "Password Changed Successfully"
        
        text_body = f"""
Hello {instructor.instructor_name},

Your password has been changed successfully.

Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

If you did not make this change, please contact the administrator immediately.

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/password_changed.html',
            instructor=instructor,
            timestamp=datetime.utcnow()
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_password_reset_email(instructor, new_password: str) -> bool:
        """Send password reset notification with new password"""
        if not instructor.email:
            return False
        
        subject = "Password Reset - Attendance System"
        
        text_body = f"""
Hello {instructor.instructor_name},

Your password has been reset by an administrator.

New Password: {new_password}

⚠️ IMPORTANT: Please log in and change this password immediately.

Login at: {url_for('auth.login', _external=True)}

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/password_reset.html',
            instructor=instructor,
            new_password=new_password,
            login_url=url_for('auth.login', _external=True)
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_account_deactivated_email(instructor, reason: Optional[str] = None) -> bool:
        """Notify instructor of account deactivation"""
        if not instructor.email:
            return False
        
        subject = "Account Deactivated"
        
        reason_text = f"\n\nReason: {reason}" if reason else ""
        
        text_body = f"""
Hello {instructor.instructor_name},

Your account has been deactivated.{reason_text}

If you believe this is an error, please contact the administrator.

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/account_deactivated.html',
            instructor=instructor,
            reason=reason
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_account_activated_email(instructor) -> bool:
        """Notify instructor of account activation"""
        if not instructor.email:
            return False
        
        subject = "Account Activated"
        
        text_body = f"""
Hello {instructor.instructor_name},

Your account has been activated. You can now log in to the system.

Login at: {url_for('auth.login', _external=True)}

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/account_activated.html',
            instructor=instructor,
            login_url=url_for('auth.login', _external=True)
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    # ==========================================
    # Session Management
    # ==========================================
    
    @staticmethod
    def send_session_reminder(instructor, session, hours_before: int = 1) -> bool:
        """Send session reminder to instructor"""
        if not instructor.email:
            return False
        
        subject = f"Session Reminder - {session.class_.class_name}"
        
        text_body = f"""
Hello {instructor.instructor_name},

This is a reminder for your upcoming class session.

Session Details:
---------------
Class: {session.class_.class_name}
Course: {session.class_.course_code}
Date: {session.date.strftime('%A, %B %d, %Y')}
Time: {session.start_time.strftime('%I:%M %p')} - {session.end_time.strftime('%I:%M %p')}
Duration: {session.duration_minutes} minutes
Expected Students: {session.total_students}

The session starts in approximately {hours_before} hour(s).

View session: {url_for('sessions.session_detail', session_id=session.session_id, _external=True)}

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/session_reminder.html',
            instructor=instructor,
            session=session,
            hours_before=hours_before
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_session_started_notification(instructor, session) -> bool:
        """Notify that a session has started"""
        if not instructor.email:
            return False
        
        subject = f"Session Started - {session.class_.class_name}"
        
        text_body = f"""
Hello {instructor.instructor_name},

Your class session has been started.

Session Details:
---------------
Class: {session.class_.class_name}
Started at: {datetime.utcnow().strftime('%I:%M %p')}

Monitor attendance: {url_for('attendance.live_attendance', session_id=session.session_id, _external=True)}

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/session_started.html',
            instructor=instructor,
            session=session
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_session_completed_summary(instructor, session, summary: Dict) -> bool:
        """Send session completion summary"""
        if not instructor.email:
            return False
        
        subject = f"Session Completed - {session.class_.class_name}"
        
        text_body = f"""
Hello {instructor.instructor_name},

Your class session has been completed.

Session Summary:
---------------
Class: {session.class_.class_name}
Date: {session.date.strftime('%A, %B %d, %Y')}
Duration: {session.duration_minutes} minutes

Attendance Statistics:
---------------------
Total Students: {summary['total']}
Present: {summary['present']} ({summary['attendance_rate']}%)
Absent: {summary['absent']}
Late: {summary['late']}
Excused: {summary['excused']}

View detailed report: {url_for('sessions.session_detail', session_id=session.session_id, _external=True)}

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/session_completed.html',
            instructor=instructor,
            session=session,
            summary=summary
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_session_cancelled_notification(instructor, session, reason: str) -> bool:
        """Notify about session cancellation"""
        if not instructor.email:
            return False
        
        subject = f"Session Cancelled - {session.class_.class_name}"
        
        text_body = f"""
Hello {instructor.instructor_name},

A class session has been cancelled.

Session Details:
---------------
Class: {session.class_.class_name}
Date: {session.date.strftime('%A, %B %d, %Y')}
Time: {session.start_time.strftime('%I:%M %p')} - {session.end_time.strftime('%I:%M %p')}

Reason: {reason}

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/session_cancelled.html',
            instructor=instructor,
            session=session,
            reason=reason
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    # ==========================================
    # Attendance Alerts
    # ==========================================
    
    @staticmethod
    def send_low_attendance_alert(instructor, student, course_code: str, 
                                 attendance_stats: Dict) -> bool:
        """Alert instructor about student's low attendance"""
        if not instructor.email:
            return False
        
        subject = f"⚠️ Low Attendance Alert - {student.full_name}"
        
        text_body = f"""
Hello {instructor.instructor_name},

ATTENDANCE ALERT

Student {student.full_name} ({student.student_id}) has low attendance in {course_code}.

Attendance Statistics:
---------------------
Total Sessions: {attendance_stats['total_sessions']}
Present: {attendance_stats['present']}
Absent: {attendance_stats['absent']}
Late: {attendance_stats['late']}
Attendance Rate: {attendance_stats['attendance_rate']}%

⚠️ This is below the required threshold of 75%.

Student Contact:
---------------
Email: {student.email or 'Not provided'}
Phone: {student.phone or 'Not provided'}

Please take appropriate action.

View details: {url_for('reports.student_attendance', student_id=student.student_id, _external=True)}

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/low_attendance_alert.html',
            instructor=instructor,
            student=student,
            course_code=course_code,
            stats=attendance_stats
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_student_absent_notification(student, session) -> bool:
        """Notify student about being marked absent"""
        if not student.email:
            return False
        
        subject = f"Absence Notice - {session.class_.class_name}"
        
        text_body = f"""
Hello {student.full_name},

You were marked ABSENT for the following session:

Session Details:
---------------
Class: {session.class_.class_name}
Course: {session.class_.course_code}
Date: {session.date.strftime('%A, %B %d, %Y')}
Time: {session.start_time.strftime('%I:%M %p')}

If this is an error, please contact your instructor immediately.

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/student_absent.html',
            student=student,
            session=session
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[student.email],
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_attendance_correction_notification(student, session, 
                                               old_status: str, new_status: str, 
                                               corrected_by: str) -> bool:
        """Notify student about attendance correction"""
        if not student.email:
            return False
        
        subject = f"Attendance Corrected - {session.class_.class_name}"
        
        text_body = f"""
Hello {student.full_name},

Your attendance has been corrected for:

Session Details:
---------------
Class: {session.class_.class_name}
Date: {session.date.strftime('%A, %B %d, %Y')}

Status Changed:
--------------
Previous: {old_status}
Updated to: {new_status}
Corrected by: {corrected_by}

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/attendance_corrected.html',
            student=student,
            session=session,
            old_status=old_status,
            new_status=new_status,
            corrected_by=corrected_by
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[student.email],
            text_body=text_body,
            html_body=html_body
        )
    
    # ==========================================
    # Reports & Analytics
    # ==========================================
    
    @staticmethod
    def send_attendance_report(instructor, report_type: str, 
                              period: str, report_file_path: Optional[str] = None) -> bool:
        """Send attendance report via email"""
        if not instructor.email:
            return False
        
        subject = f"Attendance Report - {report_type} ({period})"
        
        text_body = f"""
Hello {instructor.instructor_name},

Your requested attendance report is ready.

Report Details:
--------------
Type: {report_type}
Period: {period}
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

{f'The report is attached to this email.' if report_file_path else 'View online in your dashboard.'}

Access dashboard: {url_for('reports.index', _external=True)}

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/attendance_report.html',
            instructor=instructor,
            report_type=report_type,
            period=period
        )
        
        attachments = []
        if report_file_path:
            try:
                with open(report_file_path, 'rb') as f:
                    file_ext = report_file_path.split('.')[-1]
                    content_type = 'application/pdf' if file_ext == 'pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    attachments.append((
                        f'attendance_report.{file_ext}',
                        content_type,
                        f.read()
                    ))
            except Exception as e:
                logger.error(f"Failed to attach report file: {str(e)}")
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body,
            attachments=attachments if attachments else None
        )
    
    @staticmethod
    def send_weekly_summary(instructor, summary_data: Dict) -> bool:
        """Send weekly attendance summary"""
        if not instructor.email:
            return False
        
        subject = f"Weekly Summary - Week of {summary_data['week_start']}"
        
        text_body = f"""
Hello {instructor.instructor_name},

Here's your weekly attendance summary:

Week: {summary_data['week_start']} to {summary_data['week_end']}

Summary:
--------
Total Sessions: {summary_data['total_sessions']}
Average Attendance Rate: {summary_data['avg_attendance_rate']}%
Total Students Tracked: {summary_data['total_students']}
Low Attendance Alerts: {summary_data['low_attendance_count']}

Top Performing Class: {summary_data['best_class']}
Needs Attention: {summary_data['attention_needed']}

View detailed analytics: {url_for('dashboard.index', _external=True)}

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/weekly_summary.html',
            instructor=instructor,
            summary=summary_data
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    @staticmethod
    def send_monthly_report(instructor, report_data: Dict, 
                           report_file_path: Optional[str] = None) -> bool:
        """Send comprehensive monthly report"""
        if not instructor.email:
            return False
        
        subject = f"Monthly Report - {report_data['month']} {report_data['year']}"
        
        text_body = f"""
Hello {instructor.instructor_name},

Your monthly attendance report for {report_data['month']} {report_data['year']} is ready.

Monthly Statistics:
------------------
Total Sessions: {report_data['total_sessions']}
Average Attendance: {report_data['avg_attendance']}%
Total Classes: {report_data['total_classes']}
Active Students: {report_data['active_students']}

Performance Trends:
------------------
Best Day: {report_data['best_day']} ({report_data['best_day_rate']}%)
Worst Day: {report_data['worst_day']} ({report_data['worst_day_rate']}%)

{f'Detailed report attached.' if report_file_path else 'View online in dashboard.'}

Access dashboard: {url_for('dashboard.index', _external=True)}

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/monthly_report.html',
            instructor=instructor,
            report=report_data
        )
        
        attachments = []
        if report_file_path:
            try:
                with open(report_file_path, 'rb') as f:
                    attachments.append((
                        f'monthly_report_{report_data["month"]}_{report_data["year"]}.pdf',
                        'application/pdf',
                        f.read()
                    ))
            except Exception as e:
                logger.error(f"Failed to attach monthly report: {str(e)}")
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body,
            attachments=attachments if attachments else None
        )
    
    # ==========================================
    # System Notifications
    # ==========================================
    
    @staticmethod
    def send_system_maintenance_notice(instructors: List, 
                                      start_time: datetime, 
                                      duration_hours: int,
                                      reason: str) -> Dict:
        """Notify about scheduled system maintenance"""
        subject = "⚠️ Scheduled System Maintenance"
        
        recipients_data = []
        for instructor in instructors:
            if instructor.email:
                recipients_data.append({
                    'email': instructor.email,
                    'instructor_name': instructor.instructor_name,
                    'start_time': start_time,
                    'end_time': start_time + timedelta(hours=duration_hours),
                    'duration': duration_hours,
                    'reason': reason
                })
        
        return EmailService.send_bulk_email(
            subject=subject,
            recipients_data=recipients_data,
            template='system_maintenance'
        )
    
    @staticmethod
    def send_face_encoding_failure_alert(instructor, student, error_msg: str) -> bool:
        """Alert about face encoding failure"""
        if not instructor.email:
            return False
        
        subject = f"⚠️ Face Encoding Failed - {student.full_name}"
        
        text_body = f"""
Hello {instructor.instructor_name},

Face encoding registration failed for student:

Student: {student.full_name} ({student.student_id})
Error: {error_msg}

The student will need to re-register their face photo.

Best regards,
{current_app.config['APP_NAME']} Team
        """
        
        html_body = render_template(
            'emails/face_encoding_failure.html',
            instructor=instructor,
            student=student,
            error=error_msg
        )
        
        return EmailService.send_email(
            subject=subject,
            recipients=[instructor.email],
            text_body=text_body,
            html_body=html_body
        )
    
    # ==========================================
    # Utility Functions
    # ==========================================
    
    @staticmethod
    def test_email_configuration() -> Tuple[bool, str]:
        """Test if email is configured correctly"""
        try:
            config = current_app.config
            
            # Check required config
            required = ['MAIL_SERVER', 'MAIL_PORT', 'MAIL_USERNAME', 'MAIL_PASSWORD']
            missing = [k for k in required if not config.get(k)]
            
            if missing:
                return False, f"Missing configuration: {', '.join(missing)}"
            
            # Try sending test email
            test_email = config.get('MAIL_USERNAME')
            success = EmailService.send_email(
                subject="Email Configuration Test",
                recipients=[test_email],
                text_body="This is a test email to verify email configuration.",
                html_body="<p>This is a test email to verify email configuration.</p>",
                sync=True
            )
            
            if success:
                return True, "Email configuration is working correctly"
            else:
                return False, "Failed to send test email"
                
        except Exception as e:
            return False, f"Email configuration error: {str(e)}"
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))