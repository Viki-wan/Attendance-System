"""
Celery Background Tasks for Face Recognition Processing
Handles async face detection, recognition, and attendance marking
"""

from celery import shared_task
from app import db, socketio
from app.models import Student, Attendance, ClassSession
from app.services.face_recognition_service import FaceRecognitionService
from app.services.camera_service import CameraService
from datetime import datetime
import numpy as np
from typing import Dict, List


camera_service = CameraService()


@shared_task(bind=True, max_retries=3)
def process_frame_task(self, session_id: int, frame_data: str, class_id: str):
    """
    Process a single frame for face recognition
    
    Args:
        session_id: Attendance session ID
        frame_data: Base64 encoded frame
        class_id: Class ID for filtering students
        
    Returns:
        Dictionary with recognition results
    """
    try:
        # Load settings
        from app.models import Setting
        settings = Setting.get_all_settings()
        
        # Initialize services
        face_service = FaceRecognitionService(settings)
        
        # Decode frame
        frame = camera_service.decode_frame(frame_data)
        if frame is None:
            return {'error': 'failed_to_decode_frame'}
        
        # Validate frame quality
        quality = camera_service.validate_frame(frame)
        if not quality['valid']:
            return {
                'error': 'poor_quality',
                'details': quality
            }
        
        # Load known faces for this class
        known_faces, student_ids = face_service.load_known_faces(class_id)
        
        if not known_faces:
            return {'error': 'no_registered_faces'}
        
        # Process frame
        results = face_service.process_frame(
            frame,
            known_faces,
            student_ids,
            float(settings.get('face_recognition_sensitivity', 50)) / 100
        )
        
        # Update camera stats
        faces_detected = len(results)
        faces_recognized = sum(1 for r in results if r.get('recognized'))
        
        camera_service.update_session_stats(
            session_id,
            faces_detected=faces_detected,
            faces_recognized=faces_recognized
        )
        
        # Process recognition results
        for result in results:
            if result.get('recognized'):
                # Emit real-time update
                socketio.emit('student_recognized', {
                    'session_id': session_id,
                    'student_id': result['student_id'],
                    'name': result['name'],
                    'confidence': result['confidence'],
                    'timestamp': result['timestamp']
                }, room=f'session_{session_id}')
        
        return {
            'success': True,
            'faces_detected': faces_detected,
            'faces_recognized': faces_recognized,
            'results': results
        }
        
    except Exception as e:
        print(f"❌ Error processing frame: {e}")
        self.retry(exc=e, countdown=2)


@shared_task
def mark_attendance_task(
    session_id: int,
    student_id: str,
    confidence: float,
    method: str = 'face_recognition'
):
    """
    Mark student attendance (async to avoid blocking)
    
    Args:
        session_id: Attendance session ID
        student_id: Student ID
        confidence: Recognition confidence score
        method: Attendance marking method
        
    Returns:
        Dictionary with marking result
    """
    try:
        # Check if already marked
        existing = Attendance.query.filter_by(
            session_id=session_id,
            student_id=student_id
        ).first()
        
        if existing:
            return {
                'success': False,
                'reason': 'already_marked',
                'student_id': student_id
            }
        
        # Get session
        session = ClassSession.query.get(session_id)
        if not session:
            return {
                'success': False,
                'reason': 'session_not_found'
            }
        
        # Create attendance record
        attendance = Attendance(
            student_id=student_id,
            session_id=session_id,
            status='Present',
            method=method,
            confidence_score=confidence,
            timestamp=datetime.now()
        )
        
        db.session.add(attendance)
        
        # Update session stats
        session.attendance_count = session.attendance_count + 1
        
        db.session.commit()
        
        # Get student info
        student = Student.query.get(student_id)
        
        # Emit real-time update
        socketio.emit('attendance_marked', {
            'session_id': session_id,
            'student_id': student_id,
            'student_name': f"{student.fname} {student.lname}" if student else "Unknown",
            'status': 'Present',
            'confidence': confidence,
            'timestamp': attendance.timestamp.isoformat()
        }, room=f'session_{session_id}')
        
        # Update progress
        progress = (session.attendance_count / session.total_students * 100) if session.total_students > 0 else 0
        
        socketio.emit('session_progress', {
            'session_id': session_id,
            'present': session.attendance_count,
            'total': session.total_students,
            'percentage': round(progress, 1)
        }, room=f'session_{session_id}')
        
        return {
            'success': True,
            'student_id': student_id,
            'attendance_id': attendance.id
        }
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error marking attendance: {e}")
        return {
            'success': False,
            'reason': 'database_error',
            'error': str(e)
        }


