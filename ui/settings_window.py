import sqlite3
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QCheckBox, QSpinBox, QTabWidget, QApplication, QFormLayout, QSlider, QMessageBox
)
from PyQt5.QtCore import Qt
from config.utils_constants import DATABASE_PATH
from PyQt5.QtGui import QFont

class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚙️ System Settings")
        self.setGeometry(400, 200, 500, 450)

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS

        self.tabs = QTabWidget()
        self.general_tab = QWidget()
        self.face_recognition_tab = QWidget()

        self.tabs.addTab(self.general_tab, "General")
        self.tabs.addTab(self.face_recognition_tab, "Face Recognition")

        self.init_general_tab()
        self.init_face_recognition_tab()

        layout = QVBoxLayout()
        layout.addWidget(self.tabs)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.load_settings()  # Load settings from DB

    # -------------------- General Settings --------------------
    def init_general_tab(self):
        """Setup General Settings tab."""
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.auto_start_checkbox = QCheckBox("Start Attendance Automatically")
        form_layout.addRow("🔄 Auto-Start Attendance:", self.auto_start_checkbox)

        self.dark_mode_checkbox = QCheckBox("Enable Dark Mode")
        form_layout.addRow("🌙 Dark Mode:", self.dark_mode_checkbox)

        self.auto_logout_time_input = QSpinBox()
        self.auto_logout_time_input.setRange(1, 60)  # 1 to 60 minutes
        self.auto_logout_time_input.setSuffix(" min")
        form_layout.addRow("⏳ Admin Auto-Logout Time:", self.auto_logout_time_input)

        layout.addLayout(form_layout)

        # 🔹 Instant Dark Mode Button
        self.toggle_dark_mode_button = QPushButton("Toggle Dark Mode")
        self.toggle_dark_mode_button.clicked.connect(self.toggle_dark_mode)
        layout.addWidget(self.toggle_dark_mode_button)

        # ✅ Save & Reset Buttons
        btn_layout = QHBoxLayout()
        self.save_button = QPushButton("💾 Save")
        self.save_button.clicked.connect(self.save_settings)
        self.reset_button = QPushButton("🔄 Reset")
        self.reset_button.clicked.connect(self.load_settings)
        btn_layout.addWidget(self.save_button)
        btn_layout.addWidget(self.reset_button)
        layout.addLayout(btn_layout)

        self.general_tab.setLayout(layout)

    # -------------------- Face Recognition Settings --------------------
    def init_face_recognition_tab(self):
        """Setup Face Recognition Settings tab."""
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.recognition_tolerance = QSpinBox()
        self.recognition_tolerance.setRange(10, 100)  # 10% to 100%
        self.recognition_tolerance.setSuffix("%")
        form_layout.addRow(QLabel("🔍 Recognition Tolerance:"), self.recognition_tolerance)

        self.steady_frame_threshold = QSpinBox()
        self.steady_frame_threshold.setRange(1, 10)
        form_layout.addRow(QLabel("📷 Steady Frame Threshold:"), self.steady_frame_threshold)

        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(1, 100)
        form_layout.addRow(QLabel("⚡ Face Recognition Sensitivity:"), self.sensitivity_slider)

        self.required_matches_input = QSpinBox()
        self.required_matches_input.setRange(1, 10)
        form_layout.addRow(QLabel("✅ Required Matches for Attendance:"), self.required_matches_input)

        # ✅ Save Unknown Faces Option
        self.save_unknown_faces_checkbox = QCheckBox("📸 Save Unknown Faces")
        form_layout.addRow(QLabel("Save Faces:"), self.save_unknown_faces_checkbox)

        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        self.save_button2 = QPushButton("💾 Save")
        self.save_button2.clicked.connect(self.save_settings)
        self.reset_button2 = QPushButton("🔄 Reset")
        self.reset_button2.clicked.connect(self.load_settings)
        btn_layout.addWidget(self.save_button2)
        btn_layout.addWidget(self.reset_button2)
        layout.addLayout(btn_layout)

        self.face_recognition_tab.setLayout(layout)

    # -------------------- Load & Save Settings --------------------
    def load_settings(self):
        """Load settings from the database."""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT setting_key, setting_value FROM settings")
        settings = dict(cursor.fetchall())
        conn.close()

        self.auto_start_checkbox.setChecked(settings.get("auto_start", "0") == "1")
        self.dark_mode_checkbox.setChecked(settings.get("dark_mode", "0") == "1")
        self.auto_logout_time_input.setValue(int(settings.get("admin_auto_logout_time", "10")))
        self.recognition_tolerance.setValue(int(settings.get("recognition_tolerance", "45")))
        self.steady_frame_threshold.setValue(int(settings.get("steady_frame_threshold", "3")))
        self.sensitivity_slider.setValue(int(settings.get("face_recognition_sensitivity", "50")))
        self.required_matches_input.setValue(int(settings.get("required_matches", "3")))
        self.save_unknown_faces_checkbox.setChecked(settings.get("save_unknown_faces", "0") == "1")

    def save_settings(self):
        """Save updated settings to the database."""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        settings = {
            "auto_start": "1" if self.auto_start_checkbox.isChecked() else "0",
            "dark_mode": "1" if self.dark_mode_checkbox.isChecked() else "0",
            "admin_auto_logout_time": str(self.auto_logout_time_input.value()),
            "recognition_tolerance": str(self.recognition_tolerance.value()),
            "steady_frame_threshold": str(self.steady_frame_threshold.value()),
            "face_recognition_sensitivity": str(self.sensitivity_slider.value()),
            "required_matches": str(self.required_matches_input.value()),
            "save_unknown_faces": "1" if self.save_unknown_faces_checkbox.isChecked() else "0",
        }

        for key, value in settings.items():
            cursor.execute("""
                INSERT INTO settings (setting_key, setting_value) 
                VALUES (?, ?) ON CONFLICT(setting_key) DO UPDATE SET setting_value = ?
            """, (key, value, value))

        conn.commit()
        conn.close()

        QMessageBox.information(self, "Success", "Settings saved successfully.")

    # -------------------- Dark Mode Toggle --------------------
    def toggle_dark_mode(self):
        """Toggle dark mode and save the setting to the database."""
        dark_mode_enabled = not self.dark_mode_checkbox.isChecked()
        self.dark_mode_checkbox.setChecked(dark_mode_enabled)
        self.apply_dark_mode()

    def apply_dark_mode(self):
        """Apply dark mode immediately based on the checkbox state."""
        dark_mode_enabled = self.dark_mode_checkbox.isChecked()
        if dark_mode_enabled:
            self.setStyleSheet("background-color: #121212; color: white;")
        else:
            self.setStyleSheet("")

        self.save_settings()  # Ensure the setting is saved

