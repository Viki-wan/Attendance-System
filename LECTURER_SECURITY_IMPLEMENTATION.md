# Lecturer-Specific Data Access Security Implementation

## Overview

The attendance reporting system has been designed with **lecturer-specific data access** as a core security principle. Each lecturer can only access data for classes and courses they are assigned to, ensuring complete data isolation and security.

## 🔒 Security Implementation

### 1. **Session-Based Authentication**
```python
# Every route checks for valid instructor session
if 'instructor_id' not in session:
    return redirect(url_for('auth.login'))

instructor_id = session['instructor_id']
```

### 2. **Database-Level Security**
All database queries include instructor-specific filtering using proper JOINs:

#### **Courses Access**
```sql
-- Only courses assigned to the instructor
SELECT DISTINCT co.course_code, co.course_name, co.faculty
FROM courses co
JOIN instructor_courses ic ON co.course_code = ic.course_code
WHERE ic.instructor_id = ? AND co.is_active = 1
```

#### **Classes Access**
```sql
-- Only classes assigned to the instructor
SELECT DISTINCT c.class_id, c.class_name, c.course_code, c.year, c.semester
FROM classes c
JOIN class_instructors ci ON c.class_id = ci.class_id
WHERE ci.instructor_id = ? AND c.is_active = 1
```

#### **Students Access**
```sql
-- Only students enrolled in instructor's courses
SELECT DISTINCT s.student_id, s.fname || ' ' || s.lname AS name
FROM students s
JOIN student_courses sc ON s.student_id = sc.student_id
JOIN instructor_courses ic ON sc.course_code = ic.course_code
WHERE ic.instructor_id = ? AND s.is_active = 1 AND sc.status = 'Active'
```

#### **Attendance Data Access**
```sql
-- Only attendance for instructor's sessions
SELECT s.student_id, s.fname || ' ' || s.lname AS student_name, ...
FROM class_sessions cs
JOIN classes c ON cs.class_id = c.class_id
JOIN class_instructors ci ON cs.class_id = ci.class_id
JOIN student_courses sc ON c.course_code = sc.course_code
JOIN students s ON sc.student_id = s.student_id
LEFT JOIN attendance a ON a.student_id = s.student_id AND a.session_id = cs.session_id
WHERE ci.instructor_id = ? AND s.is_active = 1 AND sc.status = 'Active'
```

### 3. **API Endpoint Security**

#### **Course Validation**
```python
@reports_bp.route('/api/classes')
def api_get_classes():
    if 'instructor_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    instructor_id = session['instructor_id']
    course_code = request.args.get('course_code')
    
    # Validate that the course is assigned to the instructor
    if course_code:
        instructor_courses = report_service.get_instructor_courses(instructor_id)
        if not any(course['course_code'] == course_code for course in instructor_courses):
            return jsonify({"error": "Course not assigned to instructor"}), 403
```

#### **Session Access Validation**
```python
@reports_bp.route('/session/report/<int:session_id>')
def session_report(session_id):
    instructor_id = session['instructor_id']
    
    # Verify instructor has access to this session
    instructor_sessions = db_service.get_instructor_sessions(instructor_id)
    if not any(s['session_id'] == session_id for s in instructor_sessions):
        return "Session not assigned to you.", 403
```

### 4. **Service Layer Validation**

#### **Access Validation Method**
```python
def validate_instructor_access(self, instructor_id: int, course_code: str = None, 
                             class_id: str = None) -> bool:
    """Validate that instructor has access to the specified course/class"""
    try:
        if course_code:
            # Check if instructor is assigned to this course
            query = """
            SELECT 1 FROM instructor_courses 
            WHERE instructor_id = ? AND course_code = ?
            """
            self.cursor.execute(query, (instructor_id, course_code))
            if not self.cursor.fetchone():
                return False
        
        if class_id:
            # Check if instructor is assigned to this class
            query = """
            SELECT 1 FROM class_instructors 
            WHERE instructor_id = ? AND class_id = ?
            """
            self.cursor.execute(query, (instructor_id, class_id))
            if not self.cursor.fetchone():
                return False
        
        return True
    except Exception as e:
        logger.error(f"Error validating instructor access: {e}")
        return False
```

