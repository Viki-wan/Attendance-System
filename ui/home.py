import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLineEdit, QFrame, QStackedWidget
)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QTimer, QDateTime



class HomeWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🏠 Admin Dashboard")
        self.setStyleSheet("background-color: #F5F7FA;")  # Light theme
        self.setContentsMargins(10, 10, 10, 10)

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS


        # 🔹 **Main Layout**
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)

        # ✅ **Page Stack (For Smooth Navigation)**
        self.page_stack = QStackedWidget()  

        # ✅ **Central Dashboard Area**
        self.content_area = QVBoxLayout()
        self.main_layout.addLayout(self.content_area)

        # 🔹 **Search Bar**
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search...")
        self.search_bar.setStyleSheet(
            "padding: 10px; font-size: 14px; border-radius: 8px; border: 1px solid #ddd;"
        )

        # 🔹 **Current Time Display**
        self.time_label = QLabel("🕒 12:00 PM")
        self.time_label.setFont(QFont("Arial", 14))
        self.time_label.setAlignment(Qt.AlignRight)

        # ✅ **Top Bar Layout**
        self.top_bar_layout = QHBoxLayout()
        self.top_bar_layout.addWidget(self.search_bar, 70)
        self.top_bar_layout.addWidget(self.time_label, 30)

        self.content_area.addLayout(self.top_bar_layout)

        # ✅ **Main Dashboard Widgets**
        self.init_dashboard_widgets()

        # ✅ **Right Sidebar (Quick Stats & Profile)**
        self.right_panel = self.create_right_panel()
        self.main_layout.addWidget(self.right_panel)

        # 🔹 **Update Time Every Second**
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)

    def init_dashboard_widgets(self):
        """Creates the core dashboard widgets."""
        # 🔹 **Upcoming Events**
        self.upcoming_events = self.create_card("📅 Upcoming Events", "No events scheduled.")
        
        # 🔹 **Pinned Shortcuts**
        self.pinned_shortcuts = self.create_card("📌 Pinned Shortcuts", "Add your frequently used features.")

        # 🔹 **Analytics Graph Placeholder**
        self.analytics_graph = self.create_card("📊 Attendance Analytics", "Graph will be displayed here.")

        # ✅ **Add to Page Stack**
        self.page_stack.addWidget(self.upcoming_events)
        self.page_stack.addWidget(self.pinned_shortcuts)
        self.page_stack.addWidget(self.analytics_graph)

        self.content_area.addWidget(self.page_stack)

    def apply_stylesheet(self):
        """Loads the QSS stylesheet and applies it to the home window."""
        try:
            with open("styles/style.qss", "r", encoding="utf-8") as file:
                self.setStyleSheet(file.read())
                print("✅ HomeWindow Stylesheet applied successfully!")
        except FileNotFoundError:
            print("⚠️ HomeWindow Stylesheet not found. Running without custom styles.")

    def create_card(self, title, text):
        """Creates a simple card UI for dashboard widgets."""
        card = QFrame()
        card.setStyleSheet(
            "background-color: white; border-radius: 10px; padding: 15px; border: 1px solid #ddd;"
        )

        layout = QVBoxLayout()
        label = QLabel(title)
        label.setFont(QFont("Arial", 14, QFont.Bold))
        label.setStyleSheet("color: #333;")
        content = QLabel(text)
        content.setStyleSheet("font-size: 12px; color: #555;")
        layout.addWidget(label)
        layout.addWidget(content)
        card.setLayout(layout)

        return card

    def create_right_panel(self):
        """Creates a right-side panel with admin profile and system stats."""
        panel = QFrame()
        panel.setFixedWidth(250)
        panel.setStyleSheet("background-color: #EAECEE; border-radius: 10px; padding: 10px;")

        layout = QVBoxLayout()

        # 🔹 **Admin Profile**
        profile_pic = QLabel()
        profile_pic.setPixmap(QPixmap("icons/admin_profile.png").scaled(80, 80, Qt.KeepAspectRatio))
        profile_pic.setAlignment(Qt.AlignCenter)
        
        admin_name = QLabel("Admin Name")
        admin_name.setFont(QFont("Arial", 12, QFont.Bold))
        admin_name.setAlignment(Qt.AlignCenter)

        # 🔹 **Quick Stats**
        total_students = QLabel("👥 Total Students: 100")
        total_students.setAlignment(Qt.AlignCenter)

        total_attendance = QLabel("📊 Attendance Records: 500")
        total_attendance.setAlignment(Qt.AlignCenter)

        logout_button = QPushButton("🚪 Logout")
        logout_button.setStyleSheet("background-color: #E74C3C; color: white; border-radius: 6px; padding: 8px;")
        logout_button.clicked.connect(self.logout)

        layout.addWidget(profile_pic)
        layout.addWidget(admin_name)
        layout.addWidget(total_students)
        layout.addWidget(total_attendance)
        layout.addWidget(logout_button)
        panel.setLayout(layout)

        return panel

    def update_time(self):
        """Updates the time in the top bar."""
        current_time = QDateTime.currentDateTime().toString("hh:mm AP")
        self.time_label.setText(f"🕒 {current_time}")

    def logout(self):
        """Handles logout action."""
        from ui.login_window import LoginWindow
        self.login_window = LoginWindow()
        self.login_window.show()
        self.parent().close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    home = HomeWindow()
    home.show()
    sys.exit(app.exec_())
