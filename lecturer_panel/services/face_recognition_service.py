import os
import cv2
import numpy as np
import face_recognition
import pickle
import uuid
import time
from PIL import Image
import imagehash
from datetime import datetime

class FaceRecognitionService:
    def __init__(self, settings, db_service):
        self.settings = settings
        self.db_service = db_service
        self.known_faces = []
        self.student_ids = []
        self.last_unknown_save_time = 0
        # Constants
        self.UNKNOWN_DIR = "unknown_faces"
        self.MIN_FACE_SIZE = 50
        self.HASH_SIMILARITY_THRESHOLD = 10
        self.FACE_SIMILARITY_THRESHOLD = 0.6
        self.BRIGHTNESS_MIN = 40
        self.BRIGHTNESS_MAX = 215
        self.CONTRAST_THRESHOLD = 20
        if not os.path.exists(self.UNKNOWN_DIR):
            os.makedirs(self.UNKNOWN_DIR)
        self.load_known_faces()
    def load_known_faces(self):
        self.known_faces = []
        self.student_ids = []
        self.original_ids = []
        encoding_dir = "student_encodings"
        if not os.path.exists(encoding_dir):
            print("❌ Student encodings directory not found.")
            return [], []
        try:
            encoding_files = [f for f in os.listdir(encoding_dir) if f.endswith('_encodings.pkl')]
            for encoding_file in encoding_files:
                try:
                    file_path = os.path.join(encoding_dir, encoding_file)
                    student_id = encoding_file.replace('student_', '').replace('_encodings.pkl', '')
                    original_id = student_id
                    slash_id = student_id.replace('_', '/')
                    with open(file_path, 'rb') as f:
                        encodings = pickle.load(f)
                    for encoding in encodings:
                        self.known_faces.append(encoding)
                        self.student_ids.append(slash_id)
                        self.original_ids.append(original_id)
                    print(f"✅ Loaded {len(encodings)} encodings for student {slash_id} (file: {original_id})")
                except Exception as e:
                    print(f"❌ Error loading encoding file {encoding_file}: {e}")
            print(f"✅ Total loaded faces: {len(self.known_faces)}")
            return self.known_faces, self.student_ids
        except Exception as e:
            print(f"❌ Error in loading known faces: {e}")
            return [], []
    def refresh_known_faces(self):
        return self.load_known_faces()
    def process_frame(self, frame):
        result = {
            'processed_frame': frame.copy(),
            'faces_detected': [],
            'recognized_students': [],
            'unknown_faces': []
        }
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        avg_brightness = gray.mean()
        if avg_brightness < 20:
            cv2.putText(result['processed_frame'], "Low light detected", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            return result
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        if not face_locations:
            cv2.putText(result['processed_frame'], "No face detected", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            return result
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        for face_encoding, face_location in zip(face_encodings, face_locations):
            tolerance = float(self.settings.get("face_recognition_sensitivity", "50")) / 100
            if len(self.known_faces) > 0:
                matches = face_recognition.compare_faces(self.known_faces, face_encoding, tolerance=tolerance)
                face_distances = face_recognition.face_distance(self.known_faces, face_encoding)
                student_info = {
                    'student_id': "Unknown",
                    'name': "Unknown",
                    'confidence': 0.0,
                    'face_location': face_location
                }
                if np.any(matches):
                    best_match_index = int(np.argmin(face_distances))
                    if best_match_index < len(matches) and best_match_index < len(self.student_ids):
                        if matches[best_match_index]:
                            student_id = self.student_ids[best_match_index]
                            student_info['student_id'] = student_id
                            student_info['name'] = self.db_service.get_student_name(student_id)
                            confidence = 1.0 - face_distances[best_match_index]
                            student_info['confidence'] = confidence
                            result['recognized_students'].append(student_info)
                else:
                    unknown_info = {
                        'face_location': face_location,
                        'encoding': face_encoding
                    }
                    result['unknown_faces'].append(unknown_info)
            top, right, bottom, left = face_location
            color = (0, 255, 0) if student_info['student_id'] != "Unknown" else (0, 0, 255)
            cv2.rectangle(result['processed_frame'], (left, top), (right, bottom), color, 2)
            label = f"{student_info['name']} ({student_info['student_id']})" if student_info['student_id'] != "Unknown" else "⚠️ Unknown"
            cv2.putText(result['processed_frame'], label, (left, top - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            if student_info['student_id'] != "Unknown":
                confidence_text = f"Confidence: {student_info['confidence']:.2f}"
                cv2.putText(result['processed_frame'], confidence_text, (left, bottom + 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        return result
    def recognize_face(self, face_encoding, known_faces, student_ids, tolerance=0.6):
        student_id = "Unknown"
        name = "Unknown"
        is_known = False
        if len(known_faces) > 0:
            matches = face_recognition.compare_faces(known_faces, face_encoding, tolerance=tolerance)
            face_distances = face_recognition.face_distance(known_faces, face_encoding)
            if np.any(matches):
                best_match_index = int(np.argmin(face_distances))
                if best_match_index < len(matches) and best_match_index < len(student_ids):
                    if matches[best_match_index]:
                        student_id = student_ids[best_match_index]
                        name = self.db_service.get_student_name(student_id)
                        is_known = True
        return student_id, name, is_known 