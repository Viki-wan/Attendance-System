# API Reference

Complete API documentation for the Face Recognition Attendance System REST API.

## Base URL

```
https://attendance.example.com/api/v1
```

## Authentication

Most endpoints require authentication. Include the authentication token in the request headers:

```
Authorization: Bearer <token>
```

### Getting a Token

**POST** `/api/v1/auth/login`

Request:
```json
{
  "username": "lecturer@example.com",
  "password": "password123"
}
```

Response:
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": "L2025001",
      "name": "John Doe",
      "email": "lecturer@example.com",
      "role": "lecturer"
    },
    "expires_in": 3600
  }
}
```

## Endpoints

### Authentication

#### Login
**POST** `/api/v1/auth/login`

Authenticate user and receive access token.

**Request Body:**
```json
{
  "username": "string",
  "password": "string",
  "remember_me": false
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "token": "string",
    "refresh_token": "string",
    "user": {
      "id": "string",
      "name": "string",
      "email": "string",
      "role": "string"
    },
    "expires_in": 3600
  }
}
```

#### Logout
**POST** `/api/v1/auth/logout`

Invalidate current token.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

#### Refresh Token
**POST** `/api/v1/auth/refresh`

Get new access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "string"
}
```

#### Get Profile
**GET** `/api/v1/auth/profile`

