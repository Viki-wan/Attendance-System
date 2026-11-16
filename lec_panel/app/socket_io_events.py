"""
Socket.IO Event Handlers for Real-time Face Recognition
Handles WebSocket communication for live attendance sessions
Implements Phase 6 requirements from Flask Migration Plan
"""

from flask_socketio import emit, join_room, leave_room, disconnect
from flask import request, session
from flask_login import current_user
from app import socketio, db
from app.services.camera_service import CameraService
from app.services.face_recognition_service import FaceRecognitionService
from app.tasks.face_processing import (
    process_frame_task,
    mark_attendance_task,
    save_unknown_face_task,
    batch_process_frames_task
)
from app.models import ClassSession, Attendance, Student
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Initialize services
camera_service = CameraService()

# Active sessions tracking
active_sessions = {}  # session_id -> {user_id, room, started_at, stats}


# ==================== CONNECTION MANAGEMENT ====================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connection_response', {
        'status': 'connected',
        'session_id': request.sid,
        'timestamp': datetime.now().isoformat(),
        'server_version': '1.0.0'
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection - cleanup resources"""
    logger.info(f"Client disconnected: {request.sid}")
    
    # Clean up any active sessions for this client
    sessions_to_remove = []
    for session_id, info in active_sessions.items():
        if info.get('socket_id') == request.sid:
            sessions_to_remove.append(session_id)
    
    for session_id in sessions_to_remove:
        camera_service.unregister_session(session_id)
        del active_sessions[session_id]
        logger.info(f"Cleaned up session {session_id} on disconnect")
        
        # Notify room about disconnection
        emit('instructor_disconnected', {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        }, room=f'session_{session_id}')


@socketio.on('test_connection')
def handle_test_connection():
    """Test WebSocket connection"""
    emit('connection_test_response', {
        'status': 'success',
        'message': 'WebSocket connection is working',
        'timestamp': datetime.now().isoformat(),
        'latency': 0  # Client should calculate round-trip
    })


# ==================== SESSION MANAGEMENT ====================

@socketio.on('join_session')
def handle_join_session(data):
    """
    Join an attendance session room
    Real-Time Event: Establish WebSocket connection for session
    
    Expected data:
        session_id: Attendance session ID
        user_id: Instructor user ID
    """
    try:
        session_id = data.get('session_id')
        user_id = data.get('user_id')
        
        if not session_id:
            emit('error', {'message': 'Session ID is required'})
            return
        
        # Verify session exists and user has access
        session_obj = ClassSession.query.get(session_id)
        if not session_obj:
            emit('error', {'message': 'Session not found'})
            return
        
        # Ownership check
        if session_obj.created_by != user_id:
            emit('error', {'message': 'Unauthorized: You do not own this session'})
            return
        
        # Join Socket.IO room
        room = f'session_{session_id}'
        join_room(room)
        
        # Register camera session
        camera_service.register_session(session_id, user_id)
        
        # Get initial session statistics
        present_count = Attendance.query.filter_by(
            session_id=session_id,
            status='Present'
        ).count()
        
        # Track active session
        active_sessions[session_id] = {
            'user_id': user_id,
            'room': room,
            'socket_id': request.sid,
            'started_at': datetime.now(),
            'class_id': session_obj.class_id,
            'total_students': session_obj.total_students or 0,
            'present_count': present_count,
            'last_heartbeat': datetime.now()
        }
        
        logger.info(f"User {user_id} joined session {session_id}")
        
        emit('joined_session', {
            'session_id': session_id,
            'room': room,
            'status': session_obj.status,
            'class_id': session_obj.class_id,
            'total_students': session_obj.total_students,
            'present_count': present_count,
            'message': 'Successfully joined session'
        })
        
        # Broadcast to room that instructor joined
        emit('instructor_joined', {
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        }, room=room, skip_sid=request.sid)
        
    except Exception as e:
        logger.error(f"Error joining session: {e}")
        emit('error', {'message': f'Failed to join session: {str(e)}'})


@socketio.on('leave_session')
def handle_leave_session(data):
    """
    Leave an attendance session room
    Real-Time Event: Disconnect from session
    
    Expected data:
        session_id: Attendance session ID
    """
    try:
        session_id = data.get('session_id')
        
        if not session_id:
            emit('error', {'message': 'Session ID is required'})
            return
        
        room = f'session_{session_id}'
        leave_room(room)
        
        # Get final stats before cleanup
        stats = camera_service.get_session_stats(session_id)
        
        # Unregister camera session
        camera_service.unregister_session(session_id)
        
        # Remove from active sessions
        if session_id in active_sessions:
            del active_sessions[session_id]
        
        logger.info(f"Session {session_id} left by {request.sid}")
        
        emit('left_session', {
            'session_id': session_id,
            'final_stats': stats,
            'message': 'Successfully left session'
        })
        
        # Broadcast to room
        emit('instructor_left', {
            'timestamp': datetime.now().isoformat()
        }, room=room)
        
    except Exception as e:
        logger.error(f"Error leaving session: {e}")
        emit('error', {'message': f'Failed to leave session: {str(e)}'})


# ==================== FACE RECOGNITION PROCESSING ====================

@socketio.on('process_frame')
def handle_process_frame(data):
    """
    Process a frame for face recognition
    Real-Time Event: Frame received from browser MediaStream
    
    Expected data:
        session_id: Attendance session ID
        frame_data: Base64 encoded frame (JPEG)
        timestamp: Client timestamp
        frame_number: Sequential frame number
    """
    try:
        session_id = data.get('session_id')
        frame_data = data.get('frame_data')
        client_timestamp = data.get('timestamp')
        frame_number = data.get('frame_number', 0)
        
        if not session_id or not frame_data:
            emit('error', {'message': 'Session ID and frame data are required'})
            return
        
        # Verify session is active
        session_info = active_sessions.get(session_id)
        if not session_info:
            emit('error', {'message': 'Session not active. Please join session first.'})
            return
        
        class_id = session_info.get('class_id')
        
        # Quick frame validation (decode check)
        frame = camera_service.decode_frame(frame_data)
        if frame is None:
            emit('frame_error', {
                'error': 'decode_failed',
                'message': 'Failed to decode frame',
                'frame_number': frame_number
            })
            return
        
        # Validate frame quality
        validation = camera_service.validate_frame(frame)
        if not validation['valid']:
            emit('frame_warning', {
                'warnings': validation,
                'message': 'Frame quality issues detected',
                'frame_number': frame_number
            })
            # Continue processing but warn user
        
        # Log frame received (this will appear in Flask console)
        logger.info(f"📸 Frame #{frame_number} received for session {session_id}, class {class_id}")
        if frame_number % 10 == 0:  # Log every 10th frame
            print(f"📸 Processing frame #{frame_number} for session {session_id}, class {class_id}")
        
        # Submit to Celery for async processing
        task = process_frame_task.apply_async(
            args=[session_id, frame_data, class_id],
            countdown=0
        )
        
        logger.info(f"✅ Frame #{frame_number} queued as task {task.id}")
        
        # Acknowledge frame received
        emit('frame_processing', {
            'task_id': task.id,
            'status': 'queued',
            'frame_number': frame_number,
            'server_timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error processing frame: {e}")
        emit('frame_error', {
            'message': f'Frame processing failed: {str(e)}',
            'frame_number': data.get('frame_number', 0)
        })


@socketio.on('batch_process_frames')
def handle_batch_process(data):
    """
    Process multiple frames in batch for efficiency
    Real-Time Event: Batch frame processing
    
    Expected data:
        session_id: Attendance session ID
        frames: List of base64 encoded frames
    """
    try:
        session_id = data.get('session_id')
        frames_data = data.get('frames', [])
        
        if not session_id or not frames_data:
            emit('error', {'message': 'Session ID and frames are required'})
            return
        
        session_info = active_sessions.get(session_id)
        if not session_info:
            emit('error', {'message': 'Session not active'})
            return
        
        class_id = session_info.get('class_id')
        
        # Submit batch task
        task = batch_process_frames_task.apply_async(
            args=[session_id, frames_data, class_id],
            countdown=0
        )
        
        emit('batch_processing', {
            'task_id': task.id,
            'frame_count': len(frames_data),
            'status': 'queued'
        })
        
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        emit('error', {'message': f'Batch processing failed: {str(e)}'})


# ==================== RECOGNITION CONTROL ====================

@socketio.on('start_recognition')
def handle_start_recognition(data):
    """
    Start face recognition for a session
    Real-Time Event: Begin active recognition
    
    Expected data:
        session_id: Attendance session ID
    """
    try:
        session_id = data.get('session_id')
        
        if not session_id:
            emit('error', {'message': 'Session ID is required'})
            return
        
        session_obj = ClassSession.query.get(session_id)
        if not session_obj:
            emit('error', {'message': 'Session not found'})
            return
        
        # Update session status
        if session_obj.status != 'in_progress':
            session_obj.status = 'in_progress'
            session_obj.actual_start_time = datetime.now().time()
            db.session.commit()
        
        room = f'session_{session_id}'
        
        logger.info(f"Recognition started for session {session_id}")
        
        emit('recognition_started', {
            'session_id': session_id,
            'status': 'active',
            'timestamp': datetime.now().isoformat()
        })
        
        # Broadcast to all in room (for multiple viewers)
        emit('session_status_changed', {
            'session_id': session_id,
            'status': 'in_progress',
            'message': 'Face recognition is now active'
        }, room=room)
        
    except Exception as e:
        logger.error(f"Error starting recognition: {e}")
        emit('error', {'message': f'Failed to start recognition: {str(e)}'})


@socketio.on('stop_recognition')
def handle_stop_recognition(data):
    """
    Stop face recognition for a session
    Real-Time Event: End active recognition
    
    Expected data:
        session_id: Attendance session ID
    """
    try:
        session_id = data.get('session_id')
        
        if not session_id:
            emit('error', {'message': 'Session ID is required'})
            return
        
        session_obj = ClassSession.query.get(session_id)
        if not session_obj:
            emit('error', {'message': 'Session not found'})
            return
        
        # Update session status
        session_obj.status = 'completed'
        session_obj.actual_end_time = datetime.now().time()
        
        # Calculate final attendance rate
        present_count = Attendance.query.filter_by(
            session_id=session_id,
            status='Present'
        ).count()
        
        total_students = session_obj.total_students or 0
        attendance_rate = (present_count / total_students * 100) if total_students > 0 else 0
        
        session_obj.attendance_count = present_count
        session_obj.attendance_rate = attendance_rate
        
        db.session.commit()
        
        # Get final statistics
        camera_stats = camera_service.get_session_stats(session_id)
        
        room = f'session_{session_id}'
        
        logger.info(f"Recognition stopped for session {session_id}")
        
        final_stats = {
            'total_students': total_students,
            'present': present_count,
            'absent': total_students - present_count,
            'attendance_rate': round(attendance_rate, 1),
            'camera_stats': camera_stats
        }
        
        emit('recognition_stopped', {
            'session_id': session_id,
            'status': 'completed',
            'statistics': final_stats,
            'timestamp': datetime.now().isoformat()
        })
        
        # Broadcast to all in room
        emit('session_status_changed', {
            'session_id': session_id,
            'status': 'completed',
            'statistics': final_stats,
            'message': 'Face recognition stopped'
        }, room=room)
        
    except Exception as e:
        logger.error(f"Error stopping recognition: {e}")
        emit('error', {'message': f'Failed to stop recognition: {str(e)}'})


@socketio.on('pause_recognition')
def handle_pause_recognition(data):
    """
    Pause face recognition temporarily
    Real-Time Event: Pause recognition (e.g., for break)
    
    Expected data:
        session_id: Attendance session ID
    """
    try:
        session_id = data.get('session_id')
        
        if not session_id:
            emit('error', {'message': 'Session ID is required'})
            return
        
        session_obj = ClassSession.query.get(session_id)
        if not session_obj:
            emit('error', {'message': 'Session not found'})
            return
        
        session_obj.status = 'paused'
        db.session.commit()
        
        room = f'session_{session_id}'
        
        emit('recognition_paused', {
            'session_id': session_id,
            'status': 'paused',
            'timestamp': datetime.now().isoformat()
        })
        
        emit('session_status_changed', {
            'session_id': session_id,
            'status': 'paused',
            'message': 'Recognition paused'
        }, room=room)
        
    except Exception as e:
        logger.error(f"Error pausing recognition: {e}")
        emit('error', {'message': f'Failed to pause recognition: {str(e)}'})


# ==================== ATTENDANCE MANAGEMENT ====================

@socketio.on('mark_attendance_manual')
def handle_manual_attendance(data):
    """
    Manually mark attendance (fallback/correction)
    Real-Time Event: Manual attendance entry
    
    Expected data:
        session_id: Attendance session ID
        student_id: Student ID
        reason: Reason for manual marking
        status: 'Present', 'Late', 'Excused'
    """
    try:
        session_id = data.get('session_id')
        student_id = data.get('student_id')
        reason = data.get('reason', 'manual_entry')
        status = data.get('status', 'Present')
        
        if not session_id or not student_id:
            emit('error', {'message': 'Session ID and Student ID are required'})
            return
        
        # Check if already marked
        existing = Attendance.query.filter_by(
            session_id=session_id,
            student_id=student_id
        ).first()
        
        if existing:
            emit('attendance_error', {
                'message': 'Attendance already marked for this student',
                'student_id': student_id,
                'existing_status': existing.status
            })
            return
        
        # Submit to Celery
        task = mark_attendance_task.apply_async(
            args=[session_id, student_id, 1.0, 'manual'],
            countdown=0
        )
        
        logger.info(f"Manual attendance marked: {student_id} in session {session_id}")
        
        emit('attendance_processing', {
            'student_id': student_id,
            'method': 'manual',
            'reason': reason,
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"Error marking manual attendance: {e}")
        emit('error', {'message': f'Failed to mark attendance: {str(e)}'})


@socketio.on('correct_attendance')
def handle_correct_attendance(data):
    """
    Correct an existing attendance record
    Real-Time Event: Attendance correction
    
    Expected data:
        attendance_id: Attendance record ID
        new_status: New status value
        reason: Reason for correction
    """
    try:
        attendance_id = data.get('attendance_id')
        new_status = data.get('new_status')
        reason = data.get('reason', 'correction')
        
        if not attendance_id or not new_status:
            emit('error', {'message': 'Attendance ID and new status are required'})
            return
        
        attendance = Attendance.query.get(attendance_id)
        if not attendance:
            emit('error', {'message': 'Attendance record not found'})
            return
        
        old_status = attendance.status
        attendance.status = new_status
        attendance.correction_reason = reason
        attendance.corrected_at = datetime.now()
        
        db.session.commit()
        
        logger.info(f"Attendance corrected: ID {attendance_id} from {old_status} to {new_status}")
        
        emit('attendance_corrected', {
            'attendance_id': attendance_id,
            'student_id': attendance.student_id,
            'old_status': old_status,
            'new_status': new_status,
            'reason': reason
        })
        
        # Broadcast to session room
        room = f'session_{attendance.session_id}'
        emit('attendance_updated', {
            'attendance_id': attendance_id,
            'student_id': attendance.student_id,
            'status': new_status
        }, room=room)
        
    except Exception as e:
        logger.error(f"Error correcting attendance: {e}")
        emit('error', {'message': f'Failed to correct attendance: {str(e)}'})


# ==================== SESSION STATISTICS ====================

@socketio.on('request_session_stats')
def handle_stats_request(data):
    """
    Request current session statistics
    Real-Time Event: Stats update request
    
    Expected data:
        session_id: Attendance session ID
    """
    try:
        session_id = data.get('session_id')
        
        if not session_id:
            emit('error', {'message': 'Session ID is required'})
            return
        
        # Get camera stats
        camera_stats = camera_service.get_session_stats(session_id)
        
        # Get attendance stats
        session_obj = ClassSession.query.get(session_id)
        if session_obj:
            total_students = session_obj.total_students or 0
            present_count = Attendance.query.filter_by(
                session_id=session_id,
                status='Present'
            ).count()
            
            late_count = Attendance.query.filter_by(
                session_id=session_id,
                status='Late'
            ).count()
            
            attendance_rate = (present_count / total_students * 100) if total_students > 0 else 0
            
            stats = {
                'session_id': session_id,
                'status': session_obj.status,
                'total_students': total_students,
                'present': present_count,
                'late': late_count,
                'absent': total_students - present_count - late_count,
                'attendance_rate': round(attendance_rate, 1),
                'camera_stats': camera_stats,
                'timestamp': datetime.now().isoformat()
            }
        else:
            stats = {
                'error': 'Session not found',
                'camera_stats': camera_stats
            }
        
        emit('session_stats', stats)
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        emit('error', {'message': f'Failed to get statistics: {str(e)}'})


@socketio.on('subscribe_progress')
def handle_subscribe_progress(data):
    """
    Subscribe to session progress updates
    Real-Time Event: Progress tracking subscription
    
    Expected data:
        session_id: Attendance session ID
    """
    try:
        session_id = data.get('session_id')
        
        if not session_id:
            emit('error', {'message': 'Session ID is required'})
            return
        
        # Join progress room
        room = f'progress_{session_id}'
        join_room(room)
        
        emit('progress_subscribed', {
            'session_id': session_id,
            'message': 'Subscribed to progress updates'
        })
        
    except Exception as e:
        logger.error(f"Error subscribing to progress: {e}")
        emit('error', {'message': f'Failed to subscribe: {str(e)}'})


# ==================== CAMERA CONTROL ====================

@socketio.on('camera_status')
def handle_camera_status(data):
    """
    Report camera status from client
    Real-Time Event: Camera health monitoring
    
    Expected data:
        session_id: Attendance session ID
        status: 'active', 'inactive', 'error'
        fps: Current FPS
        resolution: Current resolution
    """
    try:
        session_id = data.get('session_id')
        status = data.get('status')
        fps = data.get('fps', 0)
        resolution = data.get('resolution', {})
        
        if not session_id:
            return
        
        # Update session info
        if session_id in active_sessions:
            active_sessions[session_id].update({
                'camera_status': status,
                'camera_fps': fps,
                'camera_resolution': resolution,
                'last_camera_update': datetime.now()
            })
        
        # Broadcast camera status
        room = f'session_{session_id}'
        emit('camera_status_update', {
            'session_id': session_id,
            'status': status,
            'fps': fps,
            'resolution': resolution
        }, room=room, include_self=False)
        
    except Exception as e:
        logger.error(f"Error handling camera status: {e}")


@socketio.on('unknown_face_detected')
def handle_unknown_face(data):
    """
    Handle detection of unknown face
    Real-Time Event: Unknown person alert
    
    Expected data:
        session_id: Attendance session ID
        frame_data: Base64 frame with unknown face
        face_location: Bounding box coordinates
        confidence: Recognition confidence (low)
    """
    try:
        session_id = data.get('session_id')
        frame_data = data.get('frame_data')
        face_location = data.get('face_location')
        
        if not all([session_id, frame_data, face_location]):
            emit('error', {'message': 'Missing required data'})
            return
        
        # Save unknown face asynchronously
        task = save_unknown_face_task.apply_async(
            args=[session_id, frame_data, face_location],
            countdown=0
        )
        
        # Alert instructor
        room = f'session_{session_id}'
        emit('unknown_face_alert', {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'message': 'Unknown person detected in frame'
        }, room=room)
        
    except Exception as e:
        logger.error(f"Error handling unknown face: {e}")


# ==================== UTILITY HANDLERS ====================

@socketio.on('session_heartbeat')
def handle_heartbeat(data):
    """
    Keep-alive heartbeat from client
    Real-Time Event: Connection health check
    
    Expected data:
        session_id: Attendance session ID
    """
    try:
        session_id = data.get('session_id')
        
        if session_id and session_id in active_sessions:
            active_sessions[session_id]['last_heartbeat'] = datetime.now()
            emit('heartbeat_ack', {
                'timestamp': datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"Error handling heartbeat: {e}")


@socketio.on('get_student_list')
def handle_get_students(data):
    """
    Get list of students for a class
    Real-Time Event: Student roster request
    
    Expected data:
        class_id: Class ID
    """
    try:
        class_id = data.get('class_id')
        
        if not class_id:
            emit('error', {'message': 'Class ID is required'})
            return
        
        # Get students enrolled in class
        from app.models.class_model import Class
        class_obj = Class.query.get(class_id)
        
        if not class_obj:
            emit('error', {'message': 'Class not found'})
            return
        
        # Get course code
        course_code = class_obj.course_code
        
        # Get enrolled students (using StudentCourse junction table)
        from app.models.course import StudentCourse
        students = Student.query.join(StudentCourse).filter(
            StudentCourse.course_code == course_code,
            Student.is_active == True,
            StudentCourse.status == 'Active'
        ).all()
        
        student_list = [{
            'student_id': s.student_id,
            'name': f"{s.fname} {s.lname}",
            'has_face_encoding': s.face_encoding is not None,
            'photo_url': s.face_only_path if s.face_only_path else None
        } for s in students]
        
        emit('student_list', {
            'class_id': class_id,
            'students': student_list,
            'total': len(student_list)
        })
        
    except Exception as e:
        logger.error(f"Error getting student list: {e}")
        emit('error', {'message': f'Failed to get students: {str(e)}'})


@socketio.on('get_active_sessions')
def handle_get_active_sessions():
    """
    Get list of all active sessions
    Real-Time Event: Active session monitoring
    """
    try:
        sessions_info = []
        for session_id, info in active_sessions.items():
            session_obj = ClassSession.query.get(session_id)
            if session_obj:
                sessions_info.append({
                    'session_id': session_id,
                    'class_id': info['class_id'],
                    'user_id': info['user_id'],
                    'status': session_obj.status,
                    'duration': (datetime.now() - info['started_at']).total_seconds(),
                    'present_count': info.get('present_count', 0),
                    'total_students': info.get('total_students', 0)
                })
        
        emit('active_sessions_list', {
            'sessions': sessions_info,
            'total': len(sessions_info)
        })
        
    except Exception as e:
        logger.error(f"Error getting active sessions: {e}")
        emit('error', {'message': f'Failed to get active sessions: {str(e)}'})


# ==================== ERROR HANDLING ====================

@socketio.on_error_default
def default_error_handler(e):
    """Handle Socket.IO errors"""
    logger.error(f"Socket.IO error: {e}")
    emit('error', {
        'message': 'An error occurred',
        'details': str(e),
        'timestamp': datetime.now().isoformat()
    })


# ==================== BROADCAST HELPERS ====================
# These are called from Celery tasks, not directly from clients

def broadcast_student_recognized(session_id, student_data):
    """Broadcast when a student is recognized (called from Celery)"""
    socketio.emit('student_recognized', student_data, room=f'session_{session_id}')


def broadcast_attendance_marked(session_id, attendance_data):
    """Broadcast when attendance is marked (called from Celery)"""
    socketio.emit('attendance_marked', attendance_data, room=f'session_{session_id}')


def broadcast_session_progress(session_id, progress_data):
    """Broadcast session progress updates (called from Celery)"""
    socketio.emit('session_progress', progress_data, room=f'session_{session_id}')
    socketio.emit('session_progress', progress_data, room=f'progress_{session_id}')