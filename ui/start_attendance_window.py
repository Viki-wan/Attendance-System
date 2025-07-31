import sys
import cv2
import sqlite3
import numpy as np
import face_recognition
import hashlib
import imagehash
from PIL import Image
import pickle
import time as system_time
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QProgressBar, QMessageBox
from PyQt5.QtCore import Qt, QTimer
from config.utils_constants import *
from ui.settings_window import SettingsWindow
from config.utils import enhance_image


def compute_phash(image_path):
        image = Image.open(image_path).convert("L").resize((64, 64))  # Convert to grayscale & resize
        return str(imagehash.phash(image))  # Returns a perceptual hash
class StartAttendanceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📡 Start Attendance")
        self.setGeometry(300, 200, 750, 550)

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS


         # ✅ Load settings before applying them
        self.settings = self.load_settings()  
        self.apply_saved_settings()
        # ✅ Layout
        layout = QVBoxLayout()

        # ✅ Status Label
        self.status_label = QLabel("🔄 System Ready...", self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(self.status_label)

        # ✅ Progress Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # ✅ Attendance Table
        self.attendance_table = QTableWidget(self)
        self.attendance_table.setColumnCount(3)
        self.attendance_table.setHorizontalHeaderLabels(["Student ID", "Name", "Status"])
        layout.addWidget(self.attendance_table)

        # ✅ Start & Stop Buttons
        self.start_button = QPushButton("▶ Start Attendance")
        self.start_button.clicked.connect(self.start_attendance)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("⏹ Stop Attendance")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_attendance)
        layout.addWidget(self.stop_button)

        self.setLayout(layout)

        # ✅ Timer for Processing
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)

        # ✅ Load Known Faces
        self.known_faces, self.student_ids = self.load_known_faces()

        # ✅ Tracking Variables
        self.recognized_students = {}
        self.progress = 0
        self.match_counter = {}
        self.unknown_counter = 0
        self.cap = None

    def get_name(self, student_id):
        """Fetch student name from the database using student_id."""
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM students WHERE student_id = ?", (student_id,))
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else "Unknown"

    def start_attendance(self):
        known_faces, student_ids = self.load_known_faces()
        if not known_faces:
            QMessageBox.warning(self, "No Registered Faces", "No students are registered")
            return

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            QMessageBox.critical(self, "Camera Error", "Could not open webcam")
            return
        
        match_counter = {}  # Track repeated matches for known faces
        unknown_counter = 0  # Track repeated unknown face appearances
        required_matches = 3  # Minimum times a face must be seen before marking attendance

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            avg_brightness = gray.mean()

            if avg_brightness < 20:
                cv2.putText(frame, "Low light detected", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.imshow("Attendance System", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame, model="hog")

            if not face_locations:
                cv2.putText(frame, "No face detected", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                unknown_counter = 0  # Reset unknown counter if no face is found
                cv2.imshow("Attendance System", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for face_encoding, face_location in zip(face_encodings, face_locations):

                tolerance = int(self.settings.get("face_recognition_sensitivity", "50")) / 100
                matches = face_recognition.compare_faces(known_faces, face_encoding, tolerance=tolerance)
                face_distances = face_recognition.face_distance(known_faces, face_encoding)

                student_id = "Unknown"
                name = "Unknown"

                required_matches = int(self.settings.get("required_matches", "3"))

                save_unknown_faces = self.settings.get("save_unknown_faces", "1") == "1"

                if True in matches:
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        student_id = student_ids[best_match_index]
                        name = self.get_name(student_id)

                        # Confidence Score
                        confidence = 1.0 - face_distances[best_match_index]
                        confidence_text = f"Confidence: {confidence:.2f}"

                        # ✅ Count the number of times a face is recognized
                        match_counter[student_id] = match_counter.get(student_id, 0) + 1

                        # ✅ Mark attendance only when seen required times
                        if match_counter[student_id] == required_matches:
                            self.mark_attendance(student_id)
                else:
                    unknown_counter += 1

                     # ✅ Only save unknown faces if the setting is enabled
                    if save_unknown_faces and unknown_counter >= required_matches:
                        self.save_unknown_face(frame, face_location)
                        print(f"⚠️ Unknown face saved after {required_matches} detections.")
                        unknown_counter = 0  # Reset counter after saving
                    elif not save_unknown_faces:
                        print("⚠️ Unknown face ignored due to settings.")

                    # ✅ Save unknown face only if it appears multiple times
                    if unknown_counter == required_matches:
                        self.save_unknown_face(frame, face_location)
                        unknown_counter = 0  # Reset counter after saving
                        

                # ✅ Draw a box around the face
                top, right, bottom, left = face_location
                color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

                # ✅ Display the student's name and ID or "Unknown"
                label = f"{name} ({student_id})" if name != "Unknown" else "⚠️ Unknown"
                cv2.putText(frame, label, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            cv2.imshow("Attendance System", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    def save_unknown_face(self, frame, face_location):
        """Save detected unknown faces with correct scaling and enhancement."""
        try:
            if not os.path.exists(UNKNOWN_DIR):
                os.makedirs(UNKNOWN_DIR)

            # Extract and pad face region
            top, right, bottom, left = face_location
            padding = 20
            top, bottom = max(0, top - padding), min(frame.shape[0], bottom + padding)
            left, right = max(0, left - padding), min(frame.shape[1], right + padding)
            face_img = frame[top:bottom, left:right]

            # Ensure face is large enough for recognition
            if face_img.shape[0] < MIN_FACE_SIZE or face_img.shape[1] < MIN_FACE_SIZE:
                print("⚠️ Face too small, skipping save.")
                return

            # Convert image and generate hash
            pil_image = Image.fromarray(cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB))
            standardized_image = pil_image.convert("L").resize((128, 128))
            new_hash = str(imagehash.phash(standardized_image))

            
            # Prevent duplicate saving
            for file in os.listdir(UNKNOWN_DIR):
                existing_img = Image.open(os.path.join(UNKNOWN_DIR, file))
                existing_hash = str(imagehash.phash(existing_img))
                if imagehash.hex_to_hash(new_hash) - imagehash.hex_to_hash(existing_hash) < HASH_SIMILARITY_THRESHOLD:
                    print("⚠️ Duplicate unknown face detected, not saving.")
                    return

            # Save file
            file_path = os.path.join(UNKNOWN_DIR, f"unknown_{uuid.uuid4().hex[:8]}.jpg")
            pil_image.save(file_path)

            # Check brightness & contrast before enhancement
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            avg_brightness = np.mean(gray)
            contrast = np.std(gray)

            if BRIGHTNESS_MIN < avg_brightness < BRIGHTNESS_MAX and contrast > CONTRAST_THRESHOLD:
                print("⚠️ Image quality is good, skipping enhancement.")
                final_path = file_path
            else:
                enhanced_path = enhance_image(file_path)
                if enhanced_path:
                    final_path = enhanced_path
                    print(f"📸 Enhanced & saved unknown face at {final_path}")
                else:
                    final_path = file_path  # Fallback to original

            return final_path

        except Exception as e:
            print(f"❌ Error saving unknown face: {e}")
            return None
        
    def update_progress(self):
        """Simulates progress update while attendance is running."""
        current_value = self.progress_bar.value()
        if current_value < 100:
            self.progress_bar.setValue(current_value + 5)

    def load_known_faces(self):
        self.known_faces = []  # Clear previous encodings
        self.student_ids = []  

        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        cursor.execute("SELECT student_id, face_encoding FROM students")
        records = cursor.fetchall()
        conn.close()

        for student_id, encoding_blob in records:
            if encoding_blob:
                # Convert stored string back to numpy array
                encoding_array = pickle.loads(encoding_blob)
                self.known_faces.append(encoding_array)
                self.student_ids.append(student_id)
                print(f"✅ Loaded encoding for student {student_id}")

        print(f"✅ Total loaded faces: {len(self.known_faces)}")
        return self.known_faces, self.student_ids

    def stop_attendance(self):
        """Stops the attendance process."""
        self.status_label.setText("✅ Attendance Stopped.")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.timer.stop()
        if self.cap:
            self.cap.release()
            cv2.destroyAllWindows()

    def update_table(self, student_id, name, status):
        """Updates the attendance table dynamically."""
        row = self.attendance_table.rowCount()
        self.attendance_table.insertRow(row)
        self.attendance_table.setItem(row, 0, QTableWidgetItem(student_id))
        self.attendance_table.setItem(row, 1, QTableWidgetItem(name))
        self.attendance_table.setItem(row, 2, QTableWidgetItem(status))

    def mark_attendance(self, student_id):
        """Marks attendance in the database."""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        today_date = datetime.now().strftime("%Y-%m-%d")

        cursor.execute("SELECT * FROM attendance WHERE student_id = ? AND date = ?", (student_id, today_date))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO attendance (student_id, date, status) VALUES (?, ?, 'Present')",
                           (student_id, today_date))
            conn.commit()

        conn.close()

    def load_settings(self):
        """Loads settings from the database."""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT setting_key, setting_value FROM settings")
        settings = dict(cursor.fetchall())
        conn.close()

        return settings if settings else {} 

    def apply_saved_settings(self):
        """Load and apply settings when the dashboard starts."""
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        cursor.execute("SELECT setting_key, setting_value FROM settings")
        settings = dict(cursor.fetchall())
        conn.close()
        
        if self.settings.get("auto_start", "0") == "1":
            self.start_attendance()  # Function to begin attendance automatically


    def get_saved_dark_mode_setting(self):
        """Retrieve the saved dark mode setting from the database."""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'dark_mode'")
        result = cursor.fetchone()
        conn.close()

        return result is not None and result[0] == "1"  # Convert result to Boolean


    def enable_dark_mode(self):
        """Apply dark mode to the entire application."""
        dark_stylesheet = """
            QWidget { background-color: #222; color: #ddd; }
            QPushButton { background-color: #333; border: 1px solid #555; }
            QLabel { color: #fff; }
        """
        self.setStyleSheet(dark_stylesheet)

    def disable_dark_mode(self):
        """Reset to default light mode."""
        self.setStyleSheet("")

