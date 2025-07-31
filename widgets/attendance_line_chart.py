from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics
from PyQt5.QtCore import Qt, QPoint, QRect


class AttendanceLineChart(QWidget):
    """Widget for displaying attendance data as a line chart"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = []
        self.values = []
        self.title = ""
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        # Chart colors
        self.line_color = QColor(41, 128, 185)  # Blue
        self.point_color = QColor(52, 152, 219)  # Lighter blue
        self.grid_color = QColor(200, 200, 200)  # Light gray
        self.text_color = QColor(44, 62, 80)     # Dark gray
        
        # Chart settings
        self.padding = 40
        self.y_axis_width = 60
        self.x_axis_height = 40
        self.point_radius = 4

    def set_data(self, labels, values, title=""):
        """Set the data to be displayed in the chart"""
        self.labels = labels
        self.values = values
        self.title = title
        self.update()
    
    def paintEvent(self, event):
        """Paint the chart"""
        if not self.values:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Define chart area
        chart_rect = QRect(
            self.y_axis_width,                 # Left padding including y-axis labels
            self.padding,                      # Top padding
            self.width() - self.y_axis_width - self.padding,  # Width minus padding
            self.height() - self.x_axis_height - self.padding # Height minus padding
        )
        
        # Draw title
        if self.title:
            painter.setPen(self.text_color)
            font = QFont()
            font.setBold(True)
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(
                QRect(0, 10, self.width(), 20),
                Qt.AlignCenter,
                self.title
            )
        
        # Draw chart background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(240, 240, 240, 20)))
        painter.drawRect(chart_rect)
        
        # Find min and max values for scaling
        min_val = min(self.values) if self.values else 0
        max_val = max(self.values) if self.values else 100
        
        # Ensure min_val is lower than max_val
        if min_val == max_val:
            if min_val == 0:
                max_val = 100
            else:
                min_val = 0 if min_val > 50 else min_val * 0.5
                max_val = max_val * 1.1
        
        # Calculate value range and adjust for padding
        value_range = max_val - min_val
        adjusted_min = min_val - (value_range * 0.05)
        adjusted_max = max_val + (value_range * 0.05)
        
        # Draw grid lines and y-axis labels
        painter.setPen(QPen(self.grid_color, 1, Qt.DashLine))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        
        # Draw horizontal grid lines and y-axis labels
        num_y_ticks = 5
        for i in range(num_y_ticks + 1):
            y_pos = int(chart_rect.bottom() - (i * chart_rect.height() / num_y_ticks))
            
            # Draw horizontal grid line
            painter.setPen(QPen(self.grid_color, 1, Qt.DashLine))
            painter.drawLine(chart_rect.left(), y_pos, chart_rect.right(), y_pos)
            
            # Draw y-axis label
            label_value = adjusted_min + (i * (adjusted_max - adjusted_min) / num_y_ticks)
            label_text = f"{label_value:.1f}%"
            
            painter.setPen(self.text_color)
            painter.drawText(
                QRect(5, y_pos - 10, self.y_axis_width - 5, 20),
                Qt.AlignRight | Qt.AlignVCenter,
                label_text
            )
        
        # Draw x-axis labels
        if self.labels:
            painter.setPen(self.text_color)
            label_width = chart_rect.width() / len(self.labels)
            
            # Only draw a subset of labels if we have too many
            label_step = max(1, len(self.labels) // 10)
            
            for i, label in enumerate(self.labels):
                if i % label_step == 0 or i == len(self.labels) - 1:
                    x_pos = int(chart_rect.left() + (i * chart_rect.width() / (len(self.labels) - 1 if len(self.labels) > 1 else 1)))
                    
                    # Draw rotated text for x-axis labels if they would overlap
                    painter.save()
                    painter.translate(x_pos, chart_rect.bottom() + 5)
                    painter.rotate(45 if len(self.labels) > 5 else 0)
                    
                    rect = QRect(0, 0, 70, 20)
                    painter.drawText(
                        rect,
                        Qt.AlignLeft | Qt.AlignVCenter,
                        label
                    )
                    painter.restore()
        
        # Draw data line
        if len(self.values) > 1:
            painter.setPen(QPen(self.line_color, 2))
            
            for i in range(len(self.values) - 1):
                x1 = int(chart_rect.left() + (i * chart_rect.width() / (len(self.values) - 1 if len(self.values) > 1 else 1)))
                y1 = int(chart_rect.bottom() - ((self.values[i] - adjusted_min) / (adjusted_max - adjusted_min) * chart_rect.height()))
                
                x2 = int(chart_rect.left() + ((i + 1) * chart_rect.width() / (len(self.values) - 1 if len(self.values) > 1 else 1)))
                y2 = int(chart_rect.bottom() - ((self.values[i + 1] - adjusted_min) / (adjusted_max - adjusted_min) * chart_rect.height()))
                
                painter.drawLine(x1, y1, x2, y2)
        
        # Draw data points
        painter.setPen(QPen(self.point_color, 1))
        painter.setBrush(QBrush(self.point_color))
        
        for i, value in enumerate(self.values):
            x_pos = int(chart_rect.left() + (i * chart_rect.width() / (len(self.values) - 1 if len(self.values) > 1 else 1)))
            y_pos = int(chart_rect.bottom() - ((value - adjusted_min) / (adjusted_max - adjusted_min) * chart_rect.height()))
            
            painter.drawEllipse(QPoint(x_pos, y_pos), self.point_radius, self.point_radius)