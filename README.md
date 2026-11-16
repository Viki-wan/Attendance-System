# Face Recognition Attendance System

A comprehensive, multi-platform attendance management system with real-time face recognition capabilities. The system consists of three main interfaces: Admin Panel (PyQt5), Lecturer Portal (Flask Web), and Student Portal (Flask Web).

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

The Face Recognition Attendance System is a modern solution for automating student attendance tracking in educational institutions. It uses advanced face recognition technology to identify students and record attendance automatically, reducing manual work and improving accuracy.

### Key Highlights

- **Real-time Face Recognition**: Process live video feeds with bounding boxes and labels
- **Multi-Platform**: Admin desktop application (PyQt5) + Web portals (Flask)
- **Scalable Architecture**: Celery for background processing, Redis for caching
- **WebSocket Support**: Real-time updates using Flask-SocketIO
- **Automatic Attendance Marking**: Mark students present based on face recognition
- **Comprehensive Reporting**: Generate detailed attendance reports and statistics

## ✨ Features

### 🔧 Admin Panel (PyQt5 Desktop Application)

The admin panel is a feature-rich desktop application for system administrators.

#### Core Features

- **Student Registration**
  - Register new students with profile information
  - Capture student photos via webcam
  - Automatic face encoding generation
  - Support for bulk student import
  - Image validation and quality checks

- **Attendance Management**
  - Start and manage attendance sessions
  - Real-time face recognition with detection rectangles
  - Review unknown faces detected during sessions
  - Manual attendance corrections
  - View attendance history and statistics

- **Academic Resource Management**
  - Manage courses, classes, and instructors
  - Create and assign class sessions
  - Bulk operations for data management
  - Course-instructor assignments

- **Settings & Configuration**
  - Adjust face recognition sensitivity
  - Configure recognition thresholds
  - Theme customization (light/dark mode)
  - Auto-logout configuration
  - System preferences

- **Reports & Analytics**
  - Generate attendance reports (PDF, CSV, Excel)
  - View attendance statistics and trends
  - Export data for external analysis
  - Attendance history tracking

- **Security**
  - Secure login with attempt tracking
  - Session management
  - Activity logging
  - Access control
 
<img width="1366" height="768" alt="Screenshot (132)" src="https://github.com/user-attachments/assets/373becad-d251-4bbd-a3f1-76fa2a4fc5a2" />
<img width="1366" height="768" alt="Screenshot (133)" src="https://github.com/user-attachments/assets/a7ddd467-7b59-4974-94ba-538b06c30ad3" />
<img width="1366" height="768" alt="Screenshot (163)" src="https://github.com/user-attachments/assets/1824ae0a-5c72-4324-9e03-892255e07b80" />
<img width="1366" height="768" alt="Screenshot (165)" src="https://github.com/user-attachments/assets/799ed6c0-6c23-434c-9afd-f561307fbcaf" />



### 👨‍🏫 Lecturer Portal (Flask Web Application)

A modern web-based interface for lecturers to manage their classes and sessions.

#### Core Features

- **Dashboard**
  - Overview of upcoming sessions
  - Quick access to recent activities
  - Attendance statistics summary
  - Course and class information

    <img width="1366" height="768" alt="Screenshot (212)" src="https://github.com/user-attachments/assets/e079ad4a-d49d-442e-943e-809aa431da9c" />


- **Live Attendance Capture**
  - Real-time face recognition via browser camera
  - Visual detection rectangles over detected faces
  - Automatic student recognition and marking
  - Manual attendance override options
  - Session progress tracking

- **Session Management**
  - Create and schedule attendance sessions
  - Start/stop sessions
  - View session history
  - Edit session details
  - Session status tracking (scheduled, ongoing, completed)

- **Student Management**
  - View enrolled students
  - Filter by course/class
  - Search functionality
  - Student profile preview
  - Bulk marking operations

- **Reports & Statistics**
  - Attendance reports per session
  - Attendance reports per student
  - Export to CSV/PDF
  - Visual charts and graphs
  - Attendance trends analysis
 
    <img width="1366" height="768" alt="Screenshot (214)" src="https://github.com/user-attachments/assets/f15d8fbd-2db6-4030-aebc-b475ed74cc62" />
    


- **Preferences**
  - Notification settings
  - Email preferences
  - Display preferences
  - Recognition settings

### 👨‍🎓 Student Portal (Flask Web Application)

A student-facing web portal for viewing attendance records.

#### Core Features

- **Dashboard**
  - Personal attendance overview
  - Upcoming class sessions
  - Attendance statistics
  - Recent attendance records

- **Attendance History**
  - View attendance for enrolled courses
  - Filter by date, course, or status
  - Detailed attendance records
  - Attendance percentage per course

