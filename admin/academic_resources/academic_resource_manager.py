import sys
import sqlite3
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QApplication, 
                           QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                           QDialog, QMessageBox, QTabWidget, QScrollArea,
                           QGridLayout, QFrame, QSizePolicy, QSpacerItem,
                           QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QTimer, QRect
from PyQt5.QtGui import QIcon, QFont, QColor, QPainter, QBrush, QPen, QLinearGradient, QPixmap
from config.utils_constants import DATABASE_PATH
from admin.academic_resources.student_manager import StudentManager
from admin.academic_resources.get_stats import DashboardStatsManager
from admin.academic_resources.class_manager import ClassManager
from admin.academic_resources.session_manager import SessionManager
from admin.academic_resources.instructor_manager import InstructorManager
from admin.academic_resources.manage_courses import CourseManager


class DashboardCard(QFrame):
    def __init__(self, title, icon, description, stats=None, color="#4e73df", card_type="default", parent=None):
        super().__init__(parent)
        # Set unique object name based on card type
        self.setObjectName(f"Card{card_type}")
        self.color = color
        self.hovered = False
        
        # Create shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        # Make card clickable
        self.setCursor(Qt.PointingHandCursor)
        
        # Layout for card
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Icon and title in horizontal layout
        header_layout = QHBoxLayout()
        
        icon_label = QLabel()
        icon_label.setText(icon)
        icon_label.setObjectName(f"CardIcon{card_type}")
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setObjectName(f"CardTitle{card_type}")
        title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setObjectName(f"CardDescription{card_type}")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Stats section
        if stats:
            stats_layout = QHBoxLayout()
            stats_label = QLabel(stats)
            stats_label.setObjectName(f"CardStats{card_type}")
            stats_layout.addWidget(stats_label)
            stats_layout.addStretch()
            
            layout.addSpacerItem(QSpacerItem(20, 10))
            layout.addLayout(stats_layout)
        
        self.setLayout(layout)
        self.setMinimumHeight(180)
        self.setMinimumWidth(300)
    
    def enterEvent(self, event):
        self.hovered = True
        self.update()
        QTimer.singleShot(20, self.animate_hover)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        QTimer.singleShot(20, self.animate_hover)
        super().leaveEvent(event)
    
    def animate_hover(self):
        effect = self.graphicsEffect()
        if self.hovered:
            effect.setBlurRadius(30)
            effect.setColor(QColor(0, 0, 0, 90))
            effect.setOffset(0, 6)
        else:
            effect.setBlurRadius(20)
            effect.setColor(QColor(0, 0, 0, 60))
            effect.setOffset(0, 4)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hovered:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            
            gradient = QLinearGradient(0, 0, self.width(), 0)
            color = QColor(self.color)
            gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 30))
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 5))
            
            painter.setBrush(gradient)
            painter.drawRoundedRect(0, 0, self.width(), self.height(), 12, 12)



class AnimatedButton(QPushButton):
    def __init__(self, text, icon="", color="#4e73df", button_type="default", parent=None):
        super().__init__(parent)
        self.setText(text)
        # Set unique object name for buttons
        self.setObjectName(f"ActionButton{button_type}")
        self.base_color = color
        self.hover_color = self.adjust_color(color, -30)  # Darker for hover
        
        if icon:
            self.setIcon(QIcon(icon))
            
        # Style constants
        self.border_radius = 10
        self.padding_horizontal = 120
        self.padding_vertical = 100
        self.font_size = 14

    def adjust_color(self, color, amount):
        # Helper to darken/lighten color
        c = QColor(color)
        r, g, b = c.red(), c.green(), c.blue()
        
        # Adjust the RGB values
        r = max(0, min(255, r + amount))
        g = max(0, min(255, g + amount))
        b = max(0, min(255, b + amount))
        
        # Create a new color with the adjusted values
        c.setRgb(r, g, b)
        return c.name()


class AcademicResourceManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎓 Academic Resources")
        self.setGeometry(100, 100, 1200, 800)
        
        self.setObjectName("AcademicResourceApp")
        
        
        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
               
        # Create main content area
        self.content_widget = QWidget()
        self.content_widget.setObjectName("ContentWidget")
        
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        # Content scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("AcademicScrollArea")
        scroll_area.setWidget(self.content_widget)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll_area, 4)
        
        # Initialize managers
        self.course_manager = CourseManager()
        self.instructor_manager = InstructorManager()
        self.schedule_manager = ClassManager()
        self.sessions_manager = SessionManager()
        self.student_manager = StudentManager()
        
        # Create dashboard cards
        self.create_dashboard()
        
        # Set initial animation delay
        QTimer.singleShot(100, self.animate_dashboard)
    
    
    def create_dashboard(self):
        # Dashboard container
        self.dashboard = QWidget()
        dashboard_layout = QVBoxLayout(self.dashboard)
        dashboard_layout.setContentsMargins(30, 30, 30, 30)
        dashboard_layout.setSpacing(20)
        
        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        
        welcome_label = QLabel("Welcome to Academic Dashboard")
        welcome_label.setObjectName("WelcomeLabel")
        header_layout.addWidget(welcome_label)
        
        date_label = QLabel(DashboardStatsManager.get_current_date())
        date_label.setObjectName("DateLabel")
        date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_layout.addWidget(date_label)
        
        dashboard_layout.addWidget(header)
        
        # Summary cards
        summary_container = QWidget()
        summary_layout = QHBoxLayout(summary_container)
        summary_layout.setSpacing(20)
        
        # Card 1 - Courses
        course_card = DashboardCard(
            "Courses", "📚", 
            "Manage academic course catalog and curriculum",
            DashboardStatsManager.get_course_stats(), "#4e73df",
            card_type="Course"  # Unique identifier for course card
        )
        course_card.mousePressEvent = lambda e: self.show_manager(self.course_manager, "Courses")
        summary_layout.addWidget(course_card)
        
        # Card 2 - Instructors
        instructor_card = DashboardCard(
            "Instructors", "👨‍🏫", 
            "Faculty management and assignments",
            DashboardStatsManager.get_instructor_stats(), "#1cc88a",
            card_type="Instructor"  # Unique identifier for instructor card
        )
        instructor_card.mousePressEvent = lambda e: self.show_manager(self.instructor_manager, "Instructors")
        summary_layout.addWidget(instructor_card)
        
        # Card 3 - Class Sessions
        session_card = DashboardCard(
            "Sessions", "🕓", 
            "Track class sessions and attendance records",
            DashboardStatsManager.get_sessions_stats(), "#f6c23e",
            card_type="Session"  # Unique identifier for session card
        )
        session_card.mousePressEvent = lambda e: self.show_manager(self.sessions_manager, "Sessions")
        summary_layout.addWidget(session_card)
        
        dashboard_layout.addWidget(summary_container)
        
        # Second row of cards - Assignments and Schedule
        row2_container = QWidget()
        row2_layout = QHBoxLayout(row2_container)
        row2_layout.setSpacing(20)
        
        # Card 5 - Schedule
        schedule_card = DashboardCard(
            "Class Schedule", "📅", 
            "Time table management and classroom scheduling",
            DashboardStatsManager.get_schedule_stats(), "#e74a3b",
            card_type="Schedule"  # Unique identifier for schedule card
        )
        schedule_card.mousePressEvent = lambda e: self.show_manager(self.schedule_manager, "Class Schedule")
        row2_layout.addWidget(schedule_card)
        
        dashboard_layout.addWidget(row2_container)

        student_card = DashboardCard(
            "Students", "👨‍🎓", 
            "View and filter student information by course and year",
            DashboardStatsManager.get_student_stats(), "#36b9cc",
            card_type="Student"  # Unique identifier for student card
        )
        student_card.mousePressEvent = lambda e: self.show_manager(self.student_manager, "Students")
        row2_layout.addWidget(student_card)
        
        # Quick actions section
        actions_section = QWidget()
        actions_layout = QVBoxLayout(actions_section)
        
        actions_header = QLabel("Quick Actions")
        actions_header.setObjectName("ActionsHeader")
        actions_layout.addWidget(actions_header)
        
        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setSpacing(15)
        
        add_course_btn = AnimatedButton("Add New Course", color="#4e73df", button_type="Course")
        add_course_btn.clicked.connect(lambda: self.show_manager(self.course_manager, "Courses"))
        buttons_layout.addWidget(add_course_btn)
        
        add_instructor_btn = AnimatedButton("Add Instructor", color="#1cc88a", button_type="Instructor")
        add_instructor_btn.clicked.connect(lambda: self.show_manager(self.instructor_manager, "Instructors"))
        buttons_layout.addWidget(add_instructor_btn)
        
        schedule_class_btn = AnimatedButton("Schedule Class", color="#f6c23e", button_type="Schedule")
        schedule_class_btn.clicked.connect(lambda: self.show_manager(self.schedule_manager, "Class Schedule"))
        buttons_layout.addWidget(schedule_class_btn)
        
        buttons_layout.addStretch()
        
        actions_layout.addWidget(buttons_container)
        dashboard_layout.addWidget(actions_section)
        
        # Add spacer at the bottom
        dashboard_layout.addStretch()
        
        # Add dashboard to content
        self.content_layout.addWidget(self.dashboard)
        
        # Hide the cards initially for animation
        for i in range(summary_layout.count()):
            card = summary_layout.itemAt(i).widget()
            card.setVisible(False)
        
        for i in range(row2_layout.count()):
            card = row2_layout.itemAt(i).widget()
            card.setVisible(False)
    
    def animate_dashboard(self):
        # Find the card containers by looking at the dashboard layout
        dashboard_layout = self.dashboard.layout()
        
        # Make sure we have at least 3 items in the layout (header, first row, second row)
        if dashboard_layout.count() >= 3:
            # The summary container should be the second item (index 1)
            summary_container = dashboard_layout.itemAt(1).widget()
            if summary_container and summary_container.layout():
                summary_layout = summary_container.layout()
                
                # First row animation
                for i in range(summary_layout.count()):
                    card = summary_layout.itemAt(i).widget()
                    QTimer.singleShot(i * 150, lambda c=card: self.fade_in_card(c))
            
            # The row2 container should be the third item (index 2)
            row2_container = dashboard_layout.itemAt(2).widget()
            if row2_container and row2_container.layout():
                row2_layout = row2_container.layout()
                
                # Second row animation (delayed)
                for i in range(row2_layout.count()):
                    card = row2_layout.itemAt(i).widget()
                    QTimer.singleShot((i + (summary_layout.count() if 'summary_layout' in locals() else 0)) * 150, 
                                    lambda c=card: self.fade_in_card(c))    
    def fade_in_card(self, card):
        card.setVisible(True)
        effect = QGraphicsDropShadowEffect(card)
        effect.setBlurRadius(0)
        effect.setColor(QColor(0, 0, 0, 0))
        effect.setOffset(0, 0)
        card.setGraphicsEffect(effect)
        
        # Animate shadow
        for i in range(21):
            QTimer.singleShot(i*10, lambda i=i, e=effect: self.update_shadow(e, i))
    
    def update_shadow(self, effect, step):
        effect.setBlurRadius(step)
        effect.setColor(QColor(0, 0, 0, step*3))
        effect.setOffset(0, step/5)
    
    def show_dashboard(self):
        # Hide all managers
        self.course_manager.hide()
        self.instructor_manager.hide()
        self.schedule_manager.hide()
        self.sessions_manager.hide()
        self.student_manager.hide()
        
        # Clear any existing content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
        
        # Show dashboard
        self.dashboard.show()
        self.content_layout.addWidget(self.dashboard)
        
        # Re-animate dashboard
        self.animate_dashboard()
    
    def show_manager(self, manager, title):
        # Hide all managers and the dashboard
        self.dashboard.hide()
        self.course_manager.hide()
        self.instructor_manager.hide()
        self.schedule_manager.hide()
        self.sessions_manager.hide()
        self.student_manager.hide()
        
        # Clear existing content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
        
        # Create header bar
        header_bar = QWidget()
        header_bar.setObjectName("HeaderBar")
        
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(15, 15, 15, 15)
        
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        header_layout.addWidget(title_label)
        
        back_btn = AnimatedButton("Back to Dashboard", color="#4e73df", button_type="Back")
        back_btn.setMaximumWidth(300)
        back_btn.clicked.connect(self.show_dashboard)
        header_layout.addWidget(back_btn)
        
        # Add header and manager to content
        self.content_layout.addWidget(header_bar)
        
        # Create content container with padding
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(30, 30, 30, 30)
        container_layout.addWidget(manager)
        
        self.content_layout.addWidget(container)
        
        # Show the manager
        manager.show()