Get current user profile information.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "L2025001",
    "name": "John Doe",
    "email": "lecturer@example.com",
    "role": "lecturer",
    "instructor_id": "I001"
  }
}
```

#### Change Password
**POST** `/api/v1/auth/change-password`

Change user password.

**Request Body:**
```json
{
  "current_password": "string",
  "new_password": "string",
  "confirm_password": "string"
}
```

### Sessions

#### List Sessions
**GET** `/api/v1/sessions`

Get list of attendance sessions.

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `per_page` (int): Items per page (default: 20)
- `status` (string): Filter by status (scheduled, ongoing, completed)
- `date_from` (date): Start date filter
- `date_to` (date): End date filter

**Response:**
```json
{
  "success": true,
  "data": {
    "sessions": [
      {
        "session_id": 1,
        "class_id": "C001",
        "class_name": "Database Systems",
        "date": "2025-01-15",
        "start_time": "09:00:00",
        "end_time": "11:00:00",
        "status": "ongoing",
        "attendance_count": 45,
        "total_students": 50
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 100,
      "pages": 5
    }
  }
}
```

#### Get Session
**GET** `/api/v1/sessions/{session_id}`

Get detailed session information.

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": 1,
    "class_id": "C001",
    "class_name": "Database Systems",
    "date": "2025-01-15",
    "start_time": "09:00:00",
    "end_time": "11:00:00",
    "status": "ongoing",
    "attendance_count": 45,
    "total_students": 50,
    "attendance_rate": 90.0,
    "created_at": "2025-01-15T08:30:00Z",
    "updated_at": "2025-01-15T09:15:00Z"
  }
}
```

#### Create Session
**POST** `/api/v1/sessions`

Create a new attendance session.

**Request Body:**
```json
{
  "class_id": "C001",
  "date": "2025-01-20",
  "start_time": "09:00:00",
  "end_time": "11:00:00",
  "notes": "Optional session notes"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": 2,
    "message": "Session created successfully"
  }
}
```

#### Update Session
**PUT** `/api/v1/sessions/{session_id}`

Update session details.

**Request Body:**
```json
{
  "start_time": "09:30:00",
  "end_time": "11:30:00",
  "notes": "Updated notes"
}
```

#### Delete Session
**DELETE** `/api/v1/sessions/{session_id}`

Delete a session (only if not started).

#### Get Session Statistics
**GET** `/api/v1/sessions/{session_id}/statistics`

Get attendance statistics for a session.

**Response:**
```json
{
  "success": true,
  "data": {
    "total_students": 50,
    "present": 45,
    "absent": 3,
    "late": 2,
    "attendance_rate": 90.0,
    "on_time_rate": 90.0
  }
}
```

### Attendance

#### Get Session Attendance
**GET** `/api/v1/sessions/{session_id}/attendance`

Get attendance records for a session.

**Query Parameters:**
- `status` (string): Filter by status (Present, Absent, Late)
- `student_id` (string): Filter by student ID

**Response:**
```json
{
  "success": true,
  "data": {
    "attendance": [
      {
        "attendance_id": 1,
        "student_id": "S11/10067/25",
        "student_name": "John Smith",
        "status": "Present",
        "timestamp": "2025-01-15T09:05:00Z",
        "method": "face_recognition",
        "confidence": 0.95
      }
    ],
    "summary": {
      "total": 50,
      "present": 45,
      "absent": 3,
      "late": 2
    }
  }
}
```

#### Mark Attendance
**POST** `/api/v1/sessions/{session_id}/attendance`

Mark attendance for a student.

**Request Body:**
```json
{
  "student_id": "S11/10067/25",
  "status": "Present",
  "notes": "Optional notes"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "attendance_id": 1,
    "message": "Attendance marked successfully"
  }
}
```

#### Bulk Mark Attendance
**POST** `/api/v1/sessions/{session_id}/attendance/bulk`

Mark attendance for multiple students.

**Request Body:**
```json
{
  "student_ids": ["S11/10067/25", "S11/12085/24"],
  "status": "Present",
  "notes": "Bulk marking"
}
```

#### Update Attendance Record
**PUT** `/api/v1/attendance/{attendance_id}`

Update an attendance record.

**Request Body:**
```json
{
  "status": "Late",
  "notes": "Updated status"
}
```

#### Delete Attendance Record
**DELETE** `/api/v1/attendance/{attendance_id}`

Delete an attendance record.

### Students

#### List Students
**GET** `/api/v1/students`

Get list of students.

**Query Parameters:**
- `page` (int): Page number
- `per_page` (int): Items per page
- `search` (string): Search by name or student ID
- `course_code` (string): Filter by course

**Response:**
```json
{
  "success": true,
  "data": {
    "students": [
      {
        "student_id": "S11/10067/25",
        "name": "John Smith",
        "email": "john.smith@student.edu",
        "program": "Computer Science",
        "year_of_study": 3,
        "has_face_encoding": true
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 500
    }
  }
}
```

#### Get Student
**GET** `/api/v1/students/{student_id}`

Get detailed student information.

**Response:**
```json
{
  "success": true,
  "data": {
    "student_id": "S11/10067/25",
    "name": "John Smith",
    "email": "john.smith@student.edu",
    "phone": "+1234567890",
    "program": "Computer Science",
    "year_of_study": 3,
    "enrolled_courses": ["CS301", "CS302"],
    "has_face_encoding": true
  }
}
```

#### Get Student Attendance History
**GET** `/api/v1/students/{student_id}/attendance`

Get attendance history for a student.

**Query Parameters:**
- `course_code` (string): Filter by course
- `date_from` (date): Start date
- `date_to` (date): End date

**Response:**
```json
{
  "success": true,
  "data": {
    "student_id": "S11/10067/25",
    "attendance_records": [
      {
        "session_id": 1,
        "date": "2025-01-15",
        "course_code": "CS301",
        "status": "Present",
        "timestamp": "2025-01-15T09:05:00Z"
      }
    ],
    "statistics": {
      "total_sessions": 20,
      "present": 18,
      "absent": 1,
      "late": 1,
      "attendance_rate": 90.0
    }
  }
}
```

#### Get Student Statistics
**GET** `/api/v1/students/{student_id}/statistics`

Get attendance statistics for a student.

**Response:**
```json
{
  "success": true,
  "data": {
    "total_sessions": 20,
    "present": 18,
    "absent": 1,
    "late": 1,
    "attendance_rate": 90.0,
    "on_time_rate": 90.0,
    "by_course": {
      "CS301": {
        "total": 10,
        "present": 9,
        "rate": 90.0
      }
    }
  }
}
```

### Classes

#### List Classes
**GET** `/api/v1/classes`

Get list of classes.

**Query Parameters:**
- `instructor_id` (string): Filter by instructor
- `course_code` (string): Filter by course

**Response:**
```json
{
  "success": true,
  "data": {
    "classes": [
      {
        "class_id": "C001",
        "course_code": "CS301",
        "course_name": "Database Systems",
        "instructor_id": "I001",
        "instructor_name": "John Doe",
        "student_count": 50
      }
    ]
  }
}
```

#### Get Class
**GET** `/api/v1/classes/{class_id}`

Get detailed class information.

#### Get Class Roster
**GET** `/api/v1/classes/{class_id}/students`

Get list of students enrolled in a class.

#### Get Class Sessions
**GET** `/api/v1/classes/{class_id}/sessions`

Get all sessions for a class.

### Reports

#### Generate Session Report
**GET** `/api/v1/reports/session/{session_id}`

Generate attendance report for a session.

**Query Parameters:**
- `format` (string): Export format (json, csv, pdf)

**Response (JSON):**
```json
{
  "success": true,
  "data": {
    "session_id": 1,
    "date": "2025-01-15",
    "attendance": [...],
    "statistics": {...}
  }
}
```

**Response (CSV/PDF):**
Returns file download with appropriate content-type.

#### Generate Class Report
**GET** `/api/v1/reports/class/{class_id}`

Generate attendance report for all sessions in a class.

#### Generate Student Report
**GET** `/api/v1/reports/student/{student_id}`

Generate attendance report for a student.

#### Custom Report
**POST** `/api/v1/reports/generate`

Generate custom report with filters.

**Request Body:**
```json
{
  "type": "attendance",
  "date_from": "2025-01-01",
  "date_to": "2025-01-31",
  "filters": {
    "course_code": "CS301",
    "status": "Present"
  },
  "format": "pdf"
}
```

### Dashboard

#### Get Dashboard Statistics
**GET** `/api/v1/dashboard/stats`

Get dashboard overview statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "today_sessions": 5,
    "upcoming_sessions": 3,
    "total_students": 500,
    "attendance_rate": 85.5
  }
}
```

#### Get Today's Sessions
**GET** `/api/v1/dashboard/today-sessions`

Get sessions scheduled for today.

#### Get Upcoming Sessions
**GET** `/api/v1/dashboard/upcoming-sessions`

Get upcoming sessions.

## WebSocket Events

### Connection

Connect to WebSocket:
```javascript
const socket = io('https://attendance.example.com', {
  transports: ['websocket'],
  auth: {
    token: 'your-access-token'
  }
});
```

### Client → Server Events

#### Join Session
```javascript
socket.emit('join_session', {
  session_id: 1,
  user_id: 'L2025001'
});
```

#### Start Recognition
```javascript
socket.emit('start_recognition', {
  session_id: 1,
  user_id: 'L2025001'
});
```

#### Stop Recognition
```javascript
socket.emit('stop_recognition', {
  session_id: 1,
  user_id: 'L2025001'
});
```

#### Process Frame
```javascript
socket.emit('process_frame', {
  session_id: 1,
  user_id: 'L2025001',
  frame_data: 'data:image/jpeg;base64,...',
  timestamp: '2025-01-15T09:05:00Z',
  frame_number: 10
});
```

### Server → Client Events

#### Student Recognized
```javascript
socket.on('student_recognized', (data) => {
  // data: {
  //   session_id: 1,
  //   student_id: 'S11/10067/25',
  //   name: 'John Smith',
  //   confidence: 0.95,
  //   timestamp: '2025-01-15T09:05:00Z',
  //   bbox: { x: 0.2, y: 0.3, width: 0.1, height: 0.15 }
  // }
});
```

#### Face Detection Overlay
```javascript
socket.on('face_detection_overlay', (data) => {
  // data: {
  //   session_id: 1,
  //   faces: [
  //     {
  //       bbox: { x: 0.2, y: 0.3, width: 0.1, height: 0.15 },
  //       recognized: true,
  //       name: 'John Smith',
  //       student_id: 'S11/10067/25',
  //       confidence: 0.95
  //     }
  //   ],
  //   frame_width: 640,
  //   frame_height: 480
  // }
});
```

#### Attendance Marked
```javascript
socket.on('attendance_marked', (data) => {
  // data: {
  //   session_id: 1,
  //   student_id: 'S11/10067/25',
  //   student_name: 'John Smith',
  //   status: 'Present',
  //   confidence: 0.95
  // }
});
```

#### Session Progress
```javascript
socket.on('session_progress', (data) => {
  // data: {
  //   session_id: 1,
  //   present: 45,
  //   total: 50,
  //   percentage: 90.0
  // }
});
```

## Error Responses

All error responses follow this format:

```json
{
  "success": false,
  "message": "Error description",
  "error_code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  }
}
```

### Common Error Codes

- `AUTH_REQUIRED` (401): Authentication required
- `AUTH_INVALID` (401): Invalid credentials
- `FORBIDDEN` (403): Access denied
- `NOT_FOUND` (404): Resource not found
- `VALIDATION_ERROR` (400): Request validation failed
- `SERVER_ERROR` (500): Internal server error
- `RATE_LIMIT_EXCEEDED` (429): Too many requests

## Rate Limiting

- **Standard endpoints**: 100 requests per hour
- **Authentication endpoints**: 10 requests per 15 minutes
- **Token refresh**: 20 requests per hour

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
```

## Response Format

### Success Response
```json
{
  "success": true,
  "data": {},
  "message": "Optional message",
  "timestamp": "2025-01-15T09:05:00Z"
}
```

### Error Response
```json
{
  "success": false,
  "message": "Error message",
  "error_code": "ERROR_CODE",
  "details": {},
  "timestamp": "2025-01-15T09:05:00Z"
}
```

## Pagination

Paginated responses include pagination metadata:

```json
{
  "success": true,
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 100,
      "pages": 5,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

---

**For WebSocket implementation examples, see the frontend JavaScript files in `lec_panel/app/static/js/`**

