"""
API Routes for Face Recognition Operations
RESTful endpoints for camera control and face processing
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import ClassSession, Attendance, Student
from app.services.face_recognition_service import FaceRecognitionService
from app.services.camera_service import CameraService
from app.tasks.face_processing import (
    process_frame_task,
    mark_attendance_task,
    save_unknown_face_task,
    preload_class_faces_task
)
from app.decorators import owns_session
from datetime import datetime

bp = Blueprint('face_recognition', __name__, url_prefix='/api/face-recognition')

# Initialize services
camera_service = CameraService()


@bp.route('/session/<int:session_id>/start', methods=['POST'])
@login_required
@owns_session
def start_face_recognition(session_id):
    """
    Start face recognition for a session
    
    Request Body:
        {
            "preload_faces": true  // Optional: preload faces before starting
        }
    """
    session = ClassSession.query.get_or_404(session_id)
    
    # Check if session is eligible
    if not session.is_eligible_for_attendance():
        return jsonify({
            'error': 'Session is not eligible for attendance tracking'
        }), 400
    
    # Register camera session
    camera_service.register_session(session_id, current_user.id)
    
    # Preload faces if requested
    data = request.get_json() or {}
    if data.get('preload_faces', True):
        preload_class_faces_task.delay(session.class_id)
    
    # Update session status
    session.status = 'ongoing'
    db.session.commit()
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'class_id': session.class_id,
        'message': 'Face recognition started'
    })


@bp.route('/session/<int:session_id>/stop', methods=['POST'])
@login_required
@owns_session
def stop_face_recognition(session_id):
    """Stop face recognition for a session"""
    session = ClassSession.query.get_or_404(session_id)
    
    # Get camera stats before unregistering
    stats = camera_service.get_session_stats(session_id)
    
    # Unregister camera session
    camera_service.unregister_session(session_id)
    
    # Update session status
    session.status = 'completed'
    session.end_time = datetime.now().strftime('%H:%M:%S')
    db.session.commit()
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'statistics': stats,
        'message': 'Face recognition stopped'
    })


@bp.route('/session/<int:session_id>/process-frame', methods=['POST'])
@login_required
@owns_session
def process_frame(session_id):
    """
    Process a single frame for face recognition
    
    Request Body:
        {
            "frame": "base64_encoded_image",
            "timestamp": "2025-10-31T10:30:00"
        }
    """
    session = ClassSession.query.get_or_404(session_id)
    
    data = request.get_json()
    if not data or 'frame' not in data:
        return jsonify({'error': 'No frame data provided'}), 400
    
    # Queue frame processing task
    task = process_frame_task.delay(
        session_id,
        data['frame'],
        session.class_id
    )
    
    return jsonify({
        'success': True,
        'task_id': task.id,
        'message': 'Frame queued for processing'
    })


@bp.route('/session/<int:session_id>/mark-attendance', methods=['POST'])
@login_required
@owns_session
def mark_attendance_manual(session_id):
    """
    Manually mark attendance (from recognition result)
    
    Request Body:
        {
            "student_id": "BIT/123/456",
            "confidence": 0.95,
            "method": "face_recognition"
        }
    """
    session = ClassSession.query.get_or_404(session_id)
    
    data = request.get_json()
    if not data or 'student_id' not in data:
        return jsonify({'error': 'Missing student_id'}), 400
    
    # Validate student is in this class
    student = Student.query.get(data['student_id'])
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    
    # Check if already marked
    existing = Attendance.query.filter_by(
        session_id=session_id,
        student_id=data['student_id']
    ).first()
    
    if existing:
        return jsonify({
            'error': 'Attendance already marked',
            'attendance_id': existing.id
        }), 409
    
    # Queue attendance marking
    task = mark_attendance_task.delay(
        session_id,
        data['student_id'],
        data.get('confidence', 0.0),
        data.get('method', 'face_recognition')
    )
    
    return jsonify({
        'success': True,
        'task_id': task.id,
        'message': 'Attendance queued for marking'
    })


@bp.route('/session/<int:session_id>/save-unknown', methods=['POST'])
@login_required
@owns_session
def save_unknown_face(session_id):
    """
    Save unknown face for review
    
    Request Body:
        {
            "frame": "base64_encoded_image",
            "face_location": [top, right, bottom, left]
        }
    """
    data = request.get_json()
    if not data or 'frame' not in data or 'face_location' not in data:
        return jsonify({'error': 'Missing required data'}), 400
    
    # Queue unknown face saving
    task = save_unknown_face_task.delay(
        session_id,
        data['frame'],
        data['face_location']
    )
    
    return jsonify({
        'success': True,
        'task_id': task.id,
        'message': 'Unknown face queued for saving'
    })


@bp.route('/session/<int:session_id>/expected-students', methods=['GET'])
@login_required
@owns_session
def get_expected_students(session_id):
    """Get list of students expected in this session"""
    session = ClassSession.query.get_or_404(session_id)
    
    # Get students for this class
    from app.models import Class
    class_obj = Class.query.get(session.class_id)
    
    if not class_obj:
        return jsonify({'error': 'Class not found'}), 404
    
    # Get enrolled students
    students = Student.query.join(Student.courses).filter(
        Student.courses.any(course_code=class_obj.course_code),
        Student.is_active == True
    ).all()
    
    # Get attendance status
    attendance_records = Attendance.query.filter_by(
        session_id=session_id
    ).all()
    
    present_ids = {a.student_id for a in attendance_records if a.status == 'Present'}
    
    # Format response
    students_data = [{
        'student_id': s.student_id,
        'name': f"{s.fname} {s.lname}",
        'email': s.email,
        'has_face_encoding': s.face_encoding is not None,
        'status': 'Present' if s.student_id in present_ids else 'Absent'
    } for s in students]
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'total_students': len(students_data),
        'present_count': len(present_ids),
        'students': students_data
    })


@bp.route('/session/<int:session_id>/attendance-status', methods=['GET'])
@login_required
@owns_session
def get_attendance_status(session_id):
    """Get real-time attendance status for session"""
    session = ClassSession.query.get_or_404(session_id)
    
    # Get statistics
    stats = session.get_statistics()
    
    # Get camera stats
    camera_stats = camera_service.get_session_stats(session_id)
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'session_status': session.status,
        'attendance_stats': stats,
        'camera_stats': camera_stats
    })


@bp.route('/session/<int:session_id>/recognition-settings', methods=['GET', 'POST'])
@login_required
@owns_session
def recognition_settings(session_id):
    """Get or update recognition settings for session"""
    
    if request.method == 'GET':
        # Get current settings
        from app.models import Setting
        settings = Setting.get_all_settings()
        
        return jsonify({
            'success': True,
            'settings': {
                'sensitivity': settings.get('face_recognition_sensitivity', '50'),
                'required_matches': settings.get('required_matches', '3'),
                'save_unknown_faces': settings.get('save_unknown_faces', '1'),
                'min_confidence': settings.get('min_confidence_threshold', '0.6')
            }
        })
    
    else:  # POST
        data = request.get_json()
        
        # Update settings
        from app.models import Setting
        
        if 'sensitivity' in data:
            Setting.set('face_recognition_sensitivity', str(data['sensitivity']))
        
        if 'required_matches' in data:
            Setting.set('required_matches', str(data['required_matches']))
        
        if 'save_unknown_faces' in data:
            Setting.set('save_unknown_faces', '1' if data['save_unknown_faces'] else '0')
        
        return jsonify({
            'success': True,
            'message': 'Settings updated'
        })


@bp.route('/validate-camera', methods=['POST'])
@login_required
def validate_camera():
    """
    Validate camera frame quality
    
    Request Body:
        {
            "frame": "base64_encoded_image"
        }
    """
    data = request.get_json()
    if not data or 'frame' not in data:
        return jsonify({'error': 'No frame data provided'}), 400
    
    # Decode frame
    frame = camera_service.decode_frame(data['frame'])
    if frame is None:
        return jsonify({
            'valid': False,
            'error': 'failed_to_decode'
        }), 400
    
    # Validate quality
    validation = camera_service.validate_frame(frame)
    
    return jsonify({
        'success': True,
        'validation': validation
    })


@bp.route('/cache-stats', methods=['GET'])
@login_required
def get_cache_stats():
    """Get face recognition cache statistics"""
    face_service = FaceRecognitionService()
    stats = face_service.get_cache_stats()
    
    return jsonify({
        'success': True,
        'cache_stats': stats
    })


@bp.route('/clear-cache', methods=['POST'])
@login_required
def clear_cache():
    """Clear face recognition cache"""
    face_service = FaceRecognitionService()
    face_service.clear_cache()
    
    return jsonify({
        'success': True,
        'message': 'Cache cleared'
    })


@bp.route('/student/<student_id>/register-face', methods=['POST'])
@login_required
def register_student_face(student_id):
    """
    Register or update student face encoding
    
    Request Body:
        {
            "image": "base64_encoded_image"
        }
    """
    student = Student.query.get_or_404(student_id)
    
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'error': 'No image data provided'}), 400
    
    # Decode image
    frame = camera_service.decode_frame(data['image'])
    if frame is None:
        return jsonify({'error': 'Failed to decode image'}), 400
    
    # Extract face encoding
    face_service = FaceRecognitionService()
    encoding = face_service.extract_face_encoding_from_array(frame)
    
    if encoding is None:
        return jsonify({'error': 'No face detected in image'}), 400
    
    # Save encoding
    student.face_encoding = encoding.tobytes()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'student_id': student_id,
        'message': 'Face encoding registered successfully'
    })


@bp.route('/unknown-faces', methods=['GET'])
@login_required
def list_unknown_faces():
    """List all saved unknown faces"""
    from pathlib import Path
    from config.config import Config
    
    unknown_faces_dir = Path(Config.UPLOAD_FOLDER) / 'unknown_faces'
    
    if not unknown_faces_dir.exists():
        return jsonify({
            'success': True,
            'unknown_faces': []
        })
    
    files = []
    for filepath in sorted(unknown_faces_dir.glob('*.jpg'), key=lambda x: x.stat().st_mtime, reverse=True):
        files.append({
            'filename': filepath.name,
            'timestamp': datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
            'size': filepath.stat().st_size,
            'path': str(filepath.relative_to(Config.UPLOAD_FOLDER))
        })
    
    return jsonify({
        'success': True,
        'total': len(files),
        'unknown_faces': files
    })