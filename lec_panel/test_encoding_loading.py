"""
Quick test script to verify encoding loading works
Run this to see if encodings can be loaded before testing in the web interface
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from app.services.face_recognition_service import FaceRecognitionService

app = create_app('development')

with app.app_context():
    print("=" * 60)
    print("Testing Face Encoding Loading")
    print("=" * 60)
    
    # Initialize service
    face_service = FaceRecognitionService()
    
    print(f"\n📁 Encoding directories:")
    print(f"   1. Old format: {face_service.old_encodings_dir}")
    print(f"   2. Alternative: {face_service.alt_encodings_dir}")
    print(f"   3. New format: {face_service.encodings_dir}")
    
    # Check if directories exist
    print(f"\n📂 Directory existence:")
    print(f"   Old format exists: {face_service.old_encodings_dir.exists()}")
    print(f"   Alternative exists: {face_service.alt_encodings_dir.exists()}")
    print(f"   New format exists: {face_service.encodings_dir.exists()}")
    
    # Count encoding files
    if face_service.old_encodings_dir.exists():
        old_files = list(face_service.old_encodings_dir.glob("student_*_encodings.pkl"))
        print(f"\n📊 Found {len(old_files)} encoding files in old format directory")
        if old_files:
            print(f"   Example: {old_files[0].name}")
    
    # Try loading all faces
    print(f"\n🔄 Attempting to load all face encodings...")
    known_faces, student_ids = face_service.load_known_faces()
    
    print(f"\n✅ Results:")
    print(f"   Loaded {len(known_faces)} face encodings")
    print(f"   Student IDs: {len(student_ids)}")
    
    if known_faces:
        print(f"\n📝 First few students:")
        for i, sid in enumerate(student_ids[:5]):
            print(f"   {i+1}. {sid}")
    else:
        print(f"\n❌ No encodings loaded! Check the paths above.")
    
    print("\n" + "=" * 60)

