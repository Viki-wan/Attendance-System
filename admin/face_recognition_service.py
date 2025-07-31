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
        
        # Create directory for unknown faces if it doesn't exist
        if not os.path.exists(self.UNKNOWN_DIR):
            os.makedirs(self.UNKNOWN_DIR)
        
        # Load face encodings on initialization
        self.load_known_faces()
    
    def load_known_faces(self):
        """Load all known face encodings from storage"""
        self.known_faces = []
        self.student_ids = []
        self.original_ids = []  # For keeping track of the original ID format

        # Ensure encoding directory exists
        encoding_dir = "student_encodings"
        if not os.path.exists(encoding_dir):
            print("❌ Student encodings directory not found.")
            return [], []

        try:
            # Find all encoding files
            encoding_files = [f for f in os.listdir(encoding_dir) if f.endswith('_encodings.pkl')]
            
            for encoding_file in encoding_files:
                try:
                    file_path = os.path.join(encoding_dir, encoding_file)
                    
                    # Extract student ID from filename - with more flexible handling
                    student_id = encoding_file.replace('student_', '').replace('_encodings.pkl', '')
                    
                    # Store both formats of the ID for more flexible matching
                    # Original format with underscores
                    original_id = student_id
                    # Format with slashes
                    slash_id = student_id.replace('_', '/')
                    
                    # Load encodings from pickle file
                    with open(file_path, 'rb') as f:
                        encodings = pickle.load(f)
                    
                    # Add each encoding with the database format ID (with slashes)
                    for encoding in encodings:
                        self.known_faces.append(encoding)
                        self.student_ids.append(slash_id)  # Use database format
                        self.original_ids.append(original_id)  # Keep original for file operations
                    
                    print(f"✅ Loaded {len(encodings)} encodings for student {slash_id} (file: {original_id})")
                
                except Exception as e:
                    print(f"❌ Error loading encoding file {encoding_file}: {e}")

            print(f"✅ Total loaded faces: {len(self.known_faces)}")
            return self.known_faces, self.student_ids

        except Exception as e:
            print(f"❌ Error in loading known faces: {e}")
            return [], []        
    def refresh_known_faces(self):
        """Reload all face encodings"""
        return self.load_known_faces()
    
    def process_frame(self, frame):
        """Process a video frame to detect and recognize faces"""
        result = {
            'processed_frame': frame.copy(),
            'faces_detected': [],
            'recognized_students': [],
            'unknown_faces': []
        }
        
        # Check if frame brightness is too low
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        avg_brightness = gray.mean()
        
        if avg_brightness < 20:
            cv2.putText(result['processed_frame'], "Low light detected", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            return result
        
        # Convert to RGB for face_recognition library
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        
        if not face_locations:
            cv2.putText(result['processed_frame'], "No face detected", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            return result
        
        # Get face encodings for all detected faces
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        
        # Process each detected face
        for face_encoding, face_location in zip(face_encodings, face_locations):
            # Get recognition sensitivity from settings
            tolerance = float(self.settings.get("face_recognition_sensitivity", "50")) / 100
            
            # Compare with known faces
            if len(self.known_faces) > 0:
                matches = face_recognition.compare_faces(self.known_faces, face_encoding, tolerance=tolerance)
                face_distances = face_recognition.face_distance(self.known_faces, face_encoding)
                
                student_info = {
                    'student_id': "Unknown",
                    'name': "Unknown",
                    'confidence': 0.0,
                    'face_location': face_location
                }
                
                # Check if any matches found
                if np.any(matches):
                    best_match_index = int(np.argmin(face_distances))
                    
                    # Verify the index is valid
                    if best_match_index < len(matches) and best_match_index < len(self.student_ids):
                        if matches[best_match_index]:
                            student_id = self.student_ids[best_match_index]
                            student_info['student_id'] = student_id
                            student_info['name'] = self.db_service.get_student_name(student_id)
                            
                            # Calculate confidence
                            confidence = 1.0 - face_distances[best_match_index]
                            student_info['confidence'] = confidence
                            
                            # Add to recognized students
                            result['recognized_students'].append(student_info)
                else:
                    # Unknown face
                    unknown_info = {
                        'face_location': face_location,
                        'encoding': face_encoding
                    }
                    result['unknown_faces'].append(unknown_info)
            
            # Draw rectangle and label on frame
            top, right, bottom, left = face_location
            color = (0, 255, 0) if student_info['student_id'] != "Unknown" else (0, 0, 255)
            cv2.rectangle(result['processed_frame'], (left, top), (right, bottom), color, 2)
            
            # Display student name or unknown
            label = f"{student_info['name']} ({student_info['student_id']})" if student_info['student_id'] != "Unknown" else "⚠️ Unknown"
            cv2.putText(result['processed_frame'], label, (left, top - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            # Add confidence if known face
            if student_info['student_id'] != "Unknown":
                confidence_text = f"Confidence: {student_info['confidence']:.2f}"
                cv2.putText(result['processed_frame'], confidence_text, (left, bottom + 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return result
    
    def recognize_face(self, face_encoding, known_faces, student_ids, tolerance=0.6):
        """
        Recognize a face by comparing it to known faces
        
        Args:
            face_encoding: The encoding of the face to recognize
            known_faces: List of known face encodings
            student_ids: List of corresponding student IDs
            tolerance: Recognition sensitivity (lower is stricter)
            
        Returns:
            tuple: (student_id, name, is_known)
        """
        # Default values for unknown face
        student_id = "Unknown"
        name = "Unknown"
        is_known = False
        
        # Check if we have any known faces to compare against
        if len(known_faces) > 0:
            # Compare face with known faces
            matches = face_recognition.compare_faces(known_faces, face_encoding, tolerance=tolerance)
            face_distances = face_recognition.face_distance(known_faces, face_encoding)
            
            # Check if any matches found
            if np.any(matches):
                best_match_index = int(np.argmin(face_distances))
                
                # Verify the index is valid
                if best_match_index < len(matches) and best_match_index < len(student_ids):
                    if matches[best_match_index]:
                        student_id = student_ids[best_match_index]
                        name = self.db_service.get_student_name(student_id)
                        is_known = True
        
        return student_id, name, is_known
    
    def save_unknown_face(self, frame, face_location):
        """Save detected unknown faces with robust duplicate detection"""
        try:
            # Extract and pad face region
            top, right, bottom, left = face_location
            padding = 20
            top, bottom = max(0, top - padding), min(frame.shape[0], bottom + padding)
            left, right = max(0, left - padding), min(frame.shape[1], right + padding)
            face_img = frame[top:bottom, left:right]

            # Ensure face is large enough for recognition
            if face_img.shape[0] < self.MIN_FACE_SIZE or face_img.shape[1] < self.MIN_FACE_SIZE:
                print("⚠️ Face too small, skipping save.")
                return None

            # Convert image and generate hash values
            pil_image = Image.fromarray(cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB))
            standardized_image = pil_image.convert("L").resize((128, 128))
            
            # Generate multiple hash types for robust comparison
            phash_value = imagehash.phash(standardized_image)
            dhash_value = imagehash.dhash(standardized_image)
            avg_hash_value = imagehash.average_hash(standardized_image)
            
            # Get face encoding
            rgb_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
            face_encodings = face_recognition.face_encodings(rgb_face)
            if not face_encodings:
                print("⚠️ Could not generate face encoding, skipping save.")
                return None
            face_encoding = face_encodings[0]

            # Store current timestamp for cooldown check
            current_time = time.time()
            
            # Check for duplicates
            is_duplicate = False
            closest_match = float('inf')
            closest_file = None
            
            for file in os.listdir(self.UNKNOWN_DIR):
                file_path = os.path.join(self.UNKNOWN_DIR, file)
                
                # Skip non-image files
                if not file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue
                    
                try:
                    # Multi-hash comparison
                    existing_img = Image.open(file_path).convert("L").resize((128, 128))
                    existing_phash = imagehash.phash(existing_img)
                    existing_dhash = imagehash.dhash(existing_img)
                    existing_avg_hash = imagehash.average_hash(existing_img)
                    
                    # Calculate combined hash difference
                    phash_diff = abs(phash_value - existing_phash)
                    dhash_diff = abs(dhash_value - existing_dhash)
                    avg_hash_diff = abs(avg_hash_value - existing_avg_hash)
                    
                    combined_diff = (phash_diff * 0.5) + (dhash_diff * 0.3) + (avg_hash_diff * 0.2)
                    
                    if combined_diff < closest_match:
                        closest_match = combined_diff
                        closest_file = file
                    
                    if combined_diff < self.HASH_SIMILARITY_THRESHOLD:
                        print(f"⚠️ Duplicate detected via hash (similarity: {combined_diff})")
                        is_duplicate = True
                        break
                    
                    # For borderline cases, verify with face recognition
                    if self.HASH_SIMILARITY_THRESHOLD <= combined_diff <= self.HASH_SIMILARITY_THRESHOLD * 2:
                        try:
                            existing_face_img = cv2.imread(file_path)
                            existing_rgb = cv2.cvtColor(existing_face_img, cv2.COLOR_BGR2RGB)
                            existing_encodings = face_recognition.face_encodings(existing_rgb)
                            
                            if existing_encodings:
                                # Compare face encodings
                                face_distance = face_recognition.face_distance([existing_encodings[0]], face_encoding)[0]
                                
                                if face_distance < self.FACE_SIMILARITY_THRESHOLD:
                                    print(f"⚠️ Duplicate detected via face recognition (distance: {face_distance})")
                                    is_duplicate = True
                                    break
                        except Exception as e:
                            print(f"Error comparing face encodings: {e}")
                    
                except Exception as e:
                    print(f"Error processing existing image {file}: {e}")
                    continue

            # Check cooldown period for saving unknown faces
            cooldown_period = float(self.settings.get("unknown_face_cooldown", "5"))  # 5 seconds default
            
            if current_time - self.last_unknown_save_time < cooldown_period:
                print(f"⚠️ Cooldown period active, skipping save. ({current_time - self.last_unknown_save_time:.1f}s < {cooldown_period}s)")
                return None

            # Save file if no duplicates found
            if not is_duplicate:
                file_path = os.path.join(self.UNKNOWN_DIR, f"unknown_{uuid.uuid4().hex[:8]}.jpg")
                pil_image.save(file_path)
                self.last_unknown_save_time = current_time
                
                print(f"✅ New unknown face saved: {file_path}")
                return file_path
            else:
                print("⚠️ Duplicate face not saved.")
                return None

        except Exception as e:
            print(f"❌ Error saving unknown face: {e}")
            return None

    def enhance_image(self, image_path):
        """Enhance image quality for better recognition"""
        try:
            # Load the image
            img = cv2.imread(image_path)
            if img is None:
                print(f"❌ Could not read image: {image_path}")
                return None
                
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Measure initial brightness and contrast
            initial_brightness = np.mean(gray)
            initial_contrast = np.std(gray)
            
            print(f"📊 Initial image stats: Brightness={initial_brightness:.1f}, Contrast={initial_contrast:.1f}")
            
            # Apply auto white balance if color image
            if len(img.shape) > 2:
                # Simple white balance using percentile
                for i in range(3):
                    p5 = np.percentile(img[:,:,i], 5)
                    p95 = np.percentile(img[:,:,i], 95)
                    if p95 > p5:
                        img[:,:,i] = np.clip((img[:,:,i] - p5) * 255.0 / (p95 - p5), 0, 255).astype(np.uint8)
            
            # Apply CLAHE for contrast enhancement on the luminance channel
            if len(img.shape) > 2:
                # Convert to LAB color space
                lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                
                # Apply CLAHE to L channel
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                cl = clahe.apply(l)
                
                # Merge back and convert to BGR
                limg = cv2.merge((cl, a, b))
                enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            else:
                # Apply CLAHE directly to grayscale
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
            
            # Apply slight sharpening
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            enhanced = cv2.filter2D(enhanced, -1, kernel)
            
            # Check enhanced stats
            if len(enhanced.shape) > 2:
                enhanced_gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
            else:
                enhanced_gray = enhanced
                
            enhanced_brightness = np.mean(enhanced_gray)
            enhanced_contrast = np.std(enhanced_gray)
            
            print(f"📊 Enhanced image stats: Brightness={enhanced_brightness:.1f}, Contrast={enhanced_contrast:.1f}")
            
            # Save enhanced image with _enhanced suffix
            base_name, ext = os.path.splitext(image_path)
            enhanced_path = f"{base_name}_enhanced{ext}"
            cv2.imwrite(enhanced_path, enhanced)
            
            print(f"✅ Enhanced image saved to: {enhanced_path}")
            return enhanced_path
            
        except Exception as e:
            print(f"❌ Error enhancing image: {e}")
            return None