## 🛡️ Security Features

### **1. Multi-Layer Protection**
- **Session Layer**: Authentication check on every request
- **Route Layer**: Instructor ID validation
- **Service Layer**: Database query filtering
- **API Layer**: Additional validation for dynamic requests

### **2. Data Isolation**
- Instructors can only see their assigned courses
- Instructors can only see their assigned classes
- Instructors can only see students enrolled in their courses
- Instructors can only see attendance for their sessions

### **3. Input Validation**
- All user inputs are validated against instructor assignments
- Course codes are verified before use
- Class IDs are verified before use
- Session IDs are verified before access

### **4. Error Handling**
- Graceful handling of unauthorized access attempts
- Proper HTTP status codes (401, 403)
- Logging of security violations
- User-friendly error messages

## 🔍 Security Verification

### **Database Schema Requirements**
The security implementation relies on these key tables:

1. **`instructor_courses`** - Links instructors to courses
2. **`class_instructors`** - Links instructors to classes  
3. **`student_courses`** - Links students to courses
4. **`class_sessions`** - Links sessions to classes
5. **`attendance`** - Links attendance records to sessions

### **Query Verification**
Every query includes proper JOINs to ensure instructor-specific filtering:

```sql
-- Example: Getting instructor's classes
SELECT c.*, co.course_name
FROM classes c
JOIN class_instructors ci ON c.class_id = ci.class_id  -- Security JOIN
JOIN courses co ON c.course_code = co.course_code
WHERE ci.instructor_id = ? AND c.is_active = 1  -- Security WHERE clause
```

## 🚨 Security Considerations

### **1. Session Security**
- Instructor ID is stored in Flask session
- Session is validated on every request
- No direct instructor ID exposure in URLs

### **2. SQL Injection Prevention**
- All queries use parameterized statements
- No direct string concatenation in SQL
- Proper parameter binding

### **3. Access Control**
- No admin-level access from lecturer panel
- No cross-instructor data access
- No unauthorized session access

### **4. Data Integrity**
- Only active instructors can access data
- Only active courses/classes are shown
- Only active students are included

## 📊 Security Testing

### **Test Cases**
1. **Unauthorized Access**: Try accessing without login
2. **Cross-Instructor Access**: Try accessing another instructor's data
3. **Invalid Course Access**: Try accessing unassigned course
4. **Invalid Class Access**: Try accessing unassigned class
5. **Invalid Session Access**: Try accessing unassigned session

### **Expected Results**
- All unauthorized access attempts should return 401/403
- No data leakage between instructors
- Proper error messages
- Logging of security violations

## 🔧 Implementation Checklist

### **✅ Completed Security Measures**
- [x] Session-based authentication on all routes
- [x] Instructor-specific database queries
- [x] Course assignment validation
- [x] Class assignment validation
- [x] Session access validation
- [x] API endpoint security
- [x] Input validation
- [x] Error handling
- [x] Logging

### **✅ Security Features**
- [x] Multi-layer protection
- [x] Data isolation
- [x] Input validation
- [x] Proper error handling
- [x] SQL injection prevention
- [x] Access control
- [x] Data integrity checks

## 🎯 Conclusion

The attendance reporting system implements **comprehensive lecturer-specific data access security** with multiple layers of protection:

1. **Authentication**: Session-based login verification
2. **Authorization**: Instructor assignment validation
3. **Data Filtering**: Database-level instructor-specific queries
4. **API Security**: Additional validation for dynamic requests
5. **Input Validation**: Course/class assignment verification

This ensures that each lecturer can only access data for their assigned courses and classes, providing complete data isolation and security. The implementation follows security best practices and provides robust protection against unauthorized access attempts.








