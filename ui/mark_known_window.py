import os
import shutil
import sqlite3
import cv2
import pickle
import face_recognition
import imagehash
import numpy as np
from PIL import Image, ImageOps
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QLabel, QApplication, QPushButton, QHBoxLayout, QLineEdit, QMessageBox, QWidget
)
from PyQt5 import QtGui
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from config.utils import enhance_image
from config.utils_constants import DATABASE_PATH, IMAGE_DIR

def compute_phash(image_path):
        image = Image.open(image_path).convert("L").resize((64, 64))  # Convert to grayscale & resize
        return str(imagehash.phash(image))  # Returns a perceptual hash



class MarkKnownWindow(QMainWindow):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✅ Mark as Known")
        self.setGeometry(350, 250, 550, 500)

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS


        self.image_path = image_path
        self.parent = parent  

        # ✅ Main Layout
        layout = QVBoxLayout()

        # ✅ Image Display
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(300, 300)
        layout.addWidget(self.image_label)

        # ✅ Load Image Preview
        self.load_image_preview()

        # ✅ Input Fields
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter student name")

        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Enter student ID (numbers only)")
        self.id_input.setValidator(QtGui.QIntValidator())  # Only allow numbers

        layout.addWidget(QLabel("👤 Student Name:"))
        layout.addWidget(self.name_input)
        layout.addWidget(QLabel("🆔 Student ID:"))
        layout.addWidget(self.id_input)

        # ✅ Buttons
        button_layout = QHBoxLayout()
        self.submit_button = QPushButton("✅ Save")
        self.submit_button.clicked.connect(self.save_as_known)
        self.cancel_button = QPushButton("❌ Cancel")
        self.cancel_button.clicked.connect(self.close)

        button_layout.addWidget(self.submit_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # ✅ Apply Layout
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def save_as_known(self):
        """Moves the image, renames it, and registers it in the database."""
        student_name = self.nameInput.text().strip()
        student_id = self.idInput.text().strip()

        if not student_id or not student_id.isdigit():
            QMessageBox.warning(self, "Invalid Input", "Student ID must be a valid number!")
            return

        student_id = int(student_id)  # ✅ Convert to integer safely

        if not student_name or not student_id:
            QMessageBox.warning(self, "Incomplete Data", "Please fill all fields.")
            return
        
        enhanced_image_path = enhance_image(self.image_path)  # ✅ Apply enhancement

        if not enhanced_image_path:
            QMessageBox.warning(self, "Error", "Image enhancement failed!")
            return

        new_image_path = os.path.join("student_images", f"{student_id}.jpg")

        try:
            # ✅ Ensure the file exists before moving
            if not os.path.exists(self.image_path):
                QMessageBox.warning(self, "Error", "Selected image does not exist!")
                return
            
            # ✅ Check if student ID already exists
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()
            cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone():
                QMessageBox.warning(self, "Duplicate ID", "A student with this ID already exists!")
                conn.close()
                return

            
            # ✅ Move & rename the image
            shutil.move(self.image_path, new_image_path)
            print(f"✅ Moved to student_images: {new_image_path}")

            # ✅ Verify the image was successfully moved
            if not os.path.exists(new_image_path):
                QMessageBox.warning(self, "Error", "Image move failed! Try again.")
                return

            # ✅ Compute image hash before moving
            image_hash = compute_phash(new_image_path)
            if not image_hash:
                QMessageBox.warning(self, "Error", "Failed to compute image hash.")
                return


            # ✅ Extract face encoding
            image = face_recognition.load_image_file(new_image_path)
            face_encodings = face_recognition.face_encodings(image)
            
            if not face_encodings:
                QMessageBox.warning(self, "Face Error", "No face detected in the image!")

                 # ❌ Remove the image since it's not valid
                os.remove(new_image_path)
                print(f"❌ Removed invalid image: {new_image_path}")
                return

            encoding_blob = pickle.dumps(face_encodings[0])  # Convert numpy array to BLOB

        
            # ✅ Insert into the database
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO students (student_id, name, image_path, image_hash, face_encoding) 
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, student_name, new_image_path, image_hash, encoding_blob))
            
            conn.commit()
            conn.close()

            QMessageBox.information(self, "Success", "Student registered successfully.")
            self.close()

            # ✅ Refresh unknown images list
            if self.parent:
                self.parent.refresh_unknown_images()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")
