from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLayout,
    QFrame, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QParallelAnimationGroup, QPropertyAnimation, QAbstractAnimation
from PyQt5.QtGui import QIcon


class CollapsibleSection(QWidget):
    """
    A collapsible section widget that can be expanded or collapsed to show or hide content.
    Used for organizing UI elements in the attendance analytics dashboard.
    """
    
    # Signal emitted when section is expanded or collapsed
    toggled = pyqtSignal(bool)
    
    def __init__(self, title, expanded=False, parent=None):
        """
        Initialize the collapsible section with a title and initial state
        
        Args:
            title (str): The section title text
            expanded (bool): Whether the section is initially expanded
            parent (QWidget): Parent widget
        """
        super().__init__(parent)
        
        # Store initial state
        self.expanded = expanded
        self.title = title
        self.content_widget = None
        self.animation = None
        
        # Set up the UI
        self.init_ui()
        
    def init_ui(self):
        """Set up the UI components"""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Header frame with toggle button and title
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QFrame:hover {
                background-color: #e9e9e9;
            }
        """)
        
        # Header layout
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(10, 8, 10, 8)
        
        # Toggle button
        self.toggle_button = QPushButton()
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(self.expanded)
        
        # Set button style
        self.toggle_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                font-weight: bold;
                font-size: 16px;
                padding: 2px;
                width: 20px;
                height: 20px;
            }
        """)
        
        # Set button icons (can be replaced with themed icons or images)
        self.toggle_button.setText("▼" if self.expanded else "►")
        
        # Connect button to toggle function
        self.toggle_button.clicked.connect(self.toggle_section)
        
        # Title label
        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet("""
            font-weight: bold;
            font-size: 12px;
            color: #2c3e50;
        """)
        
        # Add widgets to header layout
        header_layout.addWidget(self.toggle_button)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        # Add header to main layout
        self.main_layout.addWidget(self.header_frame)
        
        # Container for animated content
        self.content_area = QScrollArea()
        self.content_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.content_area.setMaximumHeight(0 if not self.expanded else 1000)
        self.content_area.setMinimumHeight(0)
        self.content_area.setWidgetResizable(True)
        self.content_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Add content area to main layout
        self.main_layout.addWidget(self.content_area)
        
        # Apply initial state
        if self.expanded:
            self.content_area.setMaximumHeight(1000)  # Start expanded
        else:
            self.content_area.setMaximumHeight(0)     # Start collapsed
    
    def toggle_section(self, checked=None):
        """
        Toggle the section between expanded and collapsed states
        
        Args:
            checked (bool, optional): If provided, force expansion state
        """
        # Use provided checked status or toggle current state
        if checked is not None:
            self.expanded = checked
        else:
            self.expanded = not self.expanded
            self.toggle_button.setChecked(self.expanded)
        
        # Update toggle button text
        self.toggle_button.setText("▼" if self.expanded else "►")
        
        # Set up animation for smooth expansion/collapse
        self.animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.animation.setDuration(300)  # Animation duration in ms
        
        if self.expanded:
            self.animation.setStartValue(0)
            content_height = self.content_widget.sizeHint().height() if self.content_widget else 100
            self.animation.setEndValue(content_height)
        else:
            content_height = self.content_area.height()
            self.animation.setStartValue(content_height)
            self.animation.setEndValue(0)
        
        self.animation.start()
        
        # Emit signal
        self.toggled.emit(self.expanded)
    
    def setContentLayout(self, layout):
        """
        Set the layout for the content section
        
        Args:
            layout (QLayout): Layout containing content widgets
        """
        # Create a widget to hold the content layout
        self.content_widget = QWidget()
        
        # Set layout for content widget
        if isinstance(layout, QLayout):
            self.content_widget.setLayout(layout)
        else:
            # If a widget was passed instead of a layout
            content_layout = QVBoxLayout(self.content_widget)
            content_layout.addWidget(layout)
        
        # Set widget for scroll area
        self.content_area.setWidget(self.content_widget)
        
        # Update maximum height based on expanded state
        if self.expanded:
            self.content_area.setMaximumHeight(self.content_widget.sizeHint().height())
        else:
            self.content_area.setMaximumHeight(0)
    
    def setTitle(self, title):
        """
        Update the section title
        
        Args:
            title (str): New section title
        """
        self.title = title
        self.title_label.setText(title)
    
    def isExpanded(self):
        """Return whether section is currently expanded"""
        return self.expanded
    
    def setExpanded(self, expanded):
        """
        Set section expansion state
        
        Args:
            expanded (bool): True to expand, False to collapse
        """
        if expanded != self.expanded:
            self.toggle_section(expanded)