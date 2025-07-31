from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QApplication, QSizePolicy
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation
from PyQt5.QtGui import QIcon


class Sidebar(QWidget):
    def __init__(self, parent, content_area):
        super().__init__(parent)
        self.setFixedWidth(60)  # Start in collapsed mode
        self.setStyleSheet("background-color: #2C3E50; border-radius: 10px;")

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS


        self.parent = parent
        self.content_area = content_area  # ✅ Reference to stacked content area
        self.expanded = False  # Track sidebar state

        # Layout
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignTop)

        # 🔹 **Sidebar Buttons (Now Using `switch_window`)**
        self.home_button = self.create_sidebar_button("icons/home.png", "🏠 Home", lambda: parent.switch_window("home"))
        self.register_student_button = self.create_sidebar_button("icons/register.png", "📌 Register", lambda: parent.switch_window("register"))
        self.view_attendance_button = self.create_sidebar_button("icons/attendance.png", "📋 Attendance", lambda: parent.switch_window("attendance"))
        self.start_attendance_button = self.create_sidebar_button("icons/start.png", "📡 Start", lambda: parent.switch_window("start_attendance"))
        self.review_unknown_button = self.create_sidebar_button("icons/unknown.png", "❓ Unknown", lambda: parent.switch_window("review_unknown"))
        self.settings_button = self.create_sidebar_button("icons/settings.png", "⚙ Settings", lambda: parent.switch_window("settings"))

        # ✅ **Add Buttons to Layout**
        self.layout.addWidget(self.home_button)  # Add home button at the top
        self.layout.addWidget(self.register_student_button)
        self.layout.addWidget(self.view_attendance_button)
        self.layout.addWidget(self.start_attendance_button)
        self.layout.addWidget(self.review_unknown_button)
        self.layout.addWidget(self.settings_button)

        self.setLayout(self.layout)

        # 🔹 **Animation for Expanding & Collapsing**
        self.animation = QPropertyAnimation(self, b"maximumWidth")
        self.animation.setDuration(300)  # Smooth transition

        # Enable hover detection
        self.setMouseTracking(True)

    def create_sidebar_button(self, icon_path, label, callback):
        """Creates a sidebar button with an icon and text label."""
        button = QPushButton(f"{label}")  # Text only shown when expanded
        button.setIcon(QIcon(icon_path))
        button.setIconSize(QSize(24, 24))
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.setFixedHeight(50)
        button.setStyleSheet(self.get_button_style())
        button.clicked.connect(lambda: self.debug_click(callback, label))  # Debug Click Handling
        return button

    def debug_click(self, callback, label):
        """Prints debug info when a sidebar button is clicked and then executes the function."""
        print(f"✅ Sidebar button clicked: {label}")  # Debugging
        callback()  # Execute the original function

    def get_button_style(self):
        """Returns the stylesheet for sidebar buttons."""
        return """
            QPushButton {
                background-color: #34495E;
                color: white;
                font-size: 14px;
                border: none;
                padding: 10px;
                text-align: left;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1ABC9C;
            }
        """

    def enterEvent(self, event):
        """Expand the sidebar on hover"""
        self.animation.stop()
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(180)  # Expanded width
        self.animation.start()
        self.update_button_text(True)

    def leaveEvent(self, event):
        """Collapse the sidebar when not hovered"""
        self.animation.stop()
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(60)  # Collapsed width
        self.animation.start()
        self.update_button_text(False)

    def update_button_text(self, expanded):
        """Updates button text visibility based on sidebar state."""
        if expanded:
            self.home_button.setText("🏠 Home")
            self.register_student_button.setText("📌 Register")
            self.view_attendance_button.setText("📋 Attendance")
            self.start_attendance_button.setText("📡 Start")
            self.review_unknown_button.setText("❓ Unknown")
            self.settings_button.setText("⚙ Settings")
        else:
            self.home_button.setText("")
            self.register_student_button.setText("")
            self.view_attendance_button.setText("")
            self.start_attendance_button.setText("")
            self.review_unknown_button.setText("")
            self.settings_button.setText("")
