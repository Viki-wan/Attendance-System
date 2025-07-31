import os
import cv2
import sqlite3
import pickle
import numpy as np
import imagehash
import face_recognition
from PIL import Image
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox, QApplication, QHBoxLayout
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from config.utils_constants import UNKNOWN_DIR, DATABASE_PATH
from ui.mark_known_window import MarkKnownWindow
from ui.register_student import RegisterStudentWindow

class ReviewUnknownFacesWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📷 Review Unknown Faces")
        self.setGeometry(350, 150, 600, 600)

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS


        # ✅ Layout
        layout = QVBoxLayout()

        # ✅ Image Preview
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(450, 450)
        layout.addWidget(self.image_label)

        # ✅ Matching Suggestion
        self.suggestion_label = QLabel("🔍 Possible match will appear here.", self)
        self.suggestion_label.setAlignment(Qt.AlignCenter)
        self.suggestion_label.setStyleSheet("font-size: 14px; color: blue;")
        layout.addWidget(self.suggestion_label)

        # ✅ Navigation Buttons
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("⏮ Previous")
        self.next_button = QPushButton("Next ⏭")
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)
        layout.addLayout(nav_layout)

        # ✅ Action Buttons
        action_layout = QHBoxLayout()
        self.mark_known_button = QPushButton("📝 Mark as Known")
        self.delete_button = QPushButton("🗑️ Delete")
        action_layout.addWidget(self.mark_known_button)
        action_layout.addWidget(self.delete_button)
        layout.addLayout(action_layout)

        self.setLayout(layout)

        # ✅ Load Images & Initialize UI
        self.unknown_images = self.load_unknown_images()
        self.current_index = 0

        if self.unknown_images:
            self.show_image(self.current_index)
        else:
            self.image_label.setText("No unknown faces found.")
            self.disable_buttons()

        # ✅ Connect Buttons
        self.prev_button.clicked.connect(self.show_previous)
        self.next_button.clicked.connect(self.show_next)
        self.delete_button.clicked.connect(self.delete_current_image)
        self.mark_known_button.clicked.connect(self.mark_as_known)


    def load_unknown_images(self):
        """Load only unique and valid unknown images for review."""
        if not os.path.exists(UNKNOWN_DIR):
            os.makedirs(UNKNOWN_DIR)  # ✅ Create the folder if it doesn't exist

        images = [f for f in os.listdir(UNKNOWN_DIR) if f.endswith(('.jpg', '.png', '.jpeg'))]
        valid_images = []
        seen_hashes = set()

        for img in images:
            img_path = os.path.join(UNKNOWN_DIR, img)  # ✅ Ensure correct file path

            try:
                # ✅ Load image and check face presence
                image = face_recognition.load_image_file(img_path)
                face_locations = face_recognition.face_locations(image)

                if not face_locations:
                    print(f"⚠️ Skipped {img} (No face detected)")
                    continue  # Skip images with no faces
                
                # ✅ Convert to hash for duplicate filtering
                pil_image = Image.open(img_path)
                face_hash = str(imagehash.phash(pil_image))

                if face_hash in seen_hashes:
                    print(f"⚠️ Duplicate detected in review list, skipping: {img}")
                    continue  # Skip duplicate images

                # ✅ Add to valid images & store hash
                seen_hashes.add(face_hash)
                valid_images.append(img)

            except Exception as e:
                print(f"❌ Error loading {img}: {e}")

        print(f"✅ Loaded {len(valid_images)} unique unknown images.")
        return valid_images
    
    def show_image(self, index):
        """Display the selected unknown face while ensuring clarity and proper scaling."""
        if not self.unknown_images:
            self.image_label.setText("No unknown faces found.")
            self.disable_buttons()
            return

        img_filename = self.unknown_images[index]
        img_path = os.path.join(UNKNOWN_DIR, img_filename)

        if not os.path.exists(img_path):  # ✅ Check if the image exists
            print(f"⚠️ Image not found: {img_path}")
            self.image_label.setText("⚠️ Image not found!")
            return
        
        # ✅ Enhance image before displaying (for better matching)
        enhanced_path = img_path.replace(".jpg", "_enhanced.jpg")  # Adjust if using other formats
        if os.path.exists(enhanced_path):
            img_path = enhanced_path 

        pixmap = QPixmap(img_path)

        if pixmap.isNull():  # ✅ Handle unreadable/corrupted images
            print(f"⚠️ Cannot load image: {img_path}")
            self.image_label.setText("⚠️ Cannot display image!")
            return
        
       
        scaled_pixmap = pixmap.scaled(
            450, 450, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setPixmap(scaled_pixmap)

        self.suggest_similar_face(img_path)

    def suggest_similar_face(self, unknown_image_path):
        """Compares unknown face against registered faces and suggests a possible match."""
        # ✅ Load unknown face encoding
        unknown_image = face_recognition.load_image_file(unknown_image_path)
        unknown_encodings = face_recognition.face_encodings(unknown_image)

        if not unknown_encodings:
            self.suggestionLabel.setText("No face detected in this image.")
            return
            
        unknown_encoding = unknown_encodings[0]

            # ✅ Fetch all registered encodings
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        cursor.execute("SELECT student_id, name, face_encoding FROM students")
        registered_faces = cursor.fetchall()
        conn.close()

        best_match_id = None
        best_match_name = None
        best_distance = 1.0  # Start with max possible distance

        for student_id, name, encoding_blob in registered_faces:
            known_encoding = pickle.loads(encoding_blob)  # Convert from BLOB

            # ✅ Ensure `unknown_encoding` is available
            if unknown_encoding is None:
                continue

            # ✅ Compute face distance
            distance = face_recognition.face_distance([known_encoding], unknown_encoding)[0]

            if distance < best_distance and distance < 0.5:  # Only consider strong matches
                best_distance = distance
                best_match_id = student_id
                best_match_name = name

        # ✅ Display match suggestion
        if best_match_name:
            confidence = (1.0 - best_distance) * 100
            self.suggestionLabel.setText(f"🔹 This face looks like {best_match_name} ({confidence:.2f}% match)")
        else:
            self.suggestionLabel.clear()


    def show_previous(self):
        """Show the previous unknown face."""
        if self.unknown_images:
            self.current_index = (self.current_index - 1) % len(self.unknown_images)
            self.show_image(self.current_index)

    def show_next(self):
        """Show the next unknown face."""
        if self.unknown_images:
            self.current_index = (self.current_index + 1) % len(self.unknown_images)
            self.show_image(self.current_index)

    def delete_current_image(self):
        """Delete the currently displayed unknown face after confirmation."""
        if not self.unknown_images:
            return

        img_path = os.path.join(UNKNOWN_DIR, self.unknown_images[self.current_index])
        reply = QMessageBox.question(self, "Confirm Deletion", 
                                     f"Are you sure you want to delete this image?\n\n{img_path}",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            os.remove(img_path)
            print(f"🗑️ Deleted: {img_path}")

            # Reload images after deletion
            self.unknown_images = self.load_unknown_images()

            if not self.unknown_images:
                self.image_label.setText("No unknown faces remaining.")
                self.disable_buttons()
            else:
                self.current_index = self.current_index % len(self.unknown_images)
                self.show_image(self.current_index)

    def mark_as_known(self):
        """Opens the MarkKnownWindow for marking an unknown face as a known student."""
        if not self.unknown_images:
            return

        img_path = os.path.join(UNKNOWN_DIR, self.unknown_images[self.current_index])

        reply = QMessageBox.question(self, "Mark as Known",
                                    "Proceed to mark this face as known?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    
        if reply == QMessageBox.Yes:
            self.mark_known_window = MarkKnownWindow(img_path, parent=self)
            self.mark_known_window.show()

    def refresh_unknown_images(self):
        """Reloads the unknown images after marking one as known."""
        self.unknown_images = self.load_unknown_images()

        if not self.unknown_images:
            self.image_label.setText("No unknown faces remaining.")
            self.disable_buttons()
        else:
            self.current_index = self.current_index % len(self.unknown_images)
            self.show_image(self.current_index)


    def open_registration_form(self, image_path):
        """Opens the student registration form with the image preloaded."""
        self.register_window = RegisterStudentWindow()
        self.register_window.set_image(image_path)  # Set the image path in the form
        self.register_window.show()

    def disable_buttons(self):
        """Disable navigation and action buttons when no images exist."""
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.mark_known_button.setEnabled(False)
