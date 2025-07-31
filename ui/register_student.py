import os
import cv2
import shutil
import sqlite3
import pickle
import imagehash
import face_recognition
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QVBoxLayout, QApplication, QPushButton, QLineEdit, QFormLayout, QMessageBox
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from PIL import Image, ImageOps
from ui.webcam_window import WebcamWindow
from config.utils import enhance_image
from config.utils_constants import IMAGE_DIR

def compute_phash(image_path):
        image = Image.open(image_path).convert("L").resize((64, 64))  # Convert to grayscale & resize
        return str(imagehash.phash(image))  # Returns a perceptual hash


class RegisterStudentWindow(QMainWindow):
    def __init__(self, image_path=None, parent_window=None):
        super().__init__()

        self.setWindowTitle("Register Student")
        self.setFixedSize(400, 500)  # ✅ Fixed modern size

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS


        # 🔹 Central Widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)  # ✅ Set the central widget
        layout = QVBoxLayout(central_widget)  # ✅ Apply layout to central widget

        # 🔹 Profile Image Placeholder
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setPixmap(QPixmap("icons/profile_placeholder.png").scaled(100, 100, Qt.KeepAspectRatio))
        layout.addWidget(self.image_label)

        # 🔹 Form Layout
        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.id_input = QLineEdit()
        form_layout.addRow("Student Name:", self.name_input)
        form_layout.addRow("Student ID:", self.id_input)

        layout.addLayout(form_layout)

        # 🔹 Buttons
        self.capture_button = QPushButton("📷 Capture Photo")
        self.submit_button = QPushButton("✅ Register")
        self.cancel_button = QPushButton("❌ Cancel")

        layout.addWidget(self.capture_button)
        layout.addWidget(self.submit_button)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

        # 🔹 Styling
        self.setStyleSheet("""
            QWidget {
                background-color: #ecf0f1;
                border-radius: 10px;
            }
            QLabel {
                font-size: 16px;
                font-weight: bold;
            }
            QLineEdit {
                padding: 5px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #2980b9;
                color: white;
                font-size: 16px;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
        """)

        self.parent_window = parent_window  # Store the reference to the Review Unknown Faces window
        self.captured_image_path = image_path  # Store the image path for unknown faces

        self.capture_button.clicked.connect(self.open_webcam)
        self.submit_button.clicked.connect(self.register_student)
        self.cancel_button.clicked.connect(self.close)

        if self.captured_image_path:
            self.show_preview(self.captured_image_path)

    
    def compute_phash(image_path):
        image = cv2.imread(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)  # Convert to grayscale

        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))

        if len(faces) == 0:
            print("⚠️ No face detected! Hashing full image instead.")
            pil_image = Image.fromarray(gray)
        else:
            for (x, y, w, h) in faces:
                pad = int(0.15 * w)  # Add padding
                x, y = max(0, x - pad), max(0, y - pad)
                w, h = min(gray.shape[1] - x, w + 2 * pad), min(gray.shape[0] - y, h + 2 * pad)

                face = gray[y:y+h, x:x+w]
                pil_image = Image.fromarray(face)

                # 🔹 Draw rectangle on the original image
                cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)

        # 🔹 Display the image with tracking for 2 seconds
            cv2.imshow("Face Tracking", image)
            cv2.waitKey(2000)  # Show for 2 seconds
            cv2.destroyAllWindows()

    # 🔹 Enhance the face image before hashing
        pil_image = ImageOps.exif_transpose(pil_image)
        pil_image = pil_image.resize((64, 64))
        pil_image = ImageOps.autocontrast(pil_image)

        return str(imagehash.phash(pil_image))  # Returns a perceptual hash

    def set_image(self, image_path):
        """Preload an image for registration."""
        self.captured_image_path = image_path
        pixmap = QPixmap(image_path)
        self.setPixmap(pixmap)
    
    def open_webcam(self):
        """Opens the webcam window for capturing a photo."""
        self.webcam_window = WebcamWindow(self)
        self.webcam_window.show()

    def save_photo(self, frame):
        """Saves the captured photo only if the admin confirms."""
        student_id = self.id_input.text().strip()

        if not student_id:
            QMessageBox.warning(self, "Missing ID", "Please enter Student ID before capturing.")
            return

        raw_path = os.path.join(IMAGE_DIR, f"{student_id}.jpg")
        cv2.imwrite(raw_path, frame)

        enhanced_path = enhance_image(self.raw_path)  # ✅ Apply enhancement

        if enhanced_path:
            self.captured_image_path = enhanced_path  # Store enhanced image for database
        else:
            self.captured_image_path = raw_path  # Fallback to original


    def register_student(self, is_unknown=False, unknown_image_path=None):
        student_name = self.name_input.text().strip()
        student_id = self.id_input.text().strip()

        if not student_name or not student_id or not self.captured_image_path:
            QMessageBox.warning(self, "Incomplete Data", "Please fill all fields and capture a photo.")
            return
        
        if is_unknown:
            self.captured_image_path = unknown_image_path  # Use the unknown image
        elif not self.captured_image_path:
            QMessageBox.warning(self, "Incomplete Data", "Please capture a photo.")
            return

        try:
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()

        # Compute image hash
            image_hash = compute_phash(self.captured_image_path)
            print(f"Computed Hash for new student: {image_hash}")

        # Check if Student ID already exists
            cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone():
                QMessageBox.warning(self, "Duplicate ID", "A student with this ID already exists")
                 # 🔴 DELETE IMAGE IF REGISTRATION FAILS
                if os.path.exists(self.captured_image_path):
                    os.remove(self.captured_image_path)
                    print(f"❌ Deleted unregistered image: {self.captured_image_path}")
                
                return
            

        # Check if Image is already registered
            cursor.execute("SELECT student_id, image_hash FROM students")
            for student_id_db, stored_hash in cursor.fetchall():
               if stored_hash:
                hash_diff = imagehash.hex_to_hash(image_hash) - imagehash.hex_to_hash(stored_hash)
                if hash_diff < 5:  # Tolerance level for similarity
                        print(f"Duplicate image detected! Student ID: {student_id_db}, Hamming Distance: {hash_diff}")

                         # 🔴 DELETE IMAGE IF IT'S A DUPLICATE
                        if os.path.exists(self.captured_image_path):
                            os.remove(self.captured_image_path)
                            print(f"❌ Deleted duplicate image: {self.captured_image_path}")

                        QMessageBox.warning(self, "Duplicate Image", "This image is already registered!")
                        conn.close()
                        return
            
            image = face_recognition.load_image_file(self.captured_image_path)
            face_locations = face_recognition.face_locations(image, model="hog")
            face_encodings = face_recognition.face_encodings(image)

            if not face_encodings:
                QMessageBox.warning(self, "Face Not Detected", "No face detected in the image!")
                return
            
            encoding_blob = pickle.dumps(face_encodings[0])

            final_image_path = os.path.join("student_images", f"{student_id}.jpg")

        # Insert student into the database
            cursor.execute("""
                INSERT INTO students (name, student_id, image_path, image_hash, face_encoding)
                VALUES (?, ?, ?, ?, ?)
            """, (student_name, student_id, self.captured_image_path, image_hash, encoding_blob))
            conn.commit()
            QMessageBox.information(self, "Success", "Student registered successfully.")

            # Move image ONLY after successful registration
            if is_unknown:
                shutil.move(self.captured_image_path, final_image_path)
                print(f"✅ Moved image from unknown_faces to student_images: {final_image_path}")


        except sqlite3.Error as e:
            print(f"Database error: {e}")
            QMessageBox.critical(self, "Database Error", f"An error occurred: {e}")

        except Exception as e:
            print(f"Unexpected error: {e}")
            QMessageBox.critical(self, "Unexpected Error", f"An unexpected error occurred: {e}")

        finally:
            if conn:
                conn.close()  # 🔹 Ensures connection is closed even if an error occurs

        self.close()