- **Course Information**
  - View enrolled courses
  - Course details and schedules
  - Instructor information
  - Class timetables

- **Profile Management**
  - Update personal information
  - Change email and contact details
  - View profile photo
  - Account settings

## 🛠 Technology Stack

### Backend

- **Python 3.8+**
- **Flask 2.0+**: Web framework for lecturer and student portals
- **PyQt5 5.15+**: Desktop application framework for admin panel
- **SQLAlchemy**: Database ORM
- **SQLite**: Database (can be configured for PostgreSQL/MySQL)
- **Celery**: Asynchronous task processing
- **Redis**: Caching and message broker
- **Flask-SocketIO**: WebSocket support for real-time features

### Face Recognition

- **face_recognition**: Face detection and recognition library
- **OpenCV (cv2)**: Image processing and computer vision
- **dlib**: Face detection backend
- **numpy**: Numerical operations
- **PIL/Pillow**: Image manipulation

### Frontend

- **JavaScript (ES6+)**: Client-side interactivity
- **Bootstrap 5**: Responsive UI framework
- **Socket.IO Client**: Real-time communication
- **Canvas API**: Video rendering and overlay drawing
- **WebRTC**: Camera access

### Additional Libraries

- **Flask-Login**: User session management
- **Flask-Mail**: Email notifications
- **Werkzeug**: WSGI utilities and password hashing
- **Jinja2**: Template engine
- **python-dotenv**: Environment variable management

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Redis server (for caching and Celery)
- Webcam (for face recognition)
- Git (optional, for cloning the repository)

### Step 1: Clone the Repository

```bash
git clone https://github.com/Viki-wan/attendance-system.git
cd attendance-system
```

### Step 2: Create Virtual Environment

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Note**: For `dlib` and `opencv-contrib-python`, you may need prebuilt wheels:

```bash
# For Python 3.12 (Windows)
pip install --only-binary=:all: numpy opencv-contrib-python dlib face_recognition
```

### Step 4: Install Redis

