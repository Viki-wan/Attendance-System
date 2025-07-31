import sqlite3
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QComboBox, QFrame, QHeaderView, QMessageBox,
                             QSplitter, QTreeWidget, QTreeWidgetItem)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QFont, QColor
from config.utils_constants import DATABASE_PATH

class StudentManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("StudentManager")
        self.init_ui()
        self.load_filter_data()
        
    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)
        
        # Filter section
        filter_frame = QFrame()
        filter_frame.setObjectName("FilterFrame")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(15, 15, 15, 15)
        
        # Year filter
        year_label = QLabel("Year:")
        year_label.setObjectName("FilterLabel")
        self.year_combo = QComboBox()
        self.year_combo.setObjectName("FilterCombo")
        self.year_combo.setMinimumWidth(150)
        filter_layout.addWidget(year_label)
        filter_layout.addWidget(self.year_combo)
        
        # Course filter
        course_label = QLabel("Course:")
        course_label.setObjectName("FilterLabel")
        self.course_combo = QComboBox()
        self.course_combo.setObjectName("FilterCombo")
        self.course_combo.setMinimumWidth(250)
        filter_layout.addWidget(course_label)
        filter_layout.addWidget(self.course_combo)
        
        # Apply filter button
        self.apply_filter_btn = QPushButton("Apply Filters")
        self.apply_filter_btn.setObjectName("ActionButtonFilter")
        self.apply_filter_btn.clicked.connect(self.apply_filters)
        filter_layout.addWidget(self.apply_filter_btn)
        
        # Reset filter button
        self.reset_filter_btn = QPushButton("Reset")
        self.reset_filter_btn.setObjectName("ActionButtonReset")
        self.reset_filter_btn.clicked.connect(self.reset_filters)
        filter_layout.addWidget(self.reset_filter_btn)
        
        filter_layout.addStretch()
        main_layout.addWidget(filter_frame)
        
        # Content splitter (students table and details)
        splitter = QSplitter(Qt.Horizontal)
        
        # Students table
        self.students_table = QTableWidget()
        self.students_table.setObjectName("StudentsTable")
        self.students_table.setColumnCount(6)
        self.students_table.setHorizontalHeaderLabels(["ID", "Name", "Course", "Year", "Email", "Current Semester"])
        self.students_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.students_table.verticalHeader().setVisible(False)
        self.students_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.students_table.setSelectionMode(QTableWidget.SingleSelection)
        self.students_table.itemSelectionChanged.connect(self.show_student_details)
        
        # Classes and courses tree
        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        
        self.student_header = QLabel("Student Details")
        self.student_header.setObjectName("DetailsHeader")
        self.student_header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        details_layout.addWidget(self.student_header)
        
        self.classes_tree = QTreeWidget()
        self.classes_tree.setObjectName("ClassesTree")
        self.classes_tree.setHeaderLabels(["Classes & Courses"])
        self.classes_tree.setColumnCount(1)
        self.classes_tree.setAlternatingRowColors(True)
        details_layout.addWidget(self.classes_tree)
        
        # Add widgets to splitter
        splitter.addWidget(self.students_table)
        splitter.addWidget(self.details_widget)
        splitter.setSizes([600, 400])  # Initial sizes
        
        main_layout.addWidget(splitter)
        
        # Status bar
        status_bar = QFrame()
        status_bar.setObjectName("StatusBar")
        status_layout = QHBoxLayout(status_bar)
        
        self.total_label = QLabel("Total Students: 0")
        self.total_label.setObjectName("StatusLabel")
        status_layout.addWidget(self.total_label)
        
        self.filtered_label = QLabel("Filtered: 0")
        self.filtered_label.setObjectName("StatusLabel")
        status_layout.addWidget(self.filtered_label)
        
        status_layout.addStretch()
        main_layout.addWidget(status_bar)
    
    def load_filter_data(self):
        """Load data for the filter dropdowns"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            # Get distinct years
            cursor.execute("SELECT DISTINCT year_of_study FROM students ORDER BY year_of_study")
            years = cursor.fetchall()
            
            # Get all courses
            cursor.execute("SELECT course_code, course_name FROM courses ORDER BY course_name")
            courses = cursor.fetchall()
            
            conn.close()
            
            # Populate year filter
            self.year_combo.addItem("All Years", -1)
            for year in years:
                if year[0]:  # Check if not None
                    self.year_combo.addItem(f"Year {year[0]}", year[0])
            
            # Populate course filter
            self.course_combo.addItem("All courses", "")
            for course in courses:
                self.course_combo.addItem(f"{course[0]} - {course[1]}", course[0])
                
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error loading filter data: {str(e)}")
    
    def show(self):
        """Override show method to load data when shown"""
        super().show()
        self.load_students()
    
    def load_students(self):
        """Load students based on filters"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            # Get filter values
            year_filter = self.year_combo.currentData()
            course_filter = self.course_combo.currentData()
            
            # Build query based on filters
            query = "SELECT DISTINCT s.student_id, s.fname || ' ' || s.lname, s.course, s.year_of_study, s.email, s.current_semester FROM students s"
            params = []
            
            if course_filter:
                query += " INNER JOIN student_courses sc ON s.student_id = sc.student_id"
                
            where_clauses = []
            
            if year_filter != -1:
                where_clauses.append("s.year_of_study = ?")
                params.append(year_filter)
                
            if course_filter:
                where_clauses.append("sc.course_code = ?")
                params.append(course_filter)
                
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
                
            query += " ORDER BY s.fname, s.lname"
            
            cursor.execute(query, params)
            students = cursor.fetchall()
            
            # Get total count for status bar
            cursor.execute("SELECT COUNT(*) FROM students")
            total_count = cursor.fetchone()[0]
            
            conn.close()
            
            # Update table
            self.students_table.setRowCount(0)  # Clear table
            for row, student in enumerate(students):
                self.students_table.insertRow(row)
                for col, value in enumerate(student):
                    item = QTableWidgetItem(str(value) if value else "")
                    item.setData(Qt.UserRole, student[0])  # Store student ID in UserRole
                    if col == 0:  # Make ID column more compact
                        item.setTextAlignment(Qt.AlignCenter)
                    self.students_table.setItem(row, col, item)
            
            # Update status bar
            self.total_label.setText(f"Total Students: {total_count}")
            self.filtered_label.setText(f"Filtered: {len(students)}")
            
            # Clear details panel
            self.classes_tree.clear()
            self.student_header.setText("Student Details")
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error loading students: {str(e)}")
    
    def show_student_details(self):
        """Show details for selected student"""
        selected_items = self.students_table.selectedItems()
        if not selected_items:
            return
            
        student_id = selected_items[0].data(Qt.UserRole)
        student_name = selected_items[0].tableWidget().item(selected_items[0].row(), 1).text()
        
        self.student_header.setText(f"Details for {student_name}")
        self.classes_tree.clear()
        
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            # Get student information
            cursor.execute("SELECT course, year_of_study, current_semester FROM students WHERE student_id = ?", 
                        (student_id,))
            student_info = cursor.fetchone()
            
            if not student_info:
                return
                
            course, year_of_study, current_semester = student_info
            
            # Get all classes that match the student's course, year, and semester
            query = """
            SELECT cl.class_id, cl.class_name, c.course_code, c.course_name 
            FROM classes cl
            JOIN courses c ON cl.course_code = c.course_code
            WHERE cl.course_code = ? 
            AND cl.year = ? 
            AND cl.semester = ?
            ORDER BY c.course_name, cl.class_name
            """
            
            cursor.execute(query, (course, year_of_study, current_semester))
            classes = cursor.fetchall()
            
            # Also get the courses the student is enrolled in (for reference)
            cursor.execute("""
            SELECT c.course_code, c.course_name, sc.semester 
            FROM student_courses sc
            JOIN courses c ON sc.course_code = c.course_code
            WHERE sc.student_id = ?
            ORDER BY sc.semester, c.course_name
            """, (student_id,))
            enrolled_courses = cursor.fetchall()
            
            # Create tree structure
            # First, add the current semester classes (automatically assigned)
            current_semester_item = QTreeWidgetItem(self.classes_tree, [f"Current Semester ({current_semester})"])
            current_semester_item.setFont(0, QFont("Segoe UI", 10, QFont.Bold))
            current_semester_item.setBackground(0, QColor("#e6f2ff"))  # Light blue background
            
            # Group classes by course
            courses_dict = {}
            for class_id, class_name, course_code, course_name in classes:
                if course_code not in courses_dict:
                    courses_dict[course_code] = {
                        "name": course_name,
                        "classes": []
                    }
                courses_dict[course_code]["classes"].append((class_id, class_name))
            
            # Add courses and classes to tree
            for course_code, course_data in courses_dict.items():
                course_item = QTreeWidgetItem(current_semester_item, [f"{course_code}: {course_data['name']}"])
                course_item.setFont(0, QFont("Segoe UI", 9, QFont.Bold))
                
                # Add classes under this course
                for class_id, class_name in course_data["classes"]:
                    class_item = QTreeWidgetItem(course_item, [f"{class_id}: {class_name}"])
                    class_item.setForeground(0, QColor("#0066cc"))  # Blue text for auto-assigned classes
            
            if not courses_dict:
                no_classes_item = QTreeWidgetItem(current_semester_item, ["No classes available for this semester"])
                no_classes_item.setForeground(0, QColor("#cc0000"))  # Red text
            
            # Now add other enrolled courses (from previous semesters, etc.)
            other_semesters = {}
            for course_code, course_name, semester in enrolled_courses:
                if semester != current_semester:  # Only include non-current semesters
                    if semester not in other_semesters:
                        other_semesters[semester] = []
                    other_semesters[semester].append((course_code, course_name))
            
            # Add other semesters if they exist
            if other_semesters:
                history_item = QTreeWidgetItem(self.classes_tree, ["Enrollment History"])
                history_item.setFont(0, QFont("Segoe UI", 10, QFont.Bold))
                history_item.setBackground(0, QColor("#f0f0f0"))
                
                for semester, courses in sorted(other_semesters.items()):
                    semester_item = QTreeWidgetItem(history_item, [f"Semester {semester}" if semester else "Unassigned"])
                    semester_item.setFont(0, QFont("Segoe UI", 9, QFont.Bold))
                    
                    for course_code, course_name in courses:
                        course_item = QTreeWidgetItem(semester_item, [f"{course_code}: {course_name}"])
            
            # Expand top level items
            for i in range(self.classes_tree.topLevelItemCount()):
                self.classes_tree.topLevelItem(i).setExpanded(True)
            
            conn.close()
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error loading student details: {str(e)}")
    
    def apply_filters(self):
        """Apply the selected filters"""
        self.load_students()
    
    def reset_filters(self):
        """Reset filters to defaults"""
        self.year_combo.setCurrentIndex(0)  # "All Years"
        self.course_combo.setCurrentIndex(0)  # "All courses"
        self.load_students()