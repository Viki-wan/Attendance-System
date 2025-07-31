import sys
import sqlite3
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QHBoxLayout, QVBoxLayout, 
                           QPushButton, QDialog, QFormLayout, QLineEdit,
                           QMessageBox, QComboBox, QApplication, QLabel, QDateEdit, QTimeEdit,
                           QGroupBox, QCheckBox, QSpinBox, QCalendarWidget, QRadioButton,
                           QSpacerItem, QSizePolicy, QGridLayout, QFrame, QScrollArea, QWidget)
from PyQt5.QtCore import Qt, QDate, QTime
from config.utils_constants import DATABASE_PATH

class ClassSessionDialog(QDialog):
    def __init__(self, parent=None, session_id=None, class_id=None):
        super().__init__(parent)
        
        # Set application-wide stylesheet with modern styling
        self.setStyleSheet(QApplication.instance().styleSheet())
        
        self.session_id = session_id
        self.class_id = class_id  # Used when creating a new session for a specific class
        self.is_edit_mode = session_id is not None
        
        if self.is_edit_mode:
            self.setWindowTitle("Edit Class Session")
        else:
            self.setWindowTitle("Add New Class Session")
        
        # Set a reasonable default size but allow resizing
        self.setGeometry(300, 200, 650, 600)
        self.setMinimumSize(500, 400)
        
        # Enable maximization for the dialog
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        self.setup_ui()
        
        if self.is_edit_mode:
            self.load_session_data()
            # Hide recurring options in edit mode
            self.recurring_toggle.setVisible(False)
        elif self.class_id:
            # Pre-select the class if specified
            self.set_selected_class(self.class_id)
    
    def setup_ui(self):
        """Set up the dialog UI with a modern card-based interface"""
        # Create a scroll area for the entire form
        main_layout = QVBoxLayout()
        main_layout.setSpacing(24)  # Increased spacing for modern look
        main_layout.setContentsMargins(24, 24, 24, 24)  # Consistent padding
        
        # Add a prominent header
        header = QLabel(self.windowTitle())
        header.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 16px;")
        main_layout.addWidget(header)
        
        # Create a scroll area widget
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)  # Remove border
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Container widget for scroll area
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(24)  # Modern spacing
        
        # Custom card style for all sections
        card_style = """
        QFrame.card {
            background-color: white;
            border-radius: 8px;
            padding: 24px;
            margin: 8px 0px;
        }
        QFrame.card {
            border: 1px solid #e0e0e0;
            box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.05);
        }
        QLabel.section-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 16px;
            color: #333333;
        }
        QComboBox {
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 8px;
            min-height: 20px;
            background-color: white;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 24px;
            border-left: none;
        }
        QPushButton.primary {
            background-color: #1976d2;
            color: white;
            border-radius: 4px;
            padding: 10px 20px;
            font-weight: bold;
        }
        QPushButton.primary:hover {
            background-color: #1565c0;
        }
        QPushButton.secondary {
            background-color: transparent;
            color: #1976d2;
            border: 1px solid #1976d2;
            border-radius: 4px;
            padding: 10px 20px;
        }
        QPushButton.secondary:hover {
            background-color: rgba(25, 118, 210, 0.05);
        }
        QLineEdit, QDateEdit, QTimeEdit, QSpinBox {
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 8px;
            min-height: 20px;
            background-color: white;
        }
        QLabel.helper-text {
            color: #757575;
            font-size: 12px;
            margin-top: 4px;
        }
        QLabel.form-label {
            font-weight: 500;
            color: #424242;
        }
        """
        self.setStyleSheet(card_style)
        
        # Session details card
        session_card = QFrame()
        session_card.setObjectName("session-details-card")
        session_card.setFrameShape(QFrame.StyledPanel)
        session_card.setProperty("class", "card")
        session_layout = QVBoxLayout(session_card)
        
        # Card title
        session_title = QLabel("Session Details")
        session_title.setProperty("class", "section-title")
        session_layout.addWidget(session_title)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(16)  # Consistent form spacing
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form_layout.setLabelAlignment(Qt.AlignLeft)
        
        # Class selection with improved styling
        class_label = QLabel("Class:")
        class_label.setProperty("class", "form-label")
        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(300)
        self.class_combo.setPlaceholderText("Select a class or type to search...")
        self.load_classes()
        
        class_helper = QLabel("Select the class for this session")
        class_helper.setProperty("class", "helper-text")
        
        class_container = QVBoxLayout()
        class_container.setSpacing(4)
        class_container.addWidget(self.class_combo)
        class_container.addWidget(class_helper)
        
        form_layout.addRow(class_label, class_container)
        
        # Date picker with improved styling
        date_label = QLabel("Date:")
        date_label.setProperty("class", "form-label")
        date_container = QVBoxLayout()
        date_container.setSpacing(4)
        
        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)
        self.date_picker.setDisplayFormat("yyyy-MM-dd")
        self.date_picker.setMinimumWidth(150)
        self.date_picker.setDate(QDate.currentDate())
        
        date_helper = QLabel("Select the start date for this class session")
        date_helper.setProperty("class", "helper-text")
        
        date_container.addWidget(self.date_picker)
        date_container.addWidget(date_helper)
        
        form_layout.addRow(date_label, date_container)
        
        # Time pickers with improved layout
        time_layout = QGridLayout()
        time_layout.setSpacing(16)
        time_layout.setColumnStretch(1, 1) 
        time_layout.setColumnStretch(3, 1)

        # Start time with helper text
        start_time_label = QLabel("Start Time:")
        start_time_label.setProperty("class", "form-label")
        self.start_time_picker = QTimeEdit()
        self.start_time_picker.setDisplayFormat("HH:mm")
        self.start_time_picker.setMinimumWidth(120)
        self.start_time_picker.setTime(QTime(8, 0))
        
        start_helper = QLabel("Session start time (24-hour format)")
        start_helper.setProperty("class", "helper-text")
        
        time_layout.addWidget(start_time_label, 0, 0)
        time_layout.addWidget(self.start_time_picker, 0, 1)
        time_layout.addWidget(start_helper, 1, 1)
        
        # End time with helper text
        end_time_label = QLabel("End Time:")
        end_time_label.setProperty("class", "form-label")
        self.end_time_picker = QTimeEdit()
        self.end_time_picker.setDisplayFormat("HH:mm")
        self.end_time_picker.setMinimumWidth(120)
        self.end_time_picker.setTime(QTime(10, 0))
        
        end_helper = QLabel("Session end time (24-hour format)")
        end_helper.setProperty("class", "helper-text")
        
        # Duration calculator
        self.duration_label = QLabel("Duration: 2 hours")
        self.duration_label.setStyleSheet("color: #1976d2; font-weight: 500;")
        
        # Connect time change signals to update duration
        self.start_time_picker.timeChanged.connect(self.update_duration)
        self.end_time_picker.timeChanged.connect(self.update_duration)
        
        time_layout.addWidget(end_time_label, 0, 2)
        time_layout.addWidget(self.end_time_picker, 0, 3)
        time_layout.addWidget(end_helper, 1, 3)
        time_layout.addWidget(self.duration_label, 2, 1, 1, 3)
        
        form_layout.addRow("", time_layout)
        session_layout.addLayout(form_layout)
        
        # Add session card to container
        container_layout.addWidget(session_card)
        
        # Recurring sessions card with modern toggle
        recurring_card = QFrame()
        recurring_card.setObjectName("recurring-card")
        recurring_card.setFrameShape(QFrame.StyledPanel)
        recurring_card.setProperty("class", "card")
        recurring_layout = QVBoxLayout(recurring_card)
        
        # Header with toggle
        recurring_header = QHBoxLayout()
        recurring_title = QLabel("Recurring Sessions")
        recurring_title.setProperty("class", "section-title")
        recurring_header.addWidget(recurring_title)
        
        # Create a modern toggle switch
        self.recurring_toggle = QCheckBox("Enable recurring sessions")
        self.recurring_toggle.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 36px;
                height: 20px;
                border-radius: 10px;
                background-color: #e0e0e0;
            }
            QCheckBox::indicator:checked {
                background-color: #1976d2;
            }
        """)
        
        recurring_header.addWidget(self.recurring_toggle)
        recurring_header.addStretch(1)
        recurring_layout.addLayout(recurring_header)
        
        # Recurring options container
        self.recurring_container = QWidget()
        recurring_options_layout = QVBoxLayout(self.recurring_container)
        recurring_options_layout.setSpacing(16)
        
        # Weekly recurrence pattern
        recurrence_form = QFormLayout()
        recurrence_form.setSpacing(16)
        
        weekly_layout = QHBoxLayout()
        weekly_layout.setSpacing(8)
        
        repeat_label = QLabel("Repeat every:")
        repeat_label.setProperty("class", "form-label")
        
        self.weeks_spin = QSpinBox()
        self.weeks_spin.setMinimum(1)
        self.weeks_spin.setMaximum(12)
        self.weeks_spin.setValue(1)
        self.weeks_spin.setFixedWidth(70)
        
        weekly_layout.addWidget(self.weeks_spin)
        weekly_layout.addWidget(QLabel("week(s)"))
        weekly_layout.addStretch(1)
        
        recurrence_form.addRow(repeat_label, weekly_layout)
        recurring_options_layout.addLayout(recurrence_form)
        
        # Weekday selection - improved visualization
        weekday_container = QVBoxLayout()
        weekday_label = QLabel("Days of week:")
        weekday_label.setProperty("class", "form-label")
        weekday_container.addWidget(weekday_label)
        
        weekday_helper = QLabel("Select which days of the week this class will occur")
        weekday_helper.setProperty("class", "helper-text")
        weekday_container.addWidget(weekday_helper)
        
        weekday_grid = QGridLayout()
        weekday_grid.setSpacing(16)
        
        self.day_checkboxes = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        day_icons = ["📅", "📅", "📅", "📅", "📅"]  # Icons for each day
        

        for col in range(4):
            weekday_grid.setColumnStretch(col, 1)
        # Place weekdays in a more evenly spaced grid with visual indicators
        for i, day in enumerate(days):
            row = i // 4
            col = i % 4
            day_container = QFrame()
            day_container.setStyleSheet("""
                QFrame {
                    border: 1px solid #e0e0e0;
                    border-radius: 6px;
                    padding: 8px;
                    background-color: white;
                }
                QFrame:hover {
                    background-color: #f5f5f5;
                }
            """)
            
            day_layout = QHBoxLayout(day_container)
            day_layout.setContentsMargins(8, 8, 8, 8)
            
            day_cb = QCheckBox()
            day_cb.setStyleSheet("""
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                }
                QCheckBox::indicator:checked {
                    background-color: #1976d2;
                    border: 1px solid #1976d2;
                }
            """)
            
            day_icon = QLabel(day_icons[i])
            day_label = QLabel(day)
            
            day_layout.addWidget(day_cb)
            day_layout.addWidget(day_icon)
            day_layout.addWidget(day_label)
            day_layout.addStretch(1)
            
            weekday_grid.addWidget(day_container, row, col)
            self.day_checkboxes.append(day_cb)
        
        weekday_container.addLayout(weekday_grid)
        recurring_options_layout.addLayout(weekday_container)
        
        # End options card
        end_options_container = QVBoxLayout()
        end_title = QLabel("End Options")
        end_title.setProperty("class", "form-label")
        end_options_container.addWidget(end_title)
        
        end_helper = QLabel("Choose when the recurring sessions will stop")
        end_helper.setProperty("class", "helper-text")
        end_options_container.addWidget(end_helper)
        
        # Option 1: End after occurrences
        occurrences_layout = QHBoxLayout()
        occurrences_layout.setSpacing(8)
        
        self.end_after_radio = QRadioButton("End after:")
        self.end_after_radio.setChecked(True)
        self.end_after_radio.setStyleSheet("""
            QRadioButton {
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 1px solid #d0d0d0;
            }
            QRadioButton::indicator:checked {
                background-color: #1976d2;
                border: 1px solid #1976d2;
            }
        """)
        
        self.occurrences_spin = QSpinBox()
        self.occurrences_spin.setMinimum(1)
        self.occurrences_spin.setMaximum(30)
        self.occurrences_spin.setValue(10)
        self.occurrences_spin.setFixedWidth(70)
        
        occurrences_layout.addWidget(self.end_after_radio)
        occurrences_layout.addWidget(self.occurrences_spin)
        occurrences_layout.addWidget(QLabel("occurrences"))
        occurrences_layout.addStretch(1)
        end_options_container.addLayout(occurrences_layout)
        
        # Show end date based on occurrences
        self.end_after_preview = QLabel("")
        self.end_after_preview.setProperty("class", "helper-text")
        self.end_after_preview.setStyleSheet("color: #1976d2;")
        occurrences_preview_layout = QHBoxLayout()
        occurrences_preview_layout.addSpacing(24) # Indent
        occurrences_preview_layout.addWidget(self.end_after_preview)
        end_options_container.addLayout(occurrences_preview_layout)
        
        # Option 2: End by date
        end_by_layout = QHBoxLayout()
        end_by_layout.setSpacing(8)
        
        self.end_by_radio = QRadioButton("End by date:")
        self.end_by_radio.setStyleSheet("""
            QRadioButton {
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 1px solid #d0d0d0;
            }
            QRadioButton::indicator:checked {
                background-color: #1976d2;
                border: 1px solid #1976d2;
            }
        """)
        
        self.end_date_picker = QDateEdit()
        self.end_date_picker.setCalendarPopup(True)
        self.end_date_picker.setDisplayFormat("yyyy-MM-dd")
        self.end_date_picker.setMinimumWidth(150)
        end_date = QDate.currentDate().addMonths(3)
        self.end_date_picker.setDate(end_date)
        
        end_by_layout.addWidget(self.end_by_radio)
        end_by_layout.addWidget(self.end_date_picker)
        end_by_layout.addStretch(1)
        end_options_container.addLayout(end_by_layout)
        
        # Connect radio buttons
        self.end_after_radio.toggled.connect(self.update_end_options)
        self.end_by_radio.toggled.connect(self.update_end_options)
        
        # Connect spin box to update preview
        self.occurrences_spin.valueChanged.connect(self.update_end_after_preview)
        
        # Set initial enabled states
        self.end_date_picker.setEnabled(False)
        
        recurring_options_layout.addLayout(end_options_container)
        recurring_layout.addWidget(self.recurring_container)
        
        # Connect toggle to show/hide options
        self.recurring_toggle.toggled.connect(self.recurring_container.setVisible)
        self.recurring_container.setVisible(False)  # Initially hidden
        
        container_layout.addWidget(recurring_card)
        
        # Preview card
        preview_card = QFrame()
        preview_card.setObjectName("preview-card")
        preview_card.setFrameShape(QFrame.StyledPanel)
        preview_card.setProperty("class", "card")
        preview_layout = QVBoxLayout(preview_card)
        
        # Card title
        preview_title = QLabel("Session Preview")
        preview_title.setProperty("class", "section-title")
        preview_layout.addWidget(preview_title)
        
        # Modern preview panel
        preview_panel = QFrame()
        preview_panel.setStyleSheet("""
            background-color: #f5f5f5;
            border-radius: 6px;
            padding: 16px;
            min-height: 120px;
        """)
        preview_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_panel_layout = QVBoxLayout(preview_panel)
        
        self.sessions_count_label = QLabel("No recurring sessions configured")
        self.sessions_count_label.setStyleSheet("font-weight: 500; color: #424242;")
        preview_panel_layout.addWidget(self.sessions_count_label)
        
        self.preview_label = QLabel("Click 'Preview Sessions' to see details")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("font-size: 14px; margin-top: 8px;")
        preview_panel_layout.addWidget(self.preview_label)
        
        preview_layout.addWidget(preview_panel)
        
        # Preview button
        self.preview_button = QPushButton("Preview Sessions")
        self.preview_button.setProperty("class", "primary")
        self.preview_button.setMinimumHeight(40)
        self.preview_button.clicked.connect(self.preview_sessions)
        preview_layout.addWidget(self.preview_button)
        
        container_layout.addWidget(preview_card)
        
        # Set the container as the scroll area widget
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)
        
        # Add a divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setStyleSheet("background-color: #e0e0e0; max-height: 1px;")
        main_layout.addWidget(divider)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)
        
        # Add stretch to push buttons to the right
        button_layout.addStretch(1)
        
        # Modern buttons with correct order (primary on right)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("class", "secondary")
        self.cancel_button.setMinimumWidth(120)
        self.cancel_button.setMinimumHeight(40)
        self.cancel_button.clicked.connect(self.reject)
        
        self.save_button = QPushButton("Save")
        self.save_button.setProperty("class", "primary")
        self.save_button.setMinimumWidth(120)
        self.save_button.setMinimumHeight(40)
        self.save_button.clicked.connect(self.save_session)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
        # Initialize the end after preview
        self.update_end_after_preview()
        
        # Initialize duration label
        self.update_duration()    

    def update_end_options(self, checked):
        """Update end options based on radio button selection"""
        if self.end_after_radio.isChecked():
            self.occurrences_spin.setEnabled(True)
            self.end_date_picker.setEnabled(False)
            self.update_end_after_preview()
        else:
            self.occurrences_spin.setEnabled(False)
            self.end_date_picker.setEnabled(True)

    def update_end_after_preview(self):
        """Update the preview text showing when sessions will end"""
        if not self.end_after_radio.isChecked():
            self.end_after_preview.setText("")
            return
            
        # Count selected days
        selected_days = 0
        for cb in self.day_checkboxes:
            if cb.isChecked():
                selected_days += 1
        
        if selected_days == 0:
            self.end_after_preview.setText("Please select at least one weekday")
            return
        
        # Estimate end date
        occurrences = self.occurrences_spin.value()
        weeks_needed = (occurrences + selected_days - 1) // selected_days
        weeks_needed *= self.weeks_spin.value()
        
        end_date = self.date_picker.date().addDays(weeks_needed * 7)
        end_date_str = end_date.toString("MMMM d, yyyy")
        
        self.end_after_preview.setText(f"Will end around {end_date_str}")

    def update_duration(self):
        """Update the duration text based on start and end times"""
        start_time = self.start_time_picker.time()
        end_time = self.end_time_picker.time()
        
        # Calculate duration in minutes
        start_minutes = start_time.hour() * 60 + start_time.minute()
        end_minutes = end_time.hour() * 60 + end_time.minute()
        
        # Handle if end time is before start time (next day)
        if end_minutes < start_minutes:
            end_minutes += 24 * 60  # Add a day
        
        duration_minutes = end_minutes - start_minutes
        
        # Format as hours and minutes
        hours = duration_minutes // 60
        minutes = duration_minutes % 60
        
        if hours > 0 and minutes > 0:
            duration_text = f"Duration: {hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
        elif hours > 0:
            duration_text = f"Duration: {hours} hour{'s' if hours != 1 else ''}"
        else:
            duration_text = f"Duration: {minutes} minute{'s' if minutes != 1 else ''}"
        
        self.duration_label.setText(duration_text)

    
    def determine_status(self, session_date, start_time, end_time):
        """Automatically determine session status based on date and time"""
        today = QDate.currentDate()
        current_time = QTime.currentTime()
        
        # Convert string times to QTime objects if they're strings
        if isinstance(start_time, str):
            start_time = self.parse_time_string(start_time)
        if isinstance(end_time, str):
            end_time = self.parse_time_string(end_time)
            
        # If the session date is in the future
        if session_date > today:
            return "scheduled"
        
        # If the session date is today
        elif session_date == today:
            # If the session hasn't started yet
            if current_time < start_time:
                return "scheduled"
            # If the session is currently happening
            elif start_time <= current_time <= end_time:
                return "in-progress"
            # If the session has ended
            else:
                return "completed"
        
        # If the session date is in the past
        else:
            return "completed"

    def update_weekday_selection(self, date):
        """Update the weekday checkbox based on the selected date"""
        # Only update if we're not in edit mode
        if not self.is_edit_mode:
            # Uncheck all first
            for cb in self.day_checkboxes:
                cb.setChecked(False)
                
            # Check the corresponding day
            weekday = date.dayOfWeek() - 1  # Qt uses 1-7 (Mon-Sun)
            if 0 <= weekday < 7:
                self.day_checkboxes[weekday].setChecked(True)
    
    def preview_sessions(self):
        """Generate and preview the sessions that will be created"""
        if not self.recurring_toggle.isChecked():
            self.sessions_count_label.setText("Single Session")
            self.preview_label.setText("A single session will be created for the selected date.")
            return
                
        sessions = self.generate_recurring_sessions(preview_only=True)
        
        if not sessions:
            self.sessions_count_label.setText("No Sessions")
            self.preview_label.setText("No sessions will be created. Please select at least one day of the week.")
            return
        
        self.sessions_count_label.setText(f"Total: {len(sessions)} Sessions")
        
        preview_text = "<table style='border-collapse: collapse; width: 100%;'>"
        preview_text += "<tr style='background-color: #f0f0f0;'><th style='text-align: left; padding: 8px;'>Date</th><th style='text-align: left; padding: 8px;'>Day</th><th style='text-align: left; padding: 8px;'>Time</th></tr>"
        
        for i, (date, start_time, end_time) in enumerate(sessions[:5], 1):
            day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][date.dayOfWeek() - 1]
            bg_color = "#f9f9f9" if i % 2 == 0 else "white"
            
            preview_text += f"<tr style='background-color: {bg_color};'>"
            preview_text += f"<td style='padding: 8px;'>{date.toString('MMM d, yyyy')}</td>"
            preview_text += f"<td style='padding: 8px;'>{day_name}</td>"
            preview_text += f"<td style='padding: 8px;'>{start_time} - {end_time}</td>"
            preview_text += "</tr>"
        
        preview_text += "</table>"
        
        if len(sessions) > 5:
            preview_text += f"<p>...and {len(sessions) - 5} more sessions</p>"
        
        self.preview_label.setText(preview_text)
        self.preview_label.setTextFormat(Qt.RichText)
        
    def generate_recurring_sessions(self, preview_only=False):
        """Generate recurring session dates and times based on user input"""
        if not self.recurring_toggle.isChecked():
            # If recurring is not enabled, return just the single session
            date = self.date_picker.date()
            start_time = self.start_time_picker.time().toString("HH:mm")
            end_time = self.end_time_picker.time().toString("HH:mm")
            return [(date, start_time, end_time)]
            
        sessions = []
        
        # Get selected days of week (0-6 for Mon-Sun)
        selected_days = []
        for i, cb in enumerate(self.day_checkboxes):
            if cb.isChecked():
                selected_days.append(i + 1)  # Convert to Qt's 1-7 day format
                
        if not selected_days:
            if not preview_only:
                QMessageBox.warning(self, "Input Error", "Please select at least one day of the week")
            return []
            
        # Calculate end date
        if self.end_by_radio.isChecked():
            end_date = self.end_date_picker.date()
        else:
            # Based on occurrences
            # This is an approximation, we'll count actual occurrences later
            weeks_needed = (self.occurrences_spin.value() // len(selected_days)) + 1
            end_date = self.date_picker.date().addDays(weeks_needed * 7 * self.weeks_spin.value())
            
        # Start from the selected date
        current_date = self.date_picker.date()
        
        # Get times
        start_time = self.start_time_picker.time().toString("HH:mm")
        end_time = self.end_time_picker.time().toString("HH:mm")
        
        # Set maximum sessions to avoid infinite loops
        max_sessions = 100 if not preview_only else 30
        
        # Generate sessions
        session_count = 0
        occurrence_count = 0
        
        # Add first session if the start date is a selected day
        if current_date.dayOfWeek() in selected_days:
            sessions.append((current_date, start_time, end_time))
            occurrence_count += 1
            
        # Move to next day
        current_date = current_date.addDays(1)
        
        # Generate remaining sessions
        week_counter = 0
        
        while (current_date <= end_date and 
               occurrence_count < self.occurrences_spin.value() and 
               session_count < max_sessions):
            
            # Check if we've completed a week
            if week_counter == 7:
                week_counter = 0
                
                # Apply the week interval
                if self.weeks_spin.value() > 1:
                    current_date = current_date.addDays((self.weeks_spin.value() - 1) * 7)
            
            # Check if current day is selected
            if current_date.dayOfWeek() in selected_days:
                sessions.append((current_date, start_time, end_time))
                occurrence_count += 1
                
            # Move to next day
            current_date = current_date.addDays(1)
            week_counter += 1
            session_count += 1
            
        return sessions
    
    def load_classes(self):
        """Load classes for the combo box"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT c.class_id, c.class_name, co.course_name
                FROM classes c
                JOIN courses co ON c.course_code = co.course_code
                ORDER BY c.class_name
            """)
            
            classes = cursor.fetchall()
            conn.close()
            
            self.class_combo.clear()
            for class_data in classes:
                class_id, class_name, course_name = class_data
                self.class_combo.addItem(f"{class_name} ({course_name})", class_id)
                
        except Exception as e:
            print(f"❌ Error loading classes: {e}")
            QMessageBox.warning(self, "Database Error", f"Could not load classes: {e}")
    
    def set_selected_class(self, class_id):
        """Set the selected class in the combo box"""
        for i in range(self.class_combo.count()):
            if self.class_combo.itemData(i) == class_id:
                self.class_combo.setCurrentIndex(i)
                break
    
    def parse_time_string(self, time_str):
        """Parse a time string in HH:MM format to QTime"""
        try:
            hours, minutes = map(int, time_str.split(':'))
            return QTime(hours, minutes)
        except:
            return QTime(0, 0)  # Default time
    
    def parse_date_string(self, date_str):
        """Parse a date string in YYYY-MM-DD format to QDate"""
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return QDate(date_obj.year, date_obj.month, date_obj.day)
        except:
            return QDate.currentDate()  # Default date
    
    def load_session_data(self):
        """Load existing session data for editing"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT class_id, date, start_time, end_time, status
                FROM class_sessions 
                WHERE session_id = ?
            """, (self.session_id,))
            
            session = cursor.fetchone()
            conn.close()
            
            if not session:
                QMessageBox.warning(self, "Error", "Session not found")
                self.reject()
                return
            
            class_id, date_str, start_time, end_time, status = session
            
            # Set values in the form
            self.set_selected_class(class_id)
            self.date_picker.setDate(self.parse_date_string(date_str))
            self.start_time_picker.setTime(self.parse_time_string(start_time))
            self.end_time_picker.setTime(self.parse_time_string(end_time))
            
                            
        except Exception as e:
            print(f"❌ Error loading session data: {e}")
            QMessageBox.warning(self, "Database Error", f"Could not load session data: {e}")
            self.reject()
    
    def validate_time_range(self):
        """Validate that start time is before end time"""
        start_time = self.start_time_picker.time()
        end_time = self.end_time_picker.time()
        
        return start_time < end_time
    
    def save_session(self):
        """Save the session(s) to the database"""
        try:
            class_id = self.class_combo.currentData()
            
            # Validate input
            if not class_id:
                QMessageBox.warning(self, "Input Error", "Please select a class")
                return
            
            if not self.validate_time_range():
                QMessageBox.warning(self, "Input Error", "Start time must be before end time")
                return
            
            # Show a "saving" message to indicate progress
            saving_msg = QMessageBox(self)
            saving_msg.setWindowTitle("Saving")
            saving_msg.setText("Saving session data...")
            saving_msg.setStandardButtons(QMessageBox.NoButton)
            saving_msg.show()
            QApplication.processEvents()  # Force UI update
            
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            # Get course and semester information for the selected class
            cursor.execute("""
                SELECT c.course_code, c.year, c.semester
                FROM classes c
                WHERE c.class_id = ?
            """, (class_id,))
            
            class_info = cursor.fetchone()
            
            if not class_info:
                saving_msg.close()
                QMessageBox.warning(self, "Error", "Could not retrieve class information")
                conn.close()
                return
                
            course_code, year, semester = class_info
            
            if self.is_edit_mode:
                # Update existing session
                date_str = self.date_picker.date().toString("yyyy-MM-dd")
                start_time = self.start_time_picker.time().toString("HH:mm")
                end_time = self.end_time_picker.time().toString("HH:mm")
                
                # Check for scheduling conflicts with other classes in same course/semester
                # Exclude the current session from the conflict check
                cursor.execute("""
                    SELECT cs.session_id, c.class_name, cs.start_time, cs.end_time
                    FROM class_sessions cs
                    JOIN classes c ON cs.class_id = c.class_id
                    WHERE c.course_code = ? AND c.year = ? AND c.semester = ?
                    AND cs.date = ?
                    AND cs.session_id != ?
                    AND ((cs.start_time < ? AND cs.end_time > ?) OR
                        (cs.start_time >= ? AND cs.start_time < ?) OR
                        (cs.end_time > ? AND cs.end_time <= ?))
                """, (course_code, year, semester, date_str, self.session_id, 
                    end_time, start_time, start_time, end_time, start_time, end_time))
                
                conflicts = cursor.fetchall()
                
                if conflicts:
                    saving_msg.close()
                    conflict_list = "\n".join([f"- {cls_name} ({s_time} - {e_time})" 
                                            for _, cls_name, s_time, e_time in conflicts])
                    QMessageBox.warning(self, "Scheduling Conflict", 
                                    f"There are scheduling conflicts with other classes in the same course and semester for {date_str}:\n\n{conflict_list}")
                    conn.close()
                    return
                
                # Determine status automatically
                status = self.determine_status(self.date_picker.date(), 
                                            self.start_time_picker.time(), 
                                            self.end_time_picker.time())
                
                cursor.execute("""
                    UPDATE class_sessions SET 
                    class_id = ?,
                    date = ?,
                    start_time = ?,
                    end_time = ?,
                    status = ?
                    WHERE session_id = ?
                """, (class_id, date_str, start_time, end_time, status, self.session_id))
                
                message = "Session updated successfully"
                sessions_created = 1
            else:
                # Generate sessions based on recurring options
                sessions = self.generate_recurring_sessions()
                
                if not sessions:
                    saving_msg.close()
                    QMessageBox.warning(self, "Input Error", "No sessions to create. Please check your selections.")
                    conn.close()
                    return
                
                # Check for conflicts for each session
                sessions_to_create = []
                conflict_dates = []
                
                for date, start_time, end_time in sessions:
                    date_str = date.toString("yyyy-MM-dd")
                    
                    # Check for scheduling conflicts with other classes in same course/semester
                    cursor.execute("""
                        SELECT cs.session_id, c.class_name, cs.start_time, cs.end_time
                        FROM class_sessions cs
                        JOIN classes c ON cs.class_id = c.class_id
                        WHERE c.course_code = ? AND c.year = ? AND c.semester = ?
                        AND cs.date = ?
                        AND ((cs.start_time < ? AND cs.end_time > ?) OR
                            (cs.start_time >= ? AND cs.start_time < ?) OR
                            (cs.end_time > ? AND cs.end_time <= ?))
                    """, (course_code, year, semester, date_str, 
                        end_time, start_time, start_time, end_time, start_time, end_time))
                    
                    conflicts = cursor.fetchall()
                    
                    if conflicts:
                        conflict_list = ", ".join([f"{cls_name}" for _, cls_name, _, _ in conflicts])
                        conflict_dates.append(f"{date_str} ({conflict_list})")
                    else:
                        sessions_to_create.append((date, start_time, end_time))
                
                if conflict_dates:
                    saving_msg.close()
                    if len(conflict_dates) == len(sessions):
                        QMessageBox.warning(self, "Scheduling Conflict", 
                                        f"All sessions have conflicts with other classes in the same course and semester. No sessions were created.\n\nConflicts on:\n{chr(10).join(conflict_dates[:5])}" + 
                                        (f"\n...and {len(conflict_dates)-5} more dates" if len(conflict_dates) > 5 else ""))
                        conn.close()
                        return
                    else:
                        result = QMessageBox.question(self, "Partial Scheduling Conflicts", 
                                                f"{len(conflict_dates)} out of {len(sessions)} sessions have conflicts with other classes in the same course and semester.\n\nConflicts on:\n{chr(10).join(conflict_dates[:5])}" + 
                                                (f"\n...and {len(conflict_dates)-5} more dates" if len(conflict_dates) > 5 else "") +
                                                f"\n\nDo you want to create the {len(sessions_to_create)} non-conflicting sessions?",
                                                QMessageBox.Yes | QMessageBox.No)
                        if result == QMessageBox.No:
                            conn.close()
                            return
                
                # Insert non-conflicting sessions
                for date, start_time, end_time in sessions_to_create:
                    date_str = date.toString("yyyy-MM-dd")
                    
                    # Determine status automatically for each session
                    status = self.determine_status(date, 
                                                self.parse_time_string(start_time),
                                                self.parse_time_string(end_time))
                    
                    cursor.execute("""
                        INSERT INTO class_sessions 
                        (class_id, date, start_time, end_time, status) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (class_id, date_str, start_time, end_time, status))
                    
                sessions_created = len(sessions_to_create)
                
                if sessions_created == 0:
                    saving_msg.close()
                    QMessageBox.warning(self, "Error", "No sessions were created due to conflicts")
                    conn.close()
                    return
                    
                message = f"{sessions_created} session(s) created successfully"
                if len(conflict_dates) > 0:
                    message += f" ({len(conflict_dates)} skipped due to conflicts)"

            conn.commit()
            conn.close()
            
            # Close the saving message
            saving_msg.close()
            
            QMessageBox.information(self, "Success", message)
            self.accept()
            
        except Exception as e:
            print(f"❌ Error saving session: {e}")
            QMessageBox.warning(self, "Database Error", f"Could not save session: {e}")