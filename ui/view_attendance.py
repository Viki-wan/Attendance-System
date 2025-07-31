from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem, QWidget,
    QLabel, QLineEdit, QPushButton, QApplication, QHBoxLayout, QComboBox, QFileDialog, QDateEdit
)
from PyQt5.QtCore import Qt, QDate
import sqlite3
import csv
from config.utils_constants import DATABASE_PATH

class ViewAttendanceWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Attendance Records")
        self.setGeometry(300, 200, 800, 550)  # ✅ Slightly wider window

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS


        self.records = []  # ✅ Ensure `self.records` is always defined

        self.init_ui()

    def init_ui(self):
        """Initialize UI components."""
        self.table_widget = QTableWidget()
        self.table_widget.setSortingEnabled(True)
        self.table_widget.setAlternatingRowColors(True)  
        self.table_widget.setStyleSheet(
            "QTableWidget { border: 1px solid #555; }"
            "QTableWidget::item { padding: 5px; }"
        )

        # 🔍 **Search Input**
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("🔍 Search by Student ID or Name...")
        self.search_input.textChanged.connect(self.apply_filters)

        # 📅 **Date Filter**
        self.date_filter = QDateEdit(self)
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate())
        self.date_filter.setDisplayFormat("yyyy-MM-dd")
        self.date_filter.dateChanged.connect(self.apply_filters)

        # ✅ **Status Filter**
        self.status_filter = QComboBox(self)
        self.status_filter.addItems(["All", "Present", "Absent"])
        self.status_filter.currentTextChanged.connect(self.apply_filters)

        # 📂 **Export Button**
        self.export_button = QPushButton("📂 Export to CSV")
        self.export_button.clicked.connect(self.export_to_csv)

        # 🔹 **Layout Adjustments**
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.search_input)
        top_layout.addWidget(QLabel("📅 Date:"))
        top_layout.addWidget(self.date_filter)
        top_layout.addWidget(QLabel("✅ Status:"))
        top_layout.addWidget(self.status_filter)
        top_layout.addWidget(self.export_button)

        main_layout = QVBoxLayout()
        self.title_label = QLabel("📋 Attendance Records")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 8px;")
        main_layout.addWidget(self.title_label)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.table_widget)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.load_attendance_data()

    def load_attendance_data(self):
        """Fetch and display attendance records from the database."""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
           SELECT students.student_id, students.name, 
                   COALESCE(attendance.date, 'Not Marked') AS date, 
                   COALESCE(attendance.status, 'Absent') AS status,
                   (SELECT COUNT(*) FROM attendance WHERE attendance.student_id = students.student_id AND attendance.status = 'Present') AS total_attendance
            FROM students
            LEFT JOIN attendance ON students.student_id = attendance.student_id
            ORDER BY attendance.date DESC, students.student_id;
        """)
        self.records = cursor.fetchall()
        conn.close()

        self.populate_table(self.records)


    def populate_table(self, records):
        """Populates the table with the given records."""
        self.table_widget.setRowCount(len(records))
        self.table_widget.setColumnCount(5)  # ✅ Added a new column
        self.table_widget.setHorizontalHeaderLabels(["Student ID", "Name", "Date", "Status", "Total Present"])

        for row_idx, row_data in enumerate(records):
            for col_idx, col_data in enumerate(row_data):
                item = QTableWidgetItem(str(col_data))
                item.setTextAlignment(Qt.AlignCenter)
                self.table_widget.setItem(row_idx, col_idx, item)

        self.table_widget.resizeColumnsToContents()

    def apply_filters(self):
        """Applies filtering based on search, date, and status."""
        search_text = self.search_input.text().strip().lower()
        selected_date = self.date_filter.date().toString("yyyy-MM-dd")
        selected_status = self.status_filter.currentText()

        for row in range(self.table_widget.rowCount()):
            student_id = self.table_widget.item(row, 0).text().lower()
            name = self.table_widget.item(row, 1).text().lower()
            date = self.table_widget.item(row, 2).text()
            status = self.table_widget.item(row, 3).text()

            matches_search = search_text in student_id or search_text in name
            matches_date = (selected_date in date) or (selected_date == QDate.currentDate().toString("yyyy-MM-dd"))
            matches_status = (selected_status == "All") or (status == selected_status)

            if matches_search and matches_date and matches_status:
                self.table_widget.setRowHidden(row, False)
            else:
                self.table_widget.setRowHidden(row, True)

    def export_to_csv(self):
        """Exports the attendance data to a CSV file."""
        file_path = "attendance_records.csv"
        with open(file_path, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Student ID", "Name", "Date", "Status"])  # Header

            for row in range(self.table_widget.rowCount()):
                if not self.table_widget.isRowHidden(row):
                    writer.writerow([
                        self.table_widget.item(row, 0).text(),
                        self.table_widget.item(row, 1).text(),
                        self.table_widget.item(row, 2).text(),
                        self.table_widget.item(row, 3).text()
                    ])
        
        print(f"✅ Attendance exported to {file_path}")