@shared_task
def save_unknown_face_task(
    session_id: int,
    frame_data: str,
    face_location: List[int]
):
    """
    Save unknown face for review (async)
    
    Args:
        session_id: Attendance session ID
        frame_data: Base64 encoded frame
        face_location: Face bounding box coordinates
        
    Returns:
        Path to saved image
    """
    try:
        # Decode frame
        frame = camera_service.decode_frame(frame_data)
        if frame is None:
            return None
        
        # Initialize face service
        face_service = FaceRecognitionService()
        
        # Save unknown face
        filepath = face_service.save_unknown_face(
            frame,
            tuple(face_location),
            session_id
        )
        
        if filepath:
            # Emit notification
            socketio.emit('unknown_face_detected', {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'image_path': filepath
            }, room=f'session_{session_id}')
        
        return filepath
        
    except Exception as e:
        print(f"❌ Error saving unknown face: {e}")
        return None


@shared_task
def batch_process_frames_task(
    session_id: int,
    frames_data: List[str],
    class_id: str
):
    """
    Process multiple frames in batch for efficiency
    
    Args:
        session_id: Attendance session ID
        frames_data: List of base64 encoded frames
        class_id: Class ID
        
    Returns:
        List of processing results
    """
    try:
        # Load settings
        from app.models import Setting
        settings = Setting.get_all_settings()
        
        # Initialize services
        face_service = FaceRecognitionService(settings)
        
        # Decode frames
        frames = []
        for frame_data in frames_data:
            frame = camera_service.decode_frame(frame_data)
            if frame is not None:
                frames.append(frame)
        
        if not frames:
            return {'error': 'no_valid_frames'}
        
        # Load known faces
        known_faces, student_ids = face_service.load_known_faces(class_id)
        
        # Batch process
        results = face_service.batch_process_faces(
            frames,
            known_faces,
            student_ids
        )
        
        return {
            'success': True,
            'frames_processed': len(frames),
            'results': results
        }
        
    except Exception as e:
        print(f"❌ Error batch processing frames: {e}")
        return {'error': str(e)}


@shared_task
def preload_class_faces_task(class_id: str):
    """
    Preload and cache face encodings for a class
    
    Args:
        class_id: Class ID
        
    Returns:
        Number of faces loaded
    """
    try:
        face_service = FaceRecognitionService()
        known_faces, student_ids = face_service.load_known_faces(class_id)
        
        return {
            'success': True,
            'faces_loaded': len(known_faces),
            'class_id': class_id
        }
        
    except Exception as e:
        print(f"❌ Error preloading faces: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def cleanup_old_unknown_faces_task(days: int = 30):
    """
    Clean up old unknown face images
    
    Args:
        days: Delete files older than this many days
        
    Returns:
        Number of files deleted
    """
    try:
        from pathlib import Path
        from config.config import Config
        import time
        
        unknown_faces_dir = Path(Config.UPLOAD_FOLDER) / 'unknown_faces'
        
        if not unknown_faces_dir.exists():
            return 0
        
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        deleted = 0
        
        for filepath in unknown_faces_dir.glob('*.jpg'):
            if filepath.stat().st_mtime < cutoff_time:
                filepath.unlink()
                deleted += 1
        
        print(f"🗑️ Deleted {deleted} old unknown face images")
        return deleted
        
    except Exception as e:
        print(f"❌ Error cleaning up unknown faces: {e}")
        return 0


@shared_task
def generate_face_encoding_task(student_id: str, image_path: str):
    """
    Generate and save face encoding for a student
    
    Args:
        student_id: Student ID
        image_path: Path to student's image
        
    Returns:
        Success status
    """
    try:
        face_service = FaceRecognitionService()
        
        # Extract encoding
        encoding = face_service.extract_face_encoding(image_path)
        
        if encoding is None:
            return {
                'success': False,
                'reason': 'no_face_detected'
            }
        
        # Save to database
        student = Student.query.get(student_id)
        if student:
            student.face_encoding = encoding.tobytes()
            db.session.commit()
            
            return {
                'success': True,
                'student_id': student_id
            }
        else:
            return {
                'success': False,
                'reason': 'student_not_found'
            }
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error generating face encoding: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def update_session_statistics_task(session_id: int):
    """
    Update session statistics after attendance session
    
    Args:
        session_id: Session ID
        
    Returns:
        Updated statistics
    """
    try:
        session = ClassSession.query.get(session_id)
        if not session:
            return None
        
        # Calculate statistics
        stats = session.get_statistics()
        
        # Update session
        session.attendance_count = stats['present_count']
        db.session.commit()
        
        # Emit update
        socketio.emit('session_statistics_updated', {
            'session_id': session_id,
            'statistics': stats
        }, room=f'session_{session_id}')
        
        return stats
        
    except Exception as e:
        print(f"❌ Error updating session statistics: {e}")
        return None