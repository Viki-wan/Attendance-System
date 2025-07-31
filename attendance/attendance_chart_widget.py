# attendance_chart_widget.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush

class AttendanceChartWidget(QWidget):
    """Widget for visualizing attendance statistics"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(200)
        self.attendance_data = []
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI"""
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        # Default label when no data
        self.no_data_label = QLabel("No attendance data available")
        self.no_data_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.no_data_label)
        
    def update_chart(self, attendance_data):
        """Update chart with new attendance data"""
        self.attendance_data = attendance_data
        
        # Show or hide the no data label
        self.no_data_label.setVisible(len(attendance_data) == 0)
        
        # Trigger repaint
        self.update()
        
    def paintEvent(self, event):
        """Paint the attendance chart"""
        if not self.attendance_data:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Drawing area dimensions
        chart_rect = self.rect().adjusted(10, 10, -10, -30)  # Margins
        
        # Draw chart background
        painter.fillRect(chart_rect, QColor(245, 245, 245))
        
        # Get max value for scaling
        max_total = max([day['total'] for day in self.attendance_data]) if self.attendance_data else 0
        if max_total == 0:
            return
            
        # Calculate bar width based on number of data points
        num_days = len(self.attendance_data)
        if num_days == 0:
            return
            
        bar_width = chart_rect.width() / (num_days * 2)  # Leave space between bars
        bar_spacing = bar_width / 2
        
        # Draw bars
        for i, day_data in enumerate(self.attendance_data):
            # Calculate bar positions
            x_pos = chart_rect.x() + (i * (bar_width * 2)) + bar_spacing
            
            # Present bar (green)
            present_height = (day_data['present'] / max_total) * chart_rect.height()
            present_rect = Qt.QRectF(
                x_pos, 
                chart_rect.bottom() - present_height,
                bar_width, 
                present_height
            )
            painter.setBrush(QColor(100, 200, 100))  # Green
            painter.setPen(Qt.NoPen)
            painter.drawRect(present_rect)
            
            # Absent bar (red) - next to present
            absent_height = (day_data['absent'] / max_total) * chart_rect.height()
            absent_rect = Qt.QRectF(
                x_pos + bar_width, 
                chart_rect.bottom() - absent_height,
                bar_width, 
                absent_height
            )
            painter.setBrush(QColor(200, 100, 100))  # Red
            painter.setPen(Qt.NoPen)
            painter.drawRect(absent_rect)
            
            # Draw date label
            date_str = day_data['date'].split('-')[-1]  # Just day part of date
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(
                int(x_pos), 
                chart_rect.bottom() + 15,
                int(bar_width * 2), 
                20, 
                Qt.AlignCenter, 
                date_str
            )
            
        # Draw legend
        legend_x = chart_rect.right() - 150
        legend_y = chart_rect.top() + 10
        
        # Present legend
        painter.setBrush(QColor(100, 200, 100))
        painter.drawRect(legend_x, legend_y, 20, 10)
        painter.drawText(legend_x + 25, legend_y, 100, 20, Qt.AlignLeft | Qt.AlignVCenter, "Present")
        
        # Absent legend
        painter.setBrush(QColor(200, 100, 100))
        painter.drawRect(legend_x, legend_y + 20, 20, 10)
        painter.drawText(legend_x + 25, legend_y + 20, 100, 20, Qt.AlignLeft | Qt.AlignVCenter, "Absent")