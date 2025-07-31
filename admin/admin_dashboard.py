from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QStackedWidget, QApplication, QGraphicsOpacityEffect
from PyQt5.QtCore import QTimer, QEvent, Qt, QPropertyAnimation, QEasingCurve, QSize, QRect, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath
from admin.home import HomeWindow
from admin.login_window import LoginWindow
from admin.sidebar import Sidebar
from admin.register_student import RegisterStudentWindow
from admin.view_attendance import ViewAttendanceWindow
from admin.start_attendance_window import StartAttendanceWindow
from admin.review_unknown_window import ReviewUnknownFacesWindow
from admin.settings_window import SettingsWindow
from admin.theme_transition_overlay import ThemeTransitionOverlay
from admin.academic_resources.academic_resource_manager import AcademicResourceManager
from styles.theme_manager import ThemeManager  # Updated import path from styles folder
import time as system_time
import os
import math
import sqlite3
from config.utils_constants import DATABASE_PATH


class AdminDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Admin Dashboard")
        self.setGeometry(100, 100, 1000, 650)  # ✅ Slightly larger for better UI

        # Initialize theme manager before applying styles
        self.theme_manager = ThemeManager(QApplication.instance(), DATABASE_PATH)
        QApplication.instance().setProperty("theme_manager", self.theme_manager)
        
        # Connect to the theme_changed signal
        self.theme_manager.theme_changed.connect(self.update_theme)
        
        # Apply theme from settings
        self.theme_manager.load_theme_from_settings()

        self.theme_overlay = ThemeTransitionOverlay(self)

        # Install event filter for activity tracking
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
        self.init_windows()

        # ✅ Add all windows to stacked widget
        for window in self.windows.values():
            self.content_area.addWidget(window)
        
        self.content_area.setCurrentWidget(self.windows["home"])

        # ✅ Connect Sidebar Buttons to Sections
        self.connect_sidebar_buttons()

        # 🔹 **Inactivity Tracking**
        self.last_activity_time = system_time.time()
        self.logout_timer = QTimer(self)
        self.logout_timer.timeout.connect(self.check_inactivity)
        self.logout_timer.start(10000)  # Check every 10 sec

    def init_windows(self):
        """Initialize all window components"""
        self.windows = {
            "home": HomeWindow(parent=self),  # ✅ Pass parent for proper theme handling
            "register": RegisterStudentWindow(),
            "attendance": ViewAttendanceWindow(),
            "start_attendance": StartAttendanceWindow(),
            "review_unknown": ReviewUnknownFacesWindow(),
            "settings": SettingsWindow(parent=self),
            "academic_resource_manager" : AcademicResourceManager()
        }
        
        # Update each window's stylesheet
        for window in self.windows.values():
            window.setStyleSheet(QApplication.instance().styleSheet())
            window.installEventFilter(self)

    def connect_sidebar_buttons(self):
        """Connect sidebar buttons to window switching functionality"""
        # Use dictionary attribute naming for cleaner access
        button_mappings = {
            "home": self.sidebar.sidebar_buttons.get("home"),
            "register": self.sidebar.sidebar_buttons.get("register"),
            "attendance": self.sidebar.sidebar_buttons.get("attendance"),
            "start_attendance": self.sidebar.sidebar_buttons.get("start_attendance"),
            "review_unknown": self.sidebar.sidebar_buttons.get("review_unknown"),
            "settings": self.sidebar.sidebar_buttons.get("settings"),
            "academic_resource_manager": self.sidebar.sidebar_buttons.get("academic_resource_manager")
        }
        
        # Connect buttons to switch_window function
        for window_name, button in button_mappings.items():
            if button:
                button.clicked.connect(lambda checked=False, name=window_name: self.switch_window(name))
            else:
                print(f"⚠️ Button for {window_name} not found in sidebar!")

    def switch_window(self, window_name):
        """Switches to the selected window in the main content area and ensures visibility."""
        if window_name in self.windows:
            print(f"🔄 Switching to window: {window_name}")
            self.content_area.setCurrentWidget(self.windows[window_name])
            self.windows[window_name].show()  # ✅ Force visibility
            
            # Update active window in sidebar
            self.sidebar.set_active_window(window_name)
        else:
            print(f"⚠️ Window '{window_name}' not found!")

    def eventFilter(self, obj, event):
        """Detect mouse movement or keyboard activity to reset inactivity timer."""
        if event.type() in [QEvent.MouseMove, QEvent.KeyPress, QEvent.Wheel, 
                            QEvent.MouseButtonPress, QEvent.MouseButtonRelease]:
            self.reset_activity_timer()
        return super().eventFilter(obj, event)
    


    def check_inactivity(self):
        """Automatically logs out the admin after inactivity."""
        elapsed_time = system_time.time() - self.last_activity_time
        # Only log every 30 seconds to reduce console spam
        if int(elapsed_time) % 30 == 0:
            print(f"⏳ Inactive for {elapsed_time:.2f}s / Auto logout at: {self.auto_logout_time}s")
        if elapsed_time > self.auto_logout_time:
            print("🚪 Auto Logout due to inactivity.")
            self.logout()

    def logout(self):
        """Logs out and returns to the login screen."""
        print("🚪 Logging out...")
        
        # Stop the logout timer
        self.logout_timer.stop()
        
        # Close all windows in the dashboard
        for window in self.windows.values():
            window.close()
        
        # Close the admin dashboard
        self.close()
        
        # Open login window
        self.login_window = LoginWindow()
        self.login_window.show()

    def reset_activity_timer(self):
        """Resets the inactivity timer on user activity."""
        self.last_activity_time = system_time.time()

    def load_settings(self):
        """Loads settings from the database."""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT setting_key, setting_value FROM settings")
        settings = dict(cursor.fetchall())
        conn.close()
        return settings
        
    def update_theme(self):
        """Updates theme based on current settings with improved visual feedback"""
        print("🔄 Theme change requested - updating all windows...")
        
        # Get current theme before changes
        current_theme = self.theme_manager.get_current_theme_name()
        target_theme = "Dark" if current_theme == "dark" else "Light"
        
        # Show the transition overlay
        self.theme_overlay.resize(self.size())
        self.theme_overlay.move(
            (self.width() - self.theme_overlay.width()) // 2,
            (self.height() - self.theme_overlay.height()) // 2
        )
        self.theme_overlay.show_with_message(
            f"Switching to {target_theme} Theme",
            "Updating all components..."
        )
        self.theme_overlay.raise_()
        QApplication.processEvents()
        
        
        # Start progress updates
        progress_timer = QTimer(self)
        progress_index = [0]
        window_count = len(self.windows)

        def update_progress():
            if progress_index[0] < window_count:
                window_name = list(self.windows.keys())[progress_index[0]]
                self.theme_overlay.sub_message_label.setText(f"Updating {window_name} window...")
                progress_index[0] += 1
        
        progress_timer.timeout.connect(update_progress)
        progress_timer.start(150)
        
        try:
            # Update settings cache
            self.settings = self.load_settings()
            
            # Update auto-logout time if needed
            self.auto_logout_time = int(self.settings.get("admin_auto_logout_time", "10")) * 60
            
            # Apply theme to all windows and force repaint
            for window_name, window in self.windows.items():
                print(f"  → Updating theme for window: {window_name}")
                self.theme_overlay.sub_message_label.setText(f"Updating {window_name} window...")
                QApplication.processEvents()
                
                window.setStyleSheet(QApplication.instance().styleSheet())
                
                # Deep style refresh on window and all children
                self._refresh_widget_style(window)
            
            # Apply to sidebar
            print("  → Updating theme for sidebar")
            self.theme_overlay.sub_message_label.setText("Updating sidebar...")
            QApplication.processEvents()
            self._refresh_widget_style(self.sidebar)
            
            # Apply to main window 
            print("  → Updating theme for main window")
            self.theme_overlay.sub_message_label.setText("Finalizing theme update...")
            QApplication.processEvents()
            self.setStyleSheet(QApplication.instance().styleSheet())
            self._refresh_widget_style(self.content_area)
            self._refresh_widget_style(self)
            
            print("✅ Theme updated across all application components")
        finally:
            # Stop the progress timer
            progress_timer.stop()
            
            # Change message to success message
            self.theme_overlay.show_with_message(
                f"{target_theme} Theme Applied",
                "Theme update completed successfully"
            )
            QApplication.processEvents()
            
            # Hide overlay after a brief delay
            QTimer.singleShot(800, self.theme_overlay.hide)

    def resizeEvent(self, event):
        """Handle resize events to update overlay position"""
        if hasattr(self, 'theme_overlay'):
            # Center the overlay in the window
            self.theme_overlay.move(
                (self.width() - self.theme_overlay.width()) // 2,
                (self.height() - self.theme_overlay.height()) // 2
            )
        super().resizeEvent(event)

    def _refresh_widget_style(self, widget):
        
        if widget is None:
            return
            
        # Apply the current application stylesheet
        if hasattr(widget, 'setStyleSheet'):
            widget.setStyleSheet(QApplication.instance().styleSheet())
        
        # Force the widget to re-read its style
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
        
        # Process all direct children
        for child in widget.findChildren(QWidget, '', Qt.FindDirectChildrenOnly):
            self._refresh_widget_style(child)

    
    def closeEvent(self, event):
        """Handle proper cleanup on window close"""
        # Stop the logout timer
        self.logout_timer.stop()
        
        # Properly dispose of any resources
        for window in self.windows.values():
            window.close()
            
        event.accept()