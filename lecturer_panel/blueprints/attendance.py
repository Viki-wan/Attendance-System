from flask import Blueprint, render_template, session, redirect, url_for, Response
from lecturer_panel.services.database_service import DatabaseService
from lecturer_panel.services.face_recognition_service import FaceRecognitionService
from lecturer_panel.services.session_service import SessionService
from datetime import datetime
import cv2
import face_recognition

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')
db_service = DatabaseService()
face_service = FaceRecognitionService(db_service.load_settings(), db_service)
session_service = SessionService(db_service)
ACTIVE_SESSIONS = {}

def generate_frames(session_id):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return
    session_data = ACTIVE_SESSIONS.get(session_id)
    if not session_data:
        print(f"Error: Session {session_id} not active.")
        return
    required_matches = 3
    while cap.isOpened() and session_data.get('running', False):
        ret, frame = cap.read()
        if not ret:
            break
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        for face_encoding, face_location in zip(face_encodings, face_locations):
            student_id, name, is_known = face_service.recognize_face(
                face_encoding,
                session_data['known_faces'],
                session_data['student_ids'],
                tolerance=0.5
            )
            if is_known:
                match_counter = session_data['match_counter']
                match_counter[student_id] = match_counter.get(student_id, 0) + 1
                if match_counter[student_id] == required_matches:
                    if db_service.mark_attendance(student_id, session_id):
                        print(f"Marked {name} ({student_id}) present for session {session_id}")
            top, right, bottom, left = face_location
            color = (0, 255, 0) if is_known else (0, 0, 255)
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            label = name if is_known else "Unknown"
            cv2.putText(frame, label, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    cap.release()
    print(f"Video feed for session {session_id} stopped.")

@attendance_bp.route('/session/start/<int:session_id>')
def start_session(session_id):
    if 'instructor_id' not in session:
        return redirect(url_for('auth.login'))
    instructor_id = session['instructor_id']
    # Use the new session_service/db_service logic for validation
    sessions_today = db_service.get_todays_sessions_for_instructor(instructor_id)
    session_details = next((s for s in sessions_today if s['session_id'] == session_id), None)
    if not session_details:
        return "Session not found or not assigned to you.", 404
    # Backend validation: not in the future, not completed, not missed
    now = datetime.now().strftime('%H:%M:%S')
    if session_details['start_time'] > now:
        return "Session has not started yet.", 400
    if session_details['status'] not in ['scheduled', 'ongoing']:
        return f"Session cannot be started (status: {session_details['status']}).", 400
    students = db_service.get_session_students(session_id)
    class_student_ids = [s['student_id'] for s in students]
    all_known_faces, all_student_ids = face_service.load_known_faces()
    class_known_faces = []
    class_student_ids_for_rec = []
    for face, student_id in zip(all_known_faces, all_student_ids):
        if student_id in class_student_ids:
            class_known_faces.append(face)
            class_student_ids_for_rec.append(student_id)
    ACTIVE_SESSIONS[session_id] = {
        'running': True,
        'known_faces': class_known_faces,
        'student_ids': class_student_ids_for_rec,
        'match_counter': {}
    }
    return render_template('attendance/session.html', session_details=session_details, students=students)

@attendance_bp.route('/video_feed/<int:session_id>')
def video_feed(session_id):
    if 'instructor_id' not in session:
        return "Unauthorized", 401
    return Response(generate_frames(session_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@attendance_bp.route('/session/stop/<int:session_id>')
def stop_session(session_id):
    if 'instructor_id' not in session:
        return redirect(url_for('auth.login'))
    if session_id in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS[session_id]['running'] = False
        import time
        time.sleep(1)
        if session_id in ACTIVE_SESSIONS:
            del ACTIVE_SESSIONS[session_id]
    db_service.update_session_end_time(session_id)
    return redirect(url_for('reports.session_report', session_id=session_id))

@attendance_bp.route('/sessions')
def sessions_list():
    if 'instructor_id' not in session:
        return redirect(url_for('auth.login'))
    instructor_id = session['instructor_id']
    sessions = session_service.get_today_sessions(instructor_id)
    now = datetime.now().strftime('%H:%M:%S')
    return render_template('attendance_session.html', sessions=sessions, now=now) 