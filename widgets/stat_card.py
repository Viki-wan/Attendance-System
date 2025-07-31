from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap, QFont, QColor

class StatCard(QFrame):
    """
    A styled card widget displaying a statistic with title, value, and optional icon.
    
    This widget creates cards for the dashboard to highlight key metrics in an
    easy-to-read format with visual styling.
    """
    
    def __init__(self, title, value, icon_name="", color="#3498db"):
        super().__init__()
        self.title = title
        self.value = value
        self.icon_name = icon_name
        self.color = color
        
        # Initialize UI
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI components"""
        # Set frame styling
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setObjectName("statCard")
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        # Apply custom styling
        self.setStyleSheet(f"""
            QFrame#statCard {{
                background-color: white;
                border: none;
                border-left: 5px solid {self.color};
                border-radius: 4px;
                padding: 10px;
                margin: 5px;
            }}
        """)
        
        # Create layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Add icon if provided
        if self.icon_name:
            self.icon_label = QLabel()
            self.load_icon(self.icon_name)
            self.icon_label.setFixedSize(40, 40)
            self.icon_label.setStyleSheet(f"color: {self.color};")
            main_layout.addWidget(self.icon_label)
            
        # Container for text content
        text_container = QVBoxLayout()
        
        # Title label
        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet("""
            font-size: 12pt;
            color: #7f8c8d;
        """)
        text_container.addWidget(self.title_label)
        
        # Value label
        self.value_label = QLabel(self.value)
        self.value_label.setStyleSheet(f"""
            font-size: 18pt;
            font-weight: bold;
            color: {self.color};
        """)
        text_container.addWidget(self.value_label)
        
        main_layout.addLayout(text_container)
        main_layout.setStretch(1, 1)  # Make text container take available space
        
    def set_value(self, value):
        """
        Update the displayed value
        
        Args:
            value (str): New value to display
        """
        self.value = value
        self.value_label.setText(value)
        
    def set_title(self, title):
        """
        Update the card title
        
        Args:
            title (str): New title to display
        """
        self.title = title
        self.title_label.setText(title)
        
    def set_color(self, color):
        """
        Update the card accent color
        
        Args:
            color (str): New hex color code
        """
        self.color = color
        self.setStyleSheet(f"""
            QFrame#statCard {{
                background-color: white;
                border: none;
                border-left: 5px solid {self.color};
                border-radius: 4px;
                padding: 10px;
                margin: 5px;
            }}
        """)
        self.value_label.setStyleSheet(f"""
            font-size: 18pt;
            font-weight: bold;
            color: {self.color};
        """)
        
    def load_icon(self, icon_name):
        """
        Load an icon using a predefined name
        
        Args:
            icon_name (str): Name of the icon to load
        """
        # Map icon names to appropriate resource paths
        icon_map = {
            "courses-icon": ":/icons/courses.png",
            "students-icon": ":/icons/students.png",
            "attendance-icon": ":/icons/attendance.png",
            "trophy-icon": ":/icons/trophy.png",
            "alert-icon": ":/icons/alert.png",
            "average-icon": ":/icons/average.png",
            "calendar-icon": ":/icons/calendar.png",
            "time-icon": ":/icons/time.png",
            "instructor-icon": ":/icons/instructor.png",
            "trend-up-icon": ":/icons/trend_up.png",
            "trend-down-icon": ":/icons/trend_down.png"
        }
        
        # If icon is in the map, load it
        if icon_name in icon_map:
            path = icon_map[icon_name]
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.icon_label.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        
        # Fallback - use a colored box as placeholder
        self.icon_label.setText("")
        self.icon_label.setStyleSheet(f"""
            background-color: {self.color};
            border-radius: 5px;
        """)