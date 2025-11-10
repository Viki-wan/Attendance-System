"""
Face Recognition Service for Flask Attendance System
Migrated from PyQt with web-optimized processing
"""

import os
import cv2
import numpy as np
import face_recognition
from datetime import datetime
from typing import List, Tuple, Optional, Dict
import pickle
from pathlib import Path

from app import db
from app.models import Student, Attendance, ClassSession
from config.config import Config


class FaceRecognitionService:
    """
    Handles all face recognition operations including:
    - Loading and caching face encodings
    - Face detection and recognition
    - Unknown face handling
    - Multi-face processing
    """
    
    def __init__(self, settings: Dict = None):
        """
        Initialize face recognition service
        
        Args:
            settings: Dictionary of system settings (from database)
        """
        self.settings = settings or {}
        self.known_faces = []
        self.student_ids = []
        self.encoding_cache = {}
        self.last_cache_update = None
        
        # Face recognition settings
        self.threshold = float(self.settings.get('face_recognition_sensitivity', 50)) / 100
        self.model = "hog"  # Use 'cnn' for better accuracy but slower processing
        self.min_face_size = 100  # Minimum face size in pixels
        self.max_faces_per_frame = 5
        
        # Paths
        self.faces_dir = Path(Config.UPLOAD_FOLDER) / 'faces'
        self.unknown_faces_dir = Path(Config.UPLOAD_FOLDER) / 'unknown_faces'
        self.encodings_dir = Path(Config.UPLOAD_FOLDER) / 'encodings'
        
        # Create directories
        self.faces_dir.mkdir(parents=True, exist_ok=True)
        self.unknown_faces_dir.mkdir(parents=True, exist_ok=True)
        self.encodings_dir.mkdir(parents=True, exist_ok=True)
    
    def load_known_faces(self, class_id: str = None) -> Tuple[List, List]:
        """
        Load face encodings for all students or specific class
        
        Args:
            class_id: Optional class ID to filter students
            
        Returns:
            Tuple of (face_encodings, student_ids)
        """
        print(f"🔄 Loading face encodings for class: {class_id or 'ALL'}")
        
        known_faces = []
        student_ids = []
        
        # Query students based on class_id
        if class_id:
            # Get students enrolled in courses for this class
            from app.models.class_model import Class
            class_ = Class.query.get(class_id)
            if not class_:
                print(f"⚠️ Class {class_id} not found")
                return [], []
            
            # Get course code for this class
            course_code = class_.course_code
            
            # Get students enrolled in this course
            students = Student.query.join(Student.courses).filter(
                Student.courses.any(course_code=course_code),
                Student.is_active == True
            ).all()
        else:
            students = Student.query.filter_by(is_active=True).all()
        
        # Load face encodings
        for student in students:
            # Try to load from pickle file first (faster)
            encoding_path = self.encodings_dir / f"{student.student_id.replace('/', '_')}.pkl"
            
            if encoding_path.exists():
                try:
                    with open(encoding_path, 'rb') as f:
                        encoding = pickle.load(f)
                    known_faces.append(encoding)
                    student_ids.append(student.student_id)
                    continue
                except Exception as e:
                    print(f"⚠️ Error loading encoding for {student.student_id}: {e}")
            
            # If no pickle file, try to load from database BLOB
            if student.face_encoding:
                try:
                    encoding = np.frombuffer(student.face_encoding, dtype=np.float64)
                    known_faces.append(encoding)
                    student_ids.append(student.student_id)
                    
                    # Save to pickle for faster loading next time
                    with open(encoding_path, 'wb') as f:
                        pickle.dump(encoding, f)
                except Exception as e:
                    print(f"⚠️ Error decoding face for {student.student_id}: {e}")
            
            # If no encoding, try to extract from image
            elif student.face_only_path and os.path.exists(student.face_only_path):
                try:
                    encoding = self.extract_face_encoding(student.face_only_path)
                    if encoding is not None:
                        known_faces.append(encoding)
                        student_ids.append(student.student_id)
                        
                        # Save to database and pickle
                        student.face_encoding = encoding.tobytes()
                        db.session.commit()
                        
                        with open(encoding_path, 'wb') as f:
                            pickle.dump(encoding, f)
                except Exception as e:
                    print(f"⚠️ Error extracting face for {student.student_id}: {e}")
        
        print(f"✅ Loaded {len(known_faces)} face encodings")
        
        self.known_faces = known_faces
        self.student_ids = student_ids
        self.last_cache_update = datetime.now()
        
        return known_faces, student_ids
    
    def extract_face_encoding(self, image_path: str) -> Optional[np.ndarray]:
        """
        Extract face encoding from image file
        
        Args:
            image_path: Path to image file
            
        Returns:
            Face encoding array or None if no face found
        """
        try:
            image = face_recognition.load_image_file(image_path)
            encodings = face_recognition.face_encodings(image, model="large")
            
            if len(encodings) > 0:
                return encodings[0]
            else:
                print(f"⚠️ No face found in {image_path}")
                return None
        except Exception as e:
            print(f"❌ Error extracting encoding from {image_path}: {e}")
            return None
    
    def process_frame(
        self, 
        frame: np.ndarray, 
        known_faces: List, 
        student_ids: List,
        sensitivity: float = None
    ) -> List[Dict]:
        """
        Process a single frame for face recognition
        
        Args:
            frame: BGR image from camera
            known_faces: List of known face encodings
            student_ids: List of corresponding student IDs
            sensitivity: Recognition threshold (0-1), higher = stricter
            
        Returns:
            List of detected faces with recognition results
        """
        if sensitivity is None:
            sensitivity = self.threshold
        
        results = []
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Check lighting conditions
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        avg_brightness = gray.mean()
        
        if avg_brightness < 20:
            return [{
                'error': 'low_light',
                'message': 'Insufficient lighting detected'
            }]
        
        # Detect faces
        face_locations = face_recognition.face_locations(
            rgb_frame, 
            model=self.model,
            number_of_times_to_upsample=1
        )
        
        if not face_locations:
            return []
        
        # Limit number of faces processed
        if len(face_locations) > self.max_faces_per_frame:
            face_locations = face_locations[:self.max_faces_per_frame]
        
        # Get face encodings
        face_encodings = face_recognition.face_encodings(
            rgb_frame, 
            face_locations,
            model="large"
        )
        
        # Process each detected face
        for face_encoding, face_location in zip(face_encodings, face_locations):
            # Check face size
            top, right, bottom, left = face_location
            face_width = right - left
            face_height = bottom - top
            
            if face_width < self.min_face_size or face_height < self.min_face_size:
                results.append({
                    'recognized': False,
                    'reason': 'face_too_small',
                    'location': face_location,
                    'size': (face_width, face_height)
                })
                continue
            
            # Recognize face
            student_id, name, is_known, confidence = self._recognize_face(
                face_encoding,
                known_faces,
                student_ids,
                sensitivity
            )
            
            results.append({
                'recognized': is_known,
                'student_id': student_id,
                'name': name,
                'confidence': confidence,
                'location': face_location,
                'brightness': avg_brightness,
                'timestamp': datetime.now().isoformat()
            })
        
        return results
    
    def _recognize_face(
        self,
        face_encoding: np.ndarray,
        known_faces: List,
        student_ids: List,
        sensitivity: float
    ) -> Tuple[Optional[str], Optional[str], bool, float]:
        """
        Compare face encoding against known faces
        
        Args:
            face_encoding: Face encoding to recognize
            known_faces: List of known face encodings
            student_ids: List of corresponding student IDs
            sensitivity: Recognition threshold
            
        Returns:
            Tuple of (student_id, name, is_known, confidence)
        """
        if not known_faces:
            return None, None, False, 0.0
        
        # Calculate face distances
        face_distances = face_recognition.face_distance(known_faces, face_encoding)
        
        # Find best match
        best_match_index = np.argmin(face_distances)
        min_distance = face_distances[best_match_index]
        
        # Convert distance to confidence (inverse relationship)
        confidence = 1.0 - min_distance
        
        # Check if match is good enough
        if min_distance <= sensitivity:
            student_id = student_ids[best_match_index]
            
            # Get student name
            student = Student.query.get(student_id)
            if student:
                name = f"{student.fname} {student.lname}"
                return student_id, name, True, confidence
        
        return None, "Unknown", False, confidence
    
    def recognize_face(
        self,
        face_encoding: np.ndarray,
        known_faces: List,
        student_ids: List,
        sensitivity: float = None
    ) -> Tuple[Optional[str], str, bool]:
        """
        Legacy method for backward compatibility
        """
        student_id, name, is_known, _ = self._recognize_face(
            face_encoding,
            known_faces,
            student_ids,
            sensitivity or self.threshold
        )
        return student_id, name, is_known
    
    def save_unknown_face(
        self,
        frame: np.ndarray,
        face_location: Tuple[int, int, int, int],
        session_id: int = None
    ) -> Optional[str]:
        """
        Save unknown face for review
        
        Args:
            frame: Full frame containing face
            face_location: (top, right, bottom, left) coordinates
            session_id: Optional session ID for tracking
            
        Returns:
            Path to saved image or None if save failed
        """
        try:
            top, right, bottom, left = face_location
            
            # Add padding
            padding = 20
            top = max(0, top - padding)
            left = max(0, left - padding)
            bottom = min(frame.shape[0], bottom + padding)
            right = min(frame.shape[1], right + padding)
            
            # Extract face
            face_image = frame[top:bottom, left:right]
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            session_prefix = f"session_{session_id}_" if session_id else ""
            filename = f"unknown_{session_prefix}{timestamp}.jpg"
            filepath = self.unknown_faces_dir / filename
            
            # Save image
            cv2.imwrite(str(filepath), face_image)
            
            print(f"💾 Saved unknown face: {filename}")
            return str(filepath)
            
        except Exception as e:
            print(f"❌ Error saving unknown face: {e}")
            return None
    
    def validate_face_quality(self, frame: np.ndarray, face_location: Tuple) -> Dict:
        """
        Validate if face is suitable for recognition
        
        Args:
            frame: Image frame
            face_location: Face bounding box
            
        Returns:
            Dictionary with quality metrics
        """
        top, right, bottom, left = face_location
        face_image = frame[top:bottom, left:right]
        
        # Check size
        width = right - left
        height = bottom - top
        size_ok = width >= self.min_face_size and height >= self.min_face_size
        
        # Check blur (Laplacian variance)
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_ok = blur_score > 100  # Threshold for blur detection
        
        # Check brightness
        brightness = gray.mean()
        brightness_ok = 40 < brightness < 220
        
        return {
            'valid': size_ok and blur_ok and brightness_ok,
            'size': (width, height),
            'size_ok': size_ok,
            'blur_score': blur_score,
            'blur_ok': blur_ok,
            'brightness': brightness,
            'brightness_ok': brightness_ok
        }
    
    def batch_process_faces(
        self,
        frames: List[np.ndarray],
        known_faces: List,
        student_ids: List
    ) -> List[List[Dict]]:
        """
        Process multiple frames in batch (for optimization)
        
        Args:
            frames: List of image frames
            known_faces: Known face encodings
            student_ids: Corresponding student IDs
            
        Returns:
            List of results for each frame
        """
        results = []
        for frame in frames:
            frame_results = self.process_frame(frame, known_faces, student_ids)
            results.append(frame_results)
        return results
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'total_faces': len(self.known_faces),
            'last_update': self.last_cache_update.isoformat() if self.last_cache_update else None,
            'cache_size_mb': sum(
                os.path.getsize(f) for f in self.encodings_dir.glob('*.pkl')
            ) / (1024 * 1024)
        }
    
    def clear_cache(self):
        """Clear in-memory cache"""
        self.known_faces = []
        self.student_ids = []
        self.encoding_cache = {}
        self.last_cache_update = None
        print("🗑️ Face recognition cache cleared")