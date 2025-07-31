import os

# Flask configuration
SECRET_KEY = 'your-secret-key-here'
DATABASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'attendance.db')

# Application settings
STUDENT_IMAGES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'student_images')