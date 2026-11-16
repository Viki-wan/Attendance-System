"""
Help and Support Blueprint
Provides documentation, FAQs, and support resources for instructors
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.decorators.auth import active_account_required
from app.models.activity_log import ActivityLog
from app import db

help_bp = Blueprint('help', __name__, url_prefix='/help')


@help_bp.route('/')
@login_required
@active_account_required
def index():
    """Main help center page"""
    # Log activity
    ActivityLog.log_activity(
        user_id=current_user.instructor_id,
        user_type='instructor',
        activity_type='help_accessed',
        description='Accessed help center'
    )
    
    return render_template('help/index.html', title='Help & Support')


@help_bp.route('/faq')
@login_required
@active_account_required
def faq():
    """Frequently Asked Questions page"""
    faqs = [
        {
            'category': 'Getting Started',
            'questions': [
                {
                    'q': 'How do I start an attendance session?',
                    'a': 'Navigate to Dashboard and click "Start Attendance" on any scheduled session, or go to Sessions > Create New Session.'
                },
                {
                    'q': 'What are the camera requirements?',
                    'a': 'You need a webcam with at least 720p resolution. Ensure good lighting for accurate face recognition.'
                },
                {
                    'q': 'How do I add students to my class?',
                    'a': 'Students are automatically enrolled based on class assignments. Contact admin for bulk imports.'
                }
            ]
        },
        {
            'category': 'Attendance Management',
            'questions': [
                {
                    'q': 'Can I manually mark attendance?',
                    'a': 'Yes, go to Sessions > View Session > Manual Corrections to adjust attendance records.'
                },
                {
                    'q': 'How accurate is face recognition?',
                    'a': 'The system uses state-of-the-art face recognition with 95%+ accuracy under good lighting conditions.'
                },
                {
                    'q': 'What if a student is not recognized?',
                    'a': 'You can manually mark them present or ask them to re-register their face with better quality photos.'
                }
            ]
        },
        {
            'category': 'Reports & Analytics',
            'questions': [
                {
                    'q': 'How do I generate attendance reports?',
                    'a': 'Go to Reports, select date range and class, then choose your export format (PDF, Excel, or CSV).'
                },
                {
                    'q': 'Can I see student attendance trends?',
                    'a': 'Yes, the Statistics page shows detailed trends and analytics for all your classes.'
                },
                {
                    'q': 'How do I set up low attendance alerts?',
                    'a': 'Go to Preferences > Notifications to configure automatic alerts for students with low attendance.'
                }
            ]
        },
        {
            'category': 'Technical Issues',
            'questions': [
                {
                    'q': 'Camera not working?',
                    'a': 'Check browser permissions, ensure no other app is using the camera, and refresh the page.'
                },
                {
                    'q': 'Session won\'t start?',
                    'a': 'Verify the session is within the scheduled time window (15 minutes before to 30 minutes after start time).'
                },
                {
                    'q': 'Data not saving?',
                    'a': 'Check your internet connection and try again. Contact support if the issue persists.'
                }
            ]
        }
    ]
    
    return render_template('help/faq.html', title='FAQ', faqs=faqs)


@help_bp.route('/documentation')
@login_required
@active_account_required
def documentation():
    """System documentation page"""
    docs_sections = [
        {
            'title': 'Session Management',
            'icon': 'calendar-event',
            'description': 'Learn how to create, manage, and dismiss sessions',
            'topics': [
                'Creating new sessions',
                'Starting attendance',
                'Session dismissals and rescheduling',
                'Bulk session creation from timetable'
            ]
        },
        {
            'title': 'Face Recognition',
            'icon': 'camera',
            'description': 'Understanding the face recognition system',
            'topics': [
                'Camera setup and positioning',
                'Student face registration',
                'Recognition accuracy factors',
                'Troubleshooting recognition issues'
            ]
        },
        {
            'title': 'Reports',
            'icon': 'file-earmark-bar-graph',
            'description': 'Generate and export attendance reports',
            'topics': [
                'Session summary reports',
                'Student attendance history',
                'Course analytics',
                'Export formats and scheduling'
            ]
        },
        {
            'title': 'Preferences',
            'icon': 'gear',
            'description': 'Customize your experience',
            'topics': [
                'Dashboard layout options',
                'Notification settings',
                'Auto-refresh intervals',
                'Theme customization'
            ]
        }
    ]
    
    return render_template('help/documentation.html', 
                         title='Documentation', 
                         sections=docs_sections)


@help_bp.route('/tutorials')
@login_required
@active_account_required
def tutorials():
    """Video tutorials and guides"""
    tutorials = [
        {
            'title': 'Quick Start Guide',
            'duration': '5 min',
            'description': 'Get started with the system in 5 minutes',
            'thumbnail': 'quickstart.jpg',
            'topics': ['Login', 'Dashboard overview', 'First session']
        },
        {
            'title': 'Starting Your First Session',
            'duration': '8 min',
            'description': 'Step-by-step guide to starting attendance',
            'thumbnail': 'first_session.jpg',
            'topics': ['Session creation', 'Camera setup', 'Live monitoring']
        },
        {
            'title': 'Managing Attendance Records',
            'duration': '10 min',
            'description': 'Learn to correct and manage attendance',
            'thumbnail': 'manage_attendance.jpg',
            'topics': ['Manual corrections', 'Bulk operations', 'History review']
        },
        {
            'title': 'Generating Reports',
            'duration': '7 min',
            'description': 'Create and export comprehensive reports',
            'thumbnail': 'reports.jpg',
            'topics': ['Report types', 'Filters', 'Export options']
        }
    ]
    
    return render_template('help/tutorials.html', 
                         title='Tutorials', 
                         tutorials=tutorials)


@help_bp.route('/contact', methods=['GET', 'POST'])
@login_required
@active_account_required
def contact():
    """Contact support page"""
    if request.method == 'POST':
        subject = request.form.get('subject')
        message = request.form.get('message')
        priority = request.form.get('priority', 'normal')
        
        # Log support request
        ActivityLog.log_activity(
            user_id=current_user.instructor_id,
            user_type='instructor',
            activity_type='support_request',
            description=f'Support request: {subject}'
        )
        
        # In production, send email to support team
        # For now, just log it
        flash('Your support request has been submitted. We\'ll get back to you soon!', 'success')
        return redirect(url_for('help.index'))
    
    return render_template('help/contact.html', title='Contact Support')


@help_bp.route('/api/search')
@login_required
@active_account_required
def search_help():
    """Search help content"""
    query = request.args.get('q', '').lower()
    
    if not query or len(query) < 3:
        return jsonify({'results': []})
    
    # Simple search implementation
    # In production, use full-text search or Elasticsearch
    results = []
    
    # Search FAQs
    # Add matching FAQs to results
    
    # Search documentation
    # Add matching docs to results
    
    return jsonify({'results': results})


@help_bp.route('/changelog')
@login_required
@active_account_required
def changelog():
    """System changelog and updates"""
    versions = [
        {
            'version': '1.0.0',
            'date': '2024-01-15',
            'type': 'major',
            'changes': [
                'Initial release',
                'Face recognition attendance',
                'Real-time session monitoring',
                'Comprehensive reporting'
            ]
        },
        {
            'version': '1.1.0',
            'date': '2024-02-01',
            'type': 'minor',
            'changes': [
                'Added session dismissal feature',
                'Improved face recognition accuracy',
                'New dashboard widgets',
                'Performance optimizations'
            ]
        },
        {
            'version': '1.1.1',
            'date': '2024-02-15',
            'type': 'patch',
            'changes': [
                'Bug fixes for camera permissions',
                'Fixed report generation issues',
                'UI improvements'
            ]
        }
    ]
    
    return render_template('help/changelog.html', 
                         title='Changelog', 
                         versions=versions)