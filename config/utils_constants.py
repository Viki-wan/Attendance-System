import os

# Directories
IMAGE_DIR = "student_images"
UNKNOWN_DIR = "unknown_faces"
REPORT_DIR = "attendance_reports"

# Create directories if they don't exist
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(UNKNOWN_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

# Database
DATABASE_PATH = "attendance.db"

ENCODING_DIR = "face_encodings"

# Face Recognition Settings
FACE_RECOGNITION_TOLERANCE = 0.45  # Lower values are more strict
FACE_RECOGNITION_MODEL = "hog"  # Options: 'hog' (faster) or 'cnn' (more accurate)

# Face Quality Thresholds
MIN_FACE_SIZE = 50
MOVEMENT_THRESHOLD = 0.08
STEADY_FRAME_THRESHOLD = 1
BRIGHTNESS_MIN = 50
BRIGHTNESS_MAX = 180
CONTRAST_THRESHOLD = 20
HASH_SIMILARITY_THRESHOLD = 10  # Adjust based on testing
FACE_SIMILARITY_THRESHOLD = 0.6  # Lower value = stricter matching
HASH_SIMILARITY_THRESHOLD = 5
REQUIRED_MATCH_COUNT = 3  # Number of consecutive detections before marking attendance

# Timeout Settings (in seconds)
FACE_TRACKING_TIMEOUT = 60
SESSION_TIMEOUT = 600

# UI Settings
UI_REFRESH_RATE = 50  # milliseconds between UI updates
PREVIEW_WIDTH = 400
PREVIEW_HEIGHT = 400

# Security
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"  # Should be changed in production
PASSWORD_HASH_ITERATIONS = 100000  # For secure password storage

# Feature Flags
ENABLE_FACE_ENHANCEMENT = True
ENABLE_MULTI_CAMERA = True
ENABLE_DATA_PRIVACY = True
ENABLE_MASK_DETECTION = False  # Experimental feature