**Windows:**
- Download from [Redis for Windows](https://github.com/microsoftarchive/redis/releases)
- Or use WSL: `wsl sudo apt-get install redis-server`

**Linux:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

**Mac:**
```bash
brew install redis
brew services start redis
```

### Step 5: Database Setup

The database will be created automatically on first run. To initialize manually:

```bash
cd lec_panel
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

### Step 6: Environment Configuration

Create a `.env` file in the project root (optional, defaults will be used):

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_CONFIG=development
DEBUG=True

# Database
DATABASE_URL=sqlite:///attendance.db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Email (optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Face Recognition
FACE_RECOGNITION_TOLERANCE=0.6
FACE_RECOGNITION_MODEL=hog

# Server
PORT=8080
HOST=127.0.0.1
```

## ⚙️ Configuration

### Admin Panel Configuration

Edit `config/utils_constants.py` or use the settings window in the admin panel:

- Face recognition sensitivity
- Auto-logout timeout
- Theme preferences
- Database path

### Lecturer Portal Configuration

Configuration is managed through `lec_panel/config/config.py`:

- **Development**: Basic settings for local development
- **Production**: Optimized for production deployment
- **Testing**: Settings for automated testing

### Key Configuration Files

- `lec_panel/config/config.py`: Main Flask configuration
- `config/utils_constants.py`: Admin panel constants
- `.env`: Environment variables (create as needed)

## 📁 Project Structure

```
attendance-system/
├── admin/                          # Admin Panel (PyQt5)
│   ├── admin_dashboard.py         # Main admin application
│   ├── register_student.py        # Student registration
│   ├── view_attendance.py         # Attendance viewing
│   ├── start_attendance_window.py # Session management
│   ├── review_unknown_window.py   # Unknown faces review
│   ├── settings_window.py         # Settings
│   ├── academic_resources/        # Academic management
│   └── ...
│
├── lec_panel/                      # Lecturer Portal (Flask)
│   ├── app/
│   │   ├── __init__.py            # Flask app factory
│   │   ├── models/                # Database models
│   │   ├── routes/                # Route handlers
│   │   │   ├── lecturer/          # Lecturer routes
│   │   │   └── api/               # REST API
│   │   ├── services/              # Business logic
│   │   │   ├── face_recognition_service.py
│   │   │   ├── camera_service.py
│   │   │   └── session_service.py
│   │   ├── tasks/                 # Celery tasks
│   │   │   └── face_processing.py
│   │   ├── static/                # Static files
│   │   │   ├── js/
│   │   │   │   ├── attendance_realtime.js
│   │   │   │   ├── camera_handler.js
│   │   │   │   └── face_overlay_handler.js
│   │   │   └── css/
│   │   └── templates/             # Jinja2 templates
│   ├── config/
│   │   └── config.py              # Configuration
│   ├── celery_worker.py           # Celery worker entry
│   └── run.py                     # Flask app entry
│
├── student_portal/                 # Student Portal (Flask)
│   ├── routes/                    # Student routes
│   ├── templates/                 # Student templates
│   └── models/                    # Student models
│
├── config/                         # Shared configuration
│   ├── utils_constants.py
│   └── ...
│
├── face_encodings/                 # Face encoding files
├── student_images/                 # Student photos
├── uploads/                        # Uploaded files
├── backups/                        # Database backups
├── logs/                           # Application logs
│
├── requirements.txt                # Python dependencies
├── README.md                       # This file
└── .env                           # Environment variables (create)
```

## 🚀 Usage

### Starting the Lecturer Portal

1. **Activate virtual environment:**
   ```bash
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```

2. **Start Redis:**
   ```bash
   redis-server
   ```

3. **Start Celery Worker** (in a separate terminal):
   ```bash
   cd lec_panel
   python -m celery -A celery_worker.celery worker --loglevel=info --pool=solo
   ```

4. **Start Flask Application:**
   ```bash
   cd lec_panel
   python run.py
   ```

5. **Access the application:**
   - Open browser to `http://127.0.0.1:8080`
   - Login with lecturer credentials

### Starting the Admin Panel

1. **Activate virtual environment:**
   ```bash
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```

2. **Run admin dashboard:**
   ```bash
   python admin/admin_dashboard.py
   ```

   Or use the entry point:
   ```bash
   python main.py
   ```

### Starting the Student Portal

1. **Navigate to student portal:**
   ```bash
   cd student_portal
   ```

2. **Run Flask app:**
   ```bash
   python app.py
   ```

3. **Access at:**
   - Default: `http://127.0.0.1:5000` (or configured port)

### Face Recognition Workflow

1. **Admin registers students** with photos via admin panel
2. **System generates face encodings** automatically
3. **Lecturer starts a session** via web portal
4. **Camera captures frames** from browser
5. **Frames sent to backend** via WebSocket
6. **Celery processes frames** asynchronously
7. **Face recognition** identifies students
8. **Attendance marked automatically**
9. **Real-time updates** sent to lecturer interface
10. **Detection rectangles** displayed on video feed

## 📚 API Documentation

### REST API Endpoints

Base URL: `/api/v1`

#### Authentication
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/logout` - Logout
- `GET /api/v1/auth/me` - Get current user

#### Sessions
- `GET /api/v1/sessions` - List sessions
- `POST /api/v1/sessions` - Create session
- `GET /api/v1/sessions/{id}` - Get session details
- `PUT /api/v1/sessions/{id}` - Update session
- `DELETE /api/v1/sessions/{id}` - Delete session

#### Attendance
- `GET /api/v1/attendance` - Get attendance records
- `POST /api/v1/attendance` - Mark attendance
- `GET /api/v1/attendance/{session_id}` - Get session attendance

#### Students
- `GET /api/v1/students` - List students
- `GET /api/v1/students/{id}` - Get student details

### WebSocket Events

#### Client → Server
- `join_session` - Join an attendance session
- `start_recognition` - Start face recognition
- `stop_recognition` - Stop face recognition
- `process_frame` - Send frame for processing

#### Server → Client
- `student_recognized` - Student identified
- `face_detection_overlay` - Face detection data with bounding boxes
- `attendance_marked` - Attendance recorded
- `session_progress` - Session statistics update

## 🔧 Development

### Running Tests

```bash
pytest tests/
```

### Database Migrations

Using Flask-Migrate:

```bash
cd lec_panel
flask db init
flask db migrate -m "Description"
flask db upgrade
```

### Code Style

Follow PEP 8 guidelines. Consider using:

```bash
pip install black flake8
black .
flake8 .
```

### Debugging

Enable debug mode in `.env`:
```env
DEBUG=True
FLASK_CONFIG=development
```

View logs in `logs/app.log` or console output.



### Contribution Guidelines

- Follow PEP 8 style guide
- Write clear commit messages
- Add tests for new features
- Update documentation as needed
- Ensure all tests pass before submitting


## 🆘 Support

For issues, questions, or contributions:

- Open an issue on GitHub
- Check existing documentation
- Review code comments and docstrings

## 🙏 Acknowledgments

- `face_recognition` library by Adam Geitgey
- Flask and PyQt5 communities
- All contributors and testers

## 📄 Additional Documentation

- [Face Recognition Setup Guide](docs/FACE_RECOGNITION_SETUP.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [API Reference](docs/API.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

---

**Built with ❤️ for educational institutions**




