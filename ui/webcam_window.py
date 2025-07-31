import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel, QPushButton, QMessageBox
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer

class WebcamWindow(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.setWindowTitle("📸 Capture Photo")
        self.setGeometry(400, 200, 500, 500)  # Compact & centered window

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS


        # ✅ Initialize camera
        self.cap = cv2.VideoCapture(0)
        self.captured_frame = None

        # ✅ Layout
        layout = QVBoxLayout()

        # 📌 Live camera feed
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(450, 350)  # ✅ Keep camera feed at a fixed size
        layout.addWidget(self.image_label)

        # ⚠️ Face Alignment Indicator
        self.status_label = QLabel("🔍 Align your face within the box")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: gray;")
        layout.addWidget(self.status_label)

        # ▶ Capture Button
        self.capture_button = QPushButton("📸 Capture")
        self.capture_button.clicked.connect(self.capture_photo)
        self.capture_button.setStyleSheet("background-color: #007BFF; color: white; font-size: 14px; padding: 8px;")
        layout.addWidget(self.capture_button)

        self.setLayout(layout)

        # ✅ Timer for real-time webcam updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(50)  # Update every 50ms

    def update_frame(self):
        """Continuously updates the webcam feed with real-time face detection."""
        ret, frame = self.cap.read()
        if not ret:
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ✅ Detect faces
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

        if len(faces) == 0:
            self.status_label.setText("⚠️ No face detected! Adjust your position.")
        else:
            self.status_label.setText("✅ Face detected. Stay still and capture.")

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Green rectangle around face

        # ✅ Convert OpenCV frame to Qt format
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        self.image_label.setPixmap(QPixmap.fromImage(q_img))

    def capture_photo(self):
        """Capture a photo with real-time validation before saving."""
        ret, frame = self.cap.read()
        if not ret:
            QMessageBox.warning(self, "Error", "Failed to capture image.")
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ✅ Brightness check
        avg_brightness = gray.mean()
        if avg_brightness < 30:
            QMessageBox.warning(self, "⚠️ Low Light", "Photo is too dark. Try again in better lighting.")
            return

        # ✅ Contrast check
        std_dev = gray.std()
        if std_dev < 10:
            QMessageBox.warning(self, "⚠️ Invalid Photo", "Image appears blank. Please retake.")
            return

        # ✅ Detect face
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

        if len(faces) == 0:
            QMessageBox.warning(self, "⚠️ No Face Detected", "Please ensure your face is inside the frame.")
            return

        # ✅ Save captured frame
        self.captured_frame = frame
        self.status_label.setText("✅ Photo Captured!")

        # ✅ Close the webcam and open preview
        self.timer.stop()
        self.cap.release()
        QMessageBox.information(self, "Success", "Photo captured successfully!")
        self.close()

    def closeEvent(self, event):
        """Ensure the camera is released properly when window is closed."""
        self.timer.stop()
        if self.cap.isOpened():
            self.cap.release()
        event.accept()
