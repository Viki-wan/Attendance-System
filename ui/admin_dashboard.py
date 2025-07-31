from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QApplication
from PyQt5.QtCore import QTimer, QEvent
from ui.home import HomeWindow
from ui.login_window import LoginWindow
from ui.sidebar import Sidebar
from ui.register_student import RegisterStudentWindow
from ui.view_attendance import ViewAttendanceWindow
from ui.start_attendance_window import StartAttendanceWindow
from ui.review_unknown_window import ReviewUnknownFacesWindow
from ui.settings_window import SettingsWindow
import time as system_time
import os
import sqlite3

class AdminDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Admin Dashboard")
        self.setGeometry(100, 100, 1000, 650)  # ✅ Slightly larger for better UI

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS

        
        self.installEventFilter(self)

        # ✅ Load settings
        self.settings = self.load_settings()
        self.auto_logout_time = int(self.settings.get("admin_auto_logout_time", "10")) * 60

        # 🔹 **Central Widget & Layout**
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QHBoxLayout()
        central_widget.setLayout(self.layout)

        self.content_area = QStackedWidget() 

        # 🔹 **Sidebar**
        self.sidebar = Sidebar(self, self.content_area)
        self.layout.addWidget(self.sidebar)
        self.layout.addWidget(self.content_area)

        # 🔹 **Windows (Lazy Loading)**
        self.windows = {
            "home": HomeWindow(),  # ✅ Load home page first
            "register": RegisterStudentWindow(),
            "attendance": ViewAttendanceWindow(),
            "start_attendance": StartAttendanceWindow(),
            "review_unknown": ReviewUnknownFacesWindow(),
            "settings": SettingsWindow(),
        }

        # ✅ Add all windows to stacked widget
        for window in self.windows.values():
            self.content_area.addWidget(window)
        
        self.content_area.setCurrentWidget(self.windows["home"])


        # ✅ Connect Sidebar Buttons to Sections
        self.sidebar.register_student_button.clicked.connect(lambda: self.switch_window("register"))
        self.sidebar.view_attendance_button.clicked.connect(lambda: self.switch_window("attendance"))
        self.sidebar.start_attendance_button.clicked.connect(lambda: self.switch_window("start_attendance"))
        self.sidebar.review_unknown_button.clicked.connect(lambda: self.switch_window("review_unknown"))
        self.sidebar.settings_button.clicked.connect(lambda: self.switch_window("settings"))

        self.apply_stylesheet()

        # 🔹 **Inactivity Tracking**
        self.last_activity_time = system_time.time()
        self.logout_timer = QTimer(self)
        self.logout_timer.timeout.connect(self.check_inactivity)
        self.logout_timer.start(10000)  # Check every 10 sec
        self.installEventFilter(self)

    def apply_stylesheet(self):
        """Loads the QSS stylesheet globally and applies it."""
        try:
            with open("styles/style.qss", "r", encoding="utf-8") as file:
                stylesheet = file.read()
                self.setStyleSheet(stylesheet)
                print("✅ Stylesheet applied successfully!")
        except FileNotFoundError:
            print("⚠️ Stylesheet not found. Running without custom styles.")


    def switch_window(self, window_name):
        """Switches to the selected window in the main content area and ensures visibility."""
        if window_name in self.windows:
            print(f"🔄 Switching to window: {window_name}")
            self.content_area.setCurrentWidget(self.windows[window_name])
            self.windows[window_name].show()  # ✅ Force visibility
        else:
            print(f"⚠️ Window '{window_name}' not found!")


    def eventFilter(self, obj, event):
        """Detect mouse movement or keyboard activity to reset inactivity timer."""
        if event.type() in [QEvent.MouseMove, QEvent.KeyPress, QEvent.Wheel]:
            self.reset_activity_timer()
        return super().eventFilter(obj, event)


    def check_inactivity(self):
        """Automatically logs out the admin after inactivity."""
        elapsed_time = system_time.time() - self.last_activity_time
        print(f"⏳ Inactive for {elapsed_time:.2f}s / Auto logout at: {self.auto_logout_time}s")
        if elapsed_time > self.auto_logout_time:
            print("🚪 Auto Logout due to inactivity.")
            self.logout()

    def logout(self):
        """Logs out and returns to the login screen."""
        self.logout_timer.stop()
        self.close()
        self.login_window = LoginWindow()
        self.login_window.show()

    def reset_activity_timer(self):
        """Resets the inactivity timer on user activity."""
        self.last_activity_time = system_time.time()
        print(f"🔄 Activity detected! Timer reset at {self.last_activity_time}")


    def load_settings(self):
        """Loads settings from the database."""
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        cursor.execute("SELECT setting_key, setting_value FROM settings")
        settings = dict(cursor.fetchall())
        conn.close()
        return settings
