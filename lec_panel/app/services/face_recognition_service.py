"""
Face Recognition Service for Flask Attendance System
Migrated from PyQt with web-optimized processing
"""
import base64
import imagehash
from PIL import Image, ImageOps, ImageEnhance
import os
import sys
import io
import cv2
import numpy as np
from datetime import datetime
from typing import List, Tuple, Optional, Dict
import pickle
from pathlib import Path
import logging
from contextlib import redirect_stdout, redirect_stderr

# Import face_recognition - suppress the harmless models warning that prints on import
# (models are installed; the library still prints a warning to stdout/stderr)
try:
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        import face_recognition
except ImportError as e:
    raise ImportError(f"face_recognition library not installed: {e}. Install with: pip install face_recognition")
except Exception as e:
    # If anything unexpected happens, re-raise so we can see the real error
    raise

from app import db
from app.models import Student, Attendance, ClassSession
from config.config import Config

logger = logging.getLogger(__name__)


class FaceRecognitionService:
    """
    Handles all face recognition operations including:
    - Loading and caching face encodings
    - Face detection and recognition
    - Unknown face handling
    - Multi-face processing
    """

    # Laplacian-variance blur thresholds used during student registration
    BLUR_SEVERE = 50
    BLUR_MODERATE = 100
    BLUR_ACCEPTABLE = 150
    BLUR_VERY_BLURRY_DECONV = 80

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
        
        # Also check old encoding locations for backward compatibility
        self.old_encodings_dir = Path(Config.BASE_DIR) / 'face_encodings'
        self.alt_encodings_dir = Config.FACE_ENCODINGS_FOLDER if hasattr(Config, 'FACE_ENCODINGS_FOLDER') else Path(Config.UPLOAD_FOLDER) / 'face_encodings'
        
        # Create directories
        self.faces_dir.mkdir(parents=True, exist_ok=True)
        self.unknown_faces_dir.mkdir(parents=True, exist_ok=True)
        self.encodings_dir.mkdir(parents=True, exist_ok=True)

        # Full student photos + cropped faces saved at registration.
        # Same folder the PyQt app used (its IMAGE_DIR = "student_images"), so
        # both apps share one dataset. Override with Config.STUDENT_IMAGES_FOLDER.
        self.student_photos_dir = Path(
            getattr(Config, 'STUDENT_IMAGES_FOLDER', Path(Config.BASE_DIR) / 'student_images')
        )
        self.student_photos_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Registration photos -> {self.student_photos_dir.resolve()}")
        print(f"📁 Registration encodings -> {self.old_encodings_dir.resolve()}")
    
    def load_known_faces(self, class_id: str = None) -> Tuple[List, List]:
        """
        Load face encodings for all students or specific class
        
        Args:
            class_id: Optional class ID to filter students
            
        Returns:
            Tuple of (face_encodings, student_ids)
        """
        print(f"🔄 Loading face encodings for class: {class_id or 'ALL'}")
        print(f"📁 Checking encoding directories:")
        print(f"   - Old format: {self.old_encodings_dir}")
        print(f"   - Alternative: {self.alt_encodings_dir}")
        print(f"   - New format: {self.encodings_dir}")
        
        known_faces = []
        student_ids = []
        
        # Query students based on class_id
        if class_id:
            # Get students enrolled in courses for this class
            from app.models.class_model import Class
            from app.models.course import StudentCourse
            class_ = Class.query.get(class_id)
            if not class_:
                print(f"⚠️ Class {class_id} not found")
                return [], []
            
            # Get course code for this class
            course_code = class_.course_code
            
            # Get students enrolled in this course (using StudentCourse junction table)
            students = Student.query.join(StudentCourse).filter(
                StudentCourse.course_code == course_code,
                Student.is_active == True,
                StudentCourse.status == 'Active'
            ).all()
            print(f"📊 Found {len(students)} students in class {class_id}")
        else:
            students = Student.query.filter_by(is_active=True).all()
            print(f"📊 Found {len(students)} active students")
        
        # Load face encodings
        loaded_count = 0
        students_without_encodings = []  # Track students without encodings
        for student in students:
            encoding_loaded = False
            sanitized_id = student.student_id.replace('/', '_')
            
            # Try multiple encoding file locations and formats
            encoding_paths = [
                # Old format locations (student_S11_10067_25_encodings.pkl) - CHECK THIS FIRST
                self.old_encodings_dir / f"student_{sanitized_id}_encodings.pkl",
                self.alt_encodings_dir / f"student_{sanitized_id}_encodings.pkl",
                # New format locations
                self.encodings_dir / f"{sanitized_id}.pkl",
                self.alt_encodings_dir / f"{sanitized_id}.pkl",
            ]
            
            # Try to load from pickle files
            for encoding_path in encoding_paths:
                if encoding_path.exists():
                    try:
                        with open(encoding_path, 'rb') as f:
                            encoding_data = pickle.load(f)
                        
                        # Handle both single encoding and list of encodings (old format)
                        if isinstance(encoding_data, list) and len(encoding_data) > 0:
                            # Old format: list of encodings - use the first one
                            encoding = encoding_data[0]
                            print(f"✅ Loaded encoding for {student.student_id} from {encoding_path.name} (list format, using first)")
                        elif isinstance(encoding_data, np.ndarray):
                            # New format: single encoding array
                            encoding = encoding_data
                            print(f"✅ Loaded encoding for {student.student_id} from {encoding_path.name}")
                        else:
                            print(f"⚠️ Unknown encoding format for {student.student_id} in {encoding_path.name}")
                            continue
                        
                        known_faces.append(encoding)
                        student_ids.append(student.student_id)
                        encoding_loaded = True
                        loaded_count += 1
                        break
                    except Exception as e:
                        print(f"⚠️ Error loading encoding from {encoding_path} for {student.student_id}: {e}")
                        continue
            
            if encoding_loaded:
                continue
            
            # If no pickle file, try to load from database BLOB
            if student.face_encoding:
                try:
                    encoding = np.frombuffer(student.face_encoding, dtype=np.float64)
                    if encoding.shape[0] == 128:  # Valid face encoding size
                        known_faces.append(encoding)
                        student_ids.append(student.student_id)
                        loaded_count += 1
                        print(f"✅ Loaded encoding for {student.student_id} from database")
                        encoding_loaded = True
                        
                        # Save to pickle for faster loading next time
                        encoding_path = self.encodings_dir / f"{sanitized_id}.pkl"
                        try:
                            with open(encoding_path, 'wb') as f:
                                pickle.dump(encoding, f)
                        except:
                            pass  # Ignore save errors
                    else:
                        print(f"⚠️ Invalid encoding size for {student.student_id}: {encoding.shape}")
                except Exception as e:
                    print(f"⚠️ Error decoding face from database for {student.student_id}: {e}")
            
            if encoding_loaded:
                continue
            
            # If no encoding, try to extract from image
            if student.face_only_path and os.path.exists(student.face_only_path):
                try:
                    encoding = self.extract_face_encoding(student.face_only_path)
                    if encoding is not None:
                        known_faces.append(encoding)
                        student_ids.append(student.student_id)
                        loaded_count += 1
                        print(f"✅ Extracted encoding for {student.student_id} from image")
                        encoding_loaded = True
                        
                        # Save to database and pickle
                        student.face_encoding = encoding.tobytes()
                        db.session.commit()
                        
                        encoding_path = self.encodings_dir / f"{sanitized_id}.pkl"
                        with open(encoding_path, 'wb') as f:
                            pickle.dump(encoding, f)
                except Exception as e:
                    print(f"⚠️ Error extracting face for {student.student_id}: {e}")
            
            # Track students without encodings for reporting (only if all methods failed)
            if not encoding_loaded:
                students_without_encodings.append({
                    'student_id': student.student_id,
                    'sanitized_id': sanitized_id,
                    'expected_filename': f"student_{sanitized_id}_encodings.pkl"
                })
        
        print(f"✅ Loaded {len(known_faces)} face encodings for class: {class_id or 'ALL'}")
        
        if len(known_faces) == 0:
            print(f"❌ ERROR: No face encodings found for class {class_id or 'ALL'}!")
            print(f"   Checked directories:")
            print(f"   - {self.old_encodings_dir} (exists: {self.old_encodings_dir.exists()})")
            print(f"   - {self.alt_encodings_dir} (exists: {self.alt_encodings_dir.exists()})")
            print(f"   - {self.encodings_dir} (exists: {self.encodings_dir.exists()})")
            print(f"   - Database (face_encoding column)")
        
        if students_without_encodings:
            print(f"⚠️ {len(students_without_encodings)} students without encodings found")
            if len(students_without_encodings) <= 5:
                for s in students_without_encodings[:5]:
                    print(f"   - {s['student_id']} (expected file: {s['expected_filename']})")
            else:
                print(f"   Showing first 5 of {len(students_without_encodings)} students:")
                for s in students_without_encodings[:5]:
                    print(f"   - {s['student_id']} (expected file: {s['expected_filename']})")
                print(f"   ... and {len(students_without_encodings) - 5} more")
        
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

    def register_student_face(self, image_data: str, student_id: str,
                              exclude_student_id: str = None, force: bool = False) -> dict:
        """
        Process a captured photo for student registration (or re-registration).
    
        Validates exactly one face is present, checks the photo against every
        existing student for duplicates (perceptual hash + face-distance),
        generates augmented encodings for more robust recognition, and writes
        the image files + encodings pickle to disk.
    
        Does NOT touch the database or create/update any Student row — the
        caller (StudentAdminService) takes the returned data and persists it.
        This keeps face_recognition logic in one place and DB writes in the
        service layer, same separation as the rest of this file.
    
        Args:
            image_data: base64 data URL from the webcam capture, e.g.
                "data:image/jpeg;base64,/9j/4AAQ..." (camera_handler.js's
                captureFrame() produces exactly this format).
            student_id: student ID used to build sanitized filenames/paths.
            exclude_student_id: when re-registering an existing student's own
                photo, pass their student_id here so the duplicate check
                doesn't flag their new photo against their own previous one.
            force: set True to accept a photo the blur check flagged as blurry
                (the operator confirmed "continue anyway").
    
        Returns:
            dict. On failure:
                {'success': False, 'error': str, 'error_code': str,
                'duplicate_student_id': str or None}
            On success:
                {
                    'success': True,
                    'image_path': str,        # full original photo, on disk
                    'face_only_path': str,    # cropped, 20%-padded face image
                    'image_hash': str,        # perceptual hash (image_hash column)
                    'face_encoding': bytes,   # original encoding .tobytes() (face_encoding column)
                    'encoding_path': str,     # pickle file path (face_encoding_path column)
                    'num_encodings': int,     # how many augmented encodings were generated
                }
        """
        from app.models import Student  # local import, matches this file's existing style
    
        sanitized_id = student_id.replace('/', '_')

        def fail(error, code, **extra):
            result = {
                'success': False,
                'error': error,
                'error_code': code,
                'requires_confirmation': False,
            }
            result.update(extra)
            return result
    
        # ---- Decode the captured frame ----
        try:
            raw_data = image_data.split(',', 1)[1] if ',' in image_data else image_data
            image_bytes = base64.b64decode(raw_data)
            np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
            raw_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"❌ Error decoding captured image for {student_id}: {e}")
            raw_bgr = None
    
        if raw_bgr is None:
            return fail('Could not decode the captured photo. Please try again.', 'DECODE_FAILED')
                
        # ---- Blur score on the RAW capture, then deblur/sharpen ----
        blur_value, is_blurry, blur_message = self._check_image_quality(raw_bgr)
        bgr_image = self._enhance_image(raw_bgr, blur_value)
        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
    
        # ---- Face count validation (reject 0 or >1, same as legacy) ----
        face_locations = face_recognition.face_locations(rgb_image, model=self.model)
    
        if len(face_locations) == 0:
            return fail('No face was detected. Please retake the photo.', 'NO_FACE_DETECTED')

    
        if len(face_locations) > 1:
            return fail('Multiple faces detected. Please retake the photo.', 'MULTIPLE_FACES')
    
        face_location = face_locations[0]
    
        # ---- 20%-padded face crop ----
        top, right, bottom, left = face_location
        pad_x = int(0.2 * (right - left))
        pad_y = int(0.2 * (bottom - top))
    
        crop_top = max(0, top - pad_y)
        crop_left = max(0, left - pad_x)
        crop_bottom = min(bgr_image.shape[0], bottom + pad_y)
        crop_right = min(bgr_image.shape[1], right + pad_x)
    
        face_crop_raw = bgr_image[crop_top:crop_bottom, crop_left:crop_right]
        face_crop_bgr = self._enhance_face(face_crop_raw)
        if face_crop_bgr is None:
            face_crop_bgr = face_crop_raw  # same fallback as legacy (keep the plain crop)
        
        # ---- Perceptual hash, prioritizing the face crop (falls back to full
        #      image only if the crop is somehow empty) ----
        try:
            hash_source = face_crop_bgr if face_crop_bgr.size > 0 else bgr_image
            hash_pil = Image.fromarray(cv2.cvtColor(hash_source, cv2.COLOR_BGR2RGB)).convert('L')
            hash_pil = hash_pil.resize((128, 128))
            hash_pil = ImageOps.autocontrast(hash_pil)
            image_hash = str(imagehash.phash(hash_pil))
        except Exception as e:
            print(f"⚠️ Perceptual hash computation failed for {student_id}: {e}")
            return {
                'success': False,
                'error': 'Failed to process the captured photo.',
                'error_code': 'HASH_FAILED'
            }
    
        # ---- Face encoding (used for both duplicate check and storage) ----
        encodings_at_location = face_recognition.face_encodings(rgb_image, [face_location], model="large")
        if not encodings_at_location:
            return fail('A face was located but could not be encoded. Please retake the photo with better lighting.', 'ENCODING_FAILED')
        original_encoding = encodings_at_location[0]
    
        # ---- Duplicate detection: face-distance (threshold 0.55) + dynamic
        #      perceptual hash, checked against every existing student ----
        face_tolerance = 0.55
        phash_threshold = self._dynamic_phash_threshold()
    
        for existing in Student.query.all():
            if exclude_student_id and existing.student_id == exclude_student_id:
                continue
    
            if existing.face_encoding:
                try:
                    stored = self._decode_stored_encodings(existing.face_encoding)
                    if stored:
                        distance = float(face_recognition.face_distance(stored, original_encoding).min())
                        if distance < face_tolerance:
                            return fail(f'This face closely matches an already-registered student ({existing.student_id}).', 'DUPLICATE_FACE', duplicate_student_id=existing.student_id)
                except Exception as e:
                    print(f"⚠️ Face-distance comparison error against {existing.student_id}: {e}")
    
            if existing.image_hash:
                try:
                    hash_diff = sum(c1 != c2 for c1, c2 in zip(image_hash, existing.image_hash))
                    if hash_diff <= phash_threshold:
                        return fail(f"This photo is very similar to an already-registered student's photo ({existing.student_id}).", 'DUPLICATE_IMAGE', duplicate_student_id=existing.student_id)
                except Exception as e:
                    print(f"⚠️ Hash comparison error against {existing.student_id}: {e}")

        if is_blurry and not force:
            return {
                'success': False,
                'error': (f"{blur_message} (clarity score {blur_value:.0f}; {self.BLUR_ACCEPTABLE}+ is "
                        f"clear). A blurry photo may reduce recognition accuracy."),
                'error_code': 'LOW_QUALITY',
                'requires_confirmation': True,
                'blur_value': float(blur_value),
            }
    
        # ---- Augmented encodings for more robust recognition ----
        augmented_encodings = self._generate_augmented_encodings(rgb_image, face_location)
    
        if not augmented_encodings:
            return fail('Could not generate a usable face encoding from this photo. Please retake it.', 'ENCODING_FAILED')
    
        # ---- Persist files to disk ----
        try:
            image_path = self.student_photos_dir / f"{sanitized_id}.jpg"
            cv2.imwrite(str(image_path), bgr_image)
    
            face_only_path = self.student_photos_dir / f"{sanitized_id}_face.jpg"
            cv2.imwrite(str(face_only_path), face_crop_bgr)
    
            # Old-format filename/location — load_known_faces() already checks
            # this path FIRST, so registration is instantly compatible with the
            # existing recognition loader with no changes needed there.
            self.old_encodings_dir.mkdir(parents=True, exist_ok=True)
            encoding_path = self.old_encodings_dir / f"student_{sanitized_id}_encodings.pkl"
            with open(encoding_path, 'wb') as f:
                pickle.dump(augmented_encodings, f)
        except Exception as e:
            print(f"❌ Error saving registration files for {student_id}: {e}")
            return fail('Failed to save the photo/encoding files to disk.', 'SAVE_FAILED')
    
        print(f"✅ Registered face for {student_id}: {len(augmented_encodings)} encodings saved to {encoding_path}")
    
        return {
            'success': True,
            'image_path': str(image_path),
            'face_only_path': str(face_only_path),
            'image_hash': image_hash,
            'face_encoding': original_encoding.tobytes(),
            'encoding_path': str(encoding_path),
            'num_encodings': len(augmented_encodings),
            'blur_value': float(blur_value),
        }

    def _check_image_quality(self, bgr_image) -> tuple:
        """
        Laplacian-variance blur check (port of legacy check_image_quality).
    
        Lower variance = blurrier. Thresholds: <50 severe, <100 moderate,
        <150 slight, otherwise acceptable. Anything under BLUR_ACCEPTABLE is
        flagged as blurry.
    
        Returns:
            (blur_value: float, is_blurry: bool, message: str)
        """
        try:
            gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    
            if lap_var < self.BLUR_SEVERE:
                level, is_blurry = "severely blurry", True
            elif lap_var < self.BLUR_MODERATE:
                level, is_blurry = "moderately blurry", True
            elif lap_var < self.BLUR_ACCEPTABLE:
                level, is_blurry = "slightly blurry", True
            else:
                level, is_blurry = "acceptable quality", False
    
            return lap_var, is_blurry, f"Image is {level}"
        except Exception as e:
            print(f"⚠️ Error checking image quality: {e}")
            return 0.0, True, f"Error checking image quality: {e}"
    
    def _enhance_image(self, bgr_image, blur_value: float):
        """
        Deblur/sharpen the full image when it scores below BLUR_ACCEPTABLE
        (port of the deblurring half of legacy enhance_image).
    
        - blur_value < 80: Gaussian blur followed by an unsharp mask.
        - 80 <= blur_value < 150: 3x3 sharpening kernel.
        - otherwise: image returned unchanged.
    
        Returns the enhanced image, or the original if enhancement fails.
        """
        try:
            image = bgr_image
    
            if blur_value < self.BLUR_ACCEPTABLE:
                if blur_value < self.BLUR_VERY_BLURRY_DECONV:
                    deblurred = cv2.GaussianBlur(image, (5, 5), 0)
                    gaussian = cv2.GaussianBlur(deblurred, (0, 0), 3.0)
                    image = cv2.addWeighted(deblurred, 1.5, gaussian, -0.5, 0)
                else:
                    kernel = np.array([[-1, -1, -1],
                                    [-1, 9, -1],
                                    [-1, -1, -1]])
                    image = cv2.filter2D(image, -1, kernel)
    
            return image
        except Exception as e:
            print(f"⚠️ Image enhancement error: {e}")
            return bgr_image
  
    def _enhance_face(self, face_img):
        """
        CLAHE contrast on the L channel (LAB space) plus a sharpening kernel
        (port of legacy enhance_face). Returns None on failure so the caller can
        fall back to the plain crop, exactly as legacy did.
        """
        try:
            lab = cv2.cvtColor(face_img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
    
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
    
            enhanced = cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR)
    
            kernel = np.array([[-1, -1, -1],
                            [-1, 9, -1],
                            [-1, -1, -1]])
            return cv2.filter2D(enhanced, -1, kernel)
        except Exception as e:
            print(f"⚠️ Face enhancement error: {e}")
            return None
 

    def _generate_augmented_encodings(self, rgb_image, face_location: tuple) -> list:
        """
        Generate multiple face encodings with slight augmentations, for more
        robust recognition than a single encoding gives.
    
        Produces up to 5 encodings: the original, two contrast variants
        (0.9x / 1.1x), and two small rotations (±5°). Any augmentation step
        that fails to yield a detectable face is skipped rather than aborting
        the whole registration.
    
        Args:
            rgb_image: full RGB frame (the enhanced image)
            face_location: the (top, right, bottom, left) tuple for the single
                validated face in this frame
    
        Returns:
            List of face encoding arrays (length 1-5; empty only if even the
            original encoding fails).
        """
        augmented_encodings = []
    
        original_encodings = face_recognition.face_encodings(rgb_image, [face_location], model="large")
        if not original_encodings:
            return []
        augmented_encodings.append(original_encodings[0])
    
        pil_image = Image.fromarray(rgb_image)
    
        for factor in (0.9, 1.1):
            try:
                adjusted = ImageEnhance.Contrast(pil_image).enhance(factor)
                adjusted_encodings = face_recognition.face_encodings(np.array(adjusted), model="large")
                if adjusted_encodings:
                    augmented_encodings.append(adjusted_encodings[0])
            except Exception as e:
                print(f"⚠️ Contrast augmentation ({factor}) failed: {e}")
    
        for angle in (-5, 5):
            try:
                rotated = pil_image.rotate(angle)
                rotated_encodings = face_recognition.face_encodings(np.array(rotated), model="large")
                if rotated_encodings:
                    augmented_encodings.append(rotated_encodings[0])
            except Exception as e:
                print(f"⚠️ Rotation augmentation ({angle}°) failed: {e}")
    
        return augmented_encodings
     
    
    def _decode_stored_encodings(self, blob) -> list:
        """
        Decode a students.face_encoding blob into a list of 128-d encodings.

        Two formats exist in the database:
        - Flask admin registration: one raw float64 encoding (1024 bytes).
        - PyQt registration: a pickled LIST of augmented encodings.
        Returns [] if the blob can't be decoded, so callers just skip it.
        """
        try:
            if len(blob) == 128 * 8:
                return [np.frombuffer(blob, dtype=np.float64)]
            data = pickle.loads(blob)
            if isinstance(data, np.ndarray):
                data = [data] if data.ndim == 1 else list(data)
            return [np.asarray(e, dtype=np.float64) for e in data
                    if np.asarray(e).shape == (128,)]
        except Exception:
            return []

    def _dynamic_phash_threshold(self) -> int:
        """
        Calculate a perceptual-hash Hamming-distance threshold for duplicate
        detection, scaled to the size of the existing student dataset.
    
        Small datasets (<10 students) use a fixed conservative threshold of 10,
        since there isn't enough data to estimate a meaningful distribution.
        Larger datasets sample pairs of existing hashes and set the threshold
        to roughly a third of the mean pairwise distance (floor of 5), so
        genuine duplicates (very small distance) get caught without
        false-flagging photos of different students who just look somewhat
        alike. Same approach as register_student.py's get_dynamic_threshold(),
        ported from raw sqlite3 to the Student model.
    
        Returns:
            int: Hamming-distance threshold, in bits (phash default is 64 bits).
        """
        from app.models import Student
        import random
    
        count = Student.query.count()
        if count < 10:
            return 10
    
        hashes = [s.image_hash for s in Student.query.filter(Student.image_hash.isnot(None)).all()]
        if len(hashes) < 2:
            return 10
    
        try:
            if len(hashes) > 15:
                pairs = []
                for _ in range(min(100, len(hashes) * 2)):
                    i, j = random.sample(range(len(hashes)), 2)
                    pairs.append((hashes[i], hashes[j]))
            else:
                pairs = [(hashes[i], hashes[j]) for i in range(len(hashes)) for j in range(i + 1, len(hashes))]
    
            distances = [sum(c1 != c2 for c1, c2 in zip(h1, h2)) for h1, h2 in pairs]
            if not distances:
                return 10
    
            mean_dist = sum(distances) / len(distances)
            return max(5, int(mean_dist / 3))
        except Exception as e:
            print(f"⚠️ Error calculating dynamic phash threshold: {e}")
            return 10
        
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
            sensitivity: Maximum face distance (0-1) for a match; lower = stricter
            
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