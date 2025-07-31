-- Face Recognition Attendance System - Updated Database Schema

-- Activity Log Table
CREATE TABLE activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    user_type TEXT NOT NULL, -- 'instructor', 'student', 'admin'
    activity_type TEXT NOT NULL,
    description TEXT,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Admin Users Table (Single Admin for PyQt Interface)
CREATE TABLE admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

-- Courses Table
CREATE TABLE courses (
    course_code TEXT PRIMARY KEY,
    course_name TEXT NOT NULL,
    faculty TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

-- Instructors Table
CREATE TABLE instructors (
    instructor_id TEXT PRIMARY KEY,
    instructor_name TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    phone TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    faculty TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    is_active INTEGER DEFAULT 1
);

-- Students Table
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,
    fname TEXT NOT NULL,
    lname TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT UNIQUE,
    password TEXT,
    course TEXT,
    year_of_study INTEGER DEFAULT 1,
    current_semester TEXT DEFAULT '1.1',
    image_path TEXT,
    image_hash TEXT,
    face_encoding BLOB,
    face_only_path TEXT,
    face_encoding_path TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

-- Classes Table
CREATE TABLE classes (
    class_id TEXT PRIMARY KEY,
    course_code TEXT NOT NULL,
    class_name TEXT NOT NULL,
    year INTEGER DEFAULT 1,
    semester TEXT DEFAULT '1.1',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (course_code) REFERENCES courses(course_code)
);

-- Class Sessions Table
CREATE TABLE class_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id TEXT NOT NULL,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    status TEXT DEFAULT 'scheduled',
    created_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    attendance_count INTEGER DEFAULT 0,
    total_students INTEGER DEFAULT 0,
    session_notes TEXT,
    FOREIGN KEY (class_id) REFERENCES classes(class_id),
    FOREIGN KEY (created_by) REFERENCES instructors(instructor_id),
    CONSTRAINT check_session_status CHECK (status IN ('scheduled', 'ongoing', 'completed', 'cancelled', 'dismissed'))
);

-- Attendance Table
CREATE TABLE attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    session_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'Absent',
    marked_by INTEGER,
    method TEXT DEFAULT 'face_recognition',
    confidence_score REAL,
    notes TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (session_id) REFERENCES class_sessions(session_id),
    FOREIGN KEY (marked_by) REFERENCES instructors(instructor_id),
    UNIQUE(student_id, session_id),
    CONSTRAINT check_status CHECK (status IN ('Present', 'Absent', 'Late', 'Excused'))
);

-- Class Courses Junction Table
CREATE TABLE class_courses (
    class_id TEXT NOT NULL,
    course_code TEXT NOT NULL,
    PRIMARY KEY (class_id, course_code),
    FOREIGN KEY (class_id) REFERENCES classes(class_id),
    FOREIGN KEY (course_code) REFERENCES courses(course_code)
);

-- Class Instructors Junction Table
CREATE TABLE class_instructors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id TEXT NOT NULL,
    instructor_id INTEGER NOT NULL,
    assigned_date DATE DEFAULT CURRENT_DATE,
    FOREIGN KEY (class_id) REFERENCES classes(class_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id),
    UNIQUE(class_id, instructor_id)
);

-- Instructor Courses Junction Table
CREATE TABLE instructor_courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instructor_id INTEGER NOT NULL,
    course_code TEXT NOT NULL,
    semester TEXT,
    year INTEGER,
    is_coordinator INTEGER DEFAULT 0,
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id),
    FOREIGN KEY (course_code) REFERENCES courses(course_code),
    UNIQUE(instructor_id, course_code, semester, year)
);

-- Student Courses Junction Table
CREATE TABLE student_courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    course_code TEXT NOT NULL,
    semester TEXT,
    year INTEGER,
    enrollment_date TEXT DEFAULT CURRENT_DATE,
    status TEXT DEFAULT 'Active',
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (course_code) REFERENCES courses(course_code),
    UNIQUE(student_id, course_code, semester, year),
    CONSTRAINT check_enrollment_status CHECK (status IN ('Active', 'Dropped', 'Completed', 'Failed'))
);

-- Lecturer Preferences Table
CREATE TABLE lecturer_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instructor_id INTEGER NOT NULL,
    theme TEXT DEFAULT 'light',
    dashboard_layout TEXT DEFAULT 'default',
    notification_settings TEXT DEFAULT '{}',
    auto_refresh_interval INTEGER DEFAULT 30,
    default_session_duration INTEGER DEFAULT 90,
    timezone TEXT DEFAULT 'UTC',
    language TEXT DEFAULT 'en',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id),
    UNIQUE(instructor_id)
);

-- Session Dismissals Table
CREATE TABLE session_dismissals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    instructor_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    dismissal_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    rescheduled_to DATE,
    rescheduled_time TEXT,
    notes TEXT,
    status TEXT DEFAULT 'dismissed',
    FOREIGN KEY (session_id) REFERENCES class_sessions(session_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id),
    CONSTRAINT check_dismissal_status CHECK (status IN ('dismissed', 'rescheduled', 'cancelled'))
);

