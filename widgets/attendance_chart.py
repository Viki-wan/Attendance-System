from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtChart import QChart, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis, QChartView

class AttendanceBarChart(QWidget):
    """
    A reusable bar chart widget specifically designed for attendance visualization.
    
    This widget creates bar charts for comparing attendance across different categories,
    with customizable colors and labels.
    """
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI components"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create chart view
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.layout.addWidget(self.chart_view)
        
        # Create empty chart initially
        self.create_empty_chart("No data available")
        
    def set_data(self, labels, values, title="Attendance", bar_colors=None):
        """
        Set data for the bar chart
        
        Args:
            labels (list): Category labels for the x-axis
            values (list): Values for each category
            title (str): Chart title
            bar_colors (list, optional): List of colors for bars. Defaults to None.
        """
        if not labels or not values or len(labels) != len(values):
            self.create_empty_chart("Invalid data provided")
            return
            
        # Create chart
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setTitle(title)
        
        # Create bar series
        bar_series = QBarSeries()
        
        # If bar_colors and values have the same length, create separate bar sets for each value
        # so we can color them individually
        if bar_colors and len(bar_colors) == len(values):
            for i, (label, value) in enumerate(zip(labels, values)):
                # Convert label to string to ensure it's the correct type
                bar_set = QBarSet(str(label))
                bar_set.append(value)
                # Convert string color to QColor object
                if isinstance(bar_colors[i], str):
                    bar_set.setColor(QColor(bar_colors[i]))
                else:
                    bar_set.setColor(bar_colors[i])
                bar_series.append(bar_set)
        else:
            # Create a single bar set for all values
            bar_set = QBarSet("Attendance")
            
            # Add all values to the bar set
            for value in values:
                bar_set.append(value)
            
            # Add the bar set to the series
            bar_series.append(bar_set)
        
        # Add series to chart
        chart.addSeries(bar_series)
        
        # Create axes
        axis_x = QBarCategoryAxis()
        
        # Convert all labels to strings for axis
        string_labels = [str(label) for label in labels]
        
        # Limit to 15 visible categories to avoid overcrowding
        if len(string_labels) > 15:
            # If more than 15 labels, show the first 14 and label the last one as "Others"
            visible_labels = string_labels[:14] + ["..."]
            # Store all labels for tooltip purposes
            chart.setProperty("all_labels", string_labels)
        else:
            visible_labels = string_labels
            
        axis_x.append(visible_labels)
        chart.addAxis(axis_x, Qt.AlignBottom)
        bar_series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        # Set Y-axis range to be 0-100 (percentage) or slightly higher than max value
        max_value = max(values) if values else 0
        y_max = max(100, max_value * 1.1)  # Either 100% or 110% of max value
        axis_y.setRange(0, y_max)
        axis_y.setTitleText("Percentage (%)")
        chart.addAxis(axis_y, Qt.AlignLeft)
        bar_series.attachAxis(axis_y)
        
        # Apply theme
        chart.setTheme(QChart.ChartThemeLight)
        chart.legend().setVisible(False)
        
        # Set the chart in the chart view
        self.chart_view.setChart(chart) 
        
    def clear_data(self, message="No data available"):
        """
        Clear the chart and display a message
        
        Args:
            message (str): Message to display on empty chart
        """
        self.create_empty_chart(message)
        
    def create_empty_chart(self, message):
        """
        Create an empty chart with a message
        
        Args:
            message (str): Message to display on empty chart
        """
        chart = QChart()
        chart.setTitle(message)
        chart.legend().hide()
        self.chart_view.setChart(chart)
        
    def create_line_chart(self, x_values, y_values, title="Attendance Trend"):
        """
        Create a line chart for attendance trends over time
        
        Args:
            x_values (list): X-axis values (typically dates)
            y_values (list): Y-axis values (attendance percentages)
            title (str): Chart title
        """
        # Implementation for line chart can be added here
        # This would be useful for trend_report.py
        pass
        
    def create_pie_chart(self, labels, values, title="Attendance Distribution"):
        """
        Create a pie chart for attendance distribution
        
        Args:
            labels (list): Category labels 
            values (list): Values for each category
            title (str): Chart title
        """
       
        pass