-- Notifications Table
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    user_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    action_url TEXT,
    priority TEXT DEFAULT 'normal',
    CONSTRAINT check_user_type CHECK (user_type IN ('instructor', 'student', 'admin')),
    CONSTRAINT check_notification_type CHECK (type IN ('info', 'warning', 'success', 'error')),
    CONSTRAINT check_priority CHECK (priority IN ('low', 'normal', 'high', 'urgent'))
);

-- System Metrics Table
CREATE TABLE system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metric_unit TEXT,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id INTEGER,
    instructor_id INTEGER,
    additional_data TEXT, -- JSON format for extra data
    FOREIGN KEY (session_id) REFERENCES class_sessions(session_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id)
);

-- Settings Table
CREATE TABLE settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT,
    description TEXT,
    category TEXT DEFAULT 'general',
    is_system INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Timetable Table
CREATE TABLE timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id TEXT NOT NULL,
    day_of_week INTEGER NOT NULL, -- 0=Sunday, 1=Monday, etc.
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_to DATE,
    FOREIGN KEY (class_id) REFERENCES classes(class_id),
    CONSTRAINT check_day_of_week CHECK (day_of_week >= 0 AND day_of_week <= 6)
);

-- Holidays Table
CREATE TABLE holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date DATE NOT NULL,
    description TEXT,
    is_recurring INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indexes
CREATE INDEX idx_attendance_student_session ON attendance(student_id, session_id);
CREATE INDEX idx_attendance_session_timestamp ON attendance(session_id, timestamp);
CREATE INDEX idx_attendance_status ON attendance(status);
CREATE INDEX idx_class_sessions_date ON class_sessions(date, class_id);
CREATE INDEX idx_class_sessions_status ON class_sessions(status);
CREATE INDEX idx_activity_log_user_timestamp ON activity_log(user_id, timestamp);
CREATE INDEX idx_student_courses_student_semester ON student_courses(student_id, semester);
CREATE INDEX idx_notifications_user_read ON notifications(user_id, is_read);
CREATE INDEX idx_notifications_expires ON notifications(expires_at);
CREATE INDEX idx_system_metrics_name_time ON system_metrics(metric_name, recorded_at);
CREATE INDEX idx_session_dismissals_session ON session_dismissals(session_id);
CREATE INDEX idx_timetable_class_day ON timetable(class_id, day_of_week);

-- Default Settings for Face Recognition System
INSERT INTO settings (setting_key, setting_value, description, category) VALUES 
('face_recognition_threshold', '0.6', 'Threshold for face recognition accuracy', 'face_recognition'),
('session_timeout_minutes', '30', 'Session timeout in minutes', 'session'),
('auto_mark_late_threshold', '10', 'Minutes after start time to mark as late', 'attendance'),
('max_session_duration', '180', 'Maximum session duration in minutes', 'session'),
('camera_quality_threshold', '720', 'Minimum camera quality requirement', 'camera'),
('notification_retention_days', '30', 'Days to keep notifications', 'notifications'),
('system_metrics_retention_days', '90', 'Days to keep system metrics', 'metrics'),
('auto_refresh_interval', '30', 'Dashboard auto-refresh interval in seconds', 'dashboard'),
('attendance_report_limit', '1000', 'Maximum records in attendance report', 'reports'),
('face_encoding_version', '1.0', 'Face encoding algorithm version', 'face_recognition');

-- Triggers for updated_at timestamps
CREATE TRIGGER update_instructors_timestamp 
    AFTER UPDATE ON instructors
    BEGIN
        UPDATE instructors SET updated_at = CURRENT_TIMESTAMP WHERE instructor_id = NEW.instructor_id;
    END;

CREATE TRIGGER update_students_timestamp 
    AFTER UPDATE ON students
    BEGIN
        UPDATE students SET updated_at = CURRENT_TIMESTAMP WHERE student_id = NEW.student_id;
    END;

CREATE TRIGGER update_classes_timestamp 
    AFTER UPDATE ON classes
    BEGIN
        UPDATE classes SET updated_at = CURRENT_TIMESTAMP WHERE class_id = NEW.class_id;
    END;

CREATE TRIGGER update_class_sessions_timestamp 
    AFTER UPDATE ON class_sessions
    BEGIN
        UPDATE class_sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = NEW.session_id;
    END;

CREATE TRIGGER update_courses_timestamp 
    AFTER UPDATE ON courses
    BEGIN
        UPDATE courses SET updated_at = CURRENT_TIMESTAMP WHERE course_code = NEW.course_code;
    END;

CREATE TRIGGER update_lecturer_preferences_timestamp 
    AFTER UPDATE ON lecturer_preferences
    BEGIN
        UPDATE lecturer_preferences SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER update_settings_timestamp 
    AFTER UPDATE ON settings
    BEGIN
        UPDATE settings SET updated_at = CURRENT_TIMESTAMP WHERE setting_key = NEW.setting_key;
    END;