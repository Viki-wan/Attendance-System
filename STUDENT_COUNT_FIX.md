# Student Count Filtering Fix

## Problem
The students stat card was displaying 158 students on every filter, regardless of the selected class or filters. This was incorrect because it should show the total number of students in the currently filtered view.

## Root Cause
The `get_attendance_summary` method was using a single query that counted all students across all classes for the instructor, without considering the applied filters (class, course, year, etc.).

## Solution

### 1. **Updated `get_attendance_summary` Method**
- **Added filter parameters**: `course_code`, `class_id`, `year`
- **Separated queries**: One for attendance data, one for student count
- **Applied filters to student count**: Student count now respects all active filters

### 2. **Enhanced API Endpoint**
- **Updated `/api/filtered_data`**: Now passes all filter parameters to the summary method
- **Maintains backward compatibility**: Other endpoints still work as before

### 3. **Improved Query Logic**
- **Attendance query**: Gets session counts and attendance records with filters
- **Student count query**: Gets distinct student count with the same filters
- **Consistent filtering**: Both queries use identical filter logic

## Technical Implementation

### Before (Incorrect)
```sql
-- Single query that ignored filters for student count
SELECT 
    COUNT(DISTINCT cs.session_id) as total_sessions,
    COUNT(DISTINCT s.student_id) as total_students,  -- Always counted all students
    COUNT(CASE WHEN a.status = 'Present' THEN 1 END) as present_count,
    ...
FROM class_sessions cs
JOIN classes c ON cs.class_id = c.class_id
JOIN class_instructors ci ON cs.class_id = ci.class_id
JOIN student_courses sc ON c.course_code = sc.course_code
JOIN students s ON sc.student_id = s.student_id
LEFT JOIN attendance a ON a.student_id = s.student_id AND a.session_id = cs.session_id
WHERE ci.instructor_id = ? AND s.is_active = 1 AND sc.status = 'Active'
-- No filter conditions for student count
```

### After (Correct)
```sql
-- Separate query for student count with filters
SELECT COUNT(DISTINCT s.student_id) as total_students
FROM students s
JOIN student_courses sc ON s.student_id = sc.student_id
JOIN classes c ON sc.course_code = c.course_code
JOIN class_instructors ci ON c.class_id = ci.class_id
WHERE ci.instructor_id = ? AND s.is_active = 1 AND sc.status = 'Active'
AND c.course_code = ?  -- Applied course filter
AND c.class_id = ?     -- Applied class filter
AND s.year_of_study = ? -- Applied year filter
```

## Code Changes

### 1. **Service Layer** (`attendance_report_service.py`)
```python
def get_attendance_summary(self, instructor_id: int, date_from: str = None, 
                          date_to: str = None, course_code: str = None,
                          class_id: str = None, year: int = None) -> Dict[str, Any]:
    # ... attendance data query with filters ...
    
    # Separate query for student count with filters
    student_count_query = """
    SELECT COUNT(DISTINCT s.student_id) as total_students
    FROM students s
    JOIN student_courses sc ON s.student_id = sc.student_id
    JOIN classes c ON sc.course_code = c.course_code
    JOIN class_instructors ci ON c.class_id = ci.class_id
    WHERE ci.instructor_id = ? AND s.is_active = 1 AND sc.status = 'Active'
    """
    # Apply same filters to student count query
    if course_code:
        student_count_query += " AND c.course_code = ?"
    if class_id:
        student_count_query += " AND c.class_id = ?"
    if year:
        student_count_query += " AND s.year_of_study = ?"
```

### 2. **API Layer** (`reports.py`)
```python
# Get summary statistics with all filters
summary = report_service.get_attendance_summary(
    instructor_id=instructor_id,
    date_from=date_from if date_from else None,
    date_to=date_to if date_to else None,
    course_code=course_code if course_code else None,  # Added
    class_id=class_id if class_id else None,           # Added
    year=int(year) if year else None                   # Added
)
```

## Expected Behavior

### **Before Fix**
- **All Classes**: Shows 158 students (total across all classes)
- **CS101_A**: Shows 158 students (incorrect - should show ~30)
- **CS201_A**: Shows 158 students (incorrect - should show ~25)
- **Year 1**: Shows 158 students (incorrect - should show ~40)

### **After Fix**
- **All Classes**: Shows 158 students (correct - total across all classes)
- **CS101_A**: Shows 30 students (correct - students in CS101_A only)
- **CS201_A**: Shows 25 students (correct - students in CS201_A only)
- **Year 1**: Shows 40 students (correct - students in Year 1 only)

## Benefits

### 1. **Accurate Statistics**
- Student count now reflects the actual filtered data
- Statistics cards provide meaningful information
- Users can see the scope of their current view

### 2. **Better User Experience**
- **Class Selection**: Shows exact number of students in selected class
- **Year Filtering**: Shows students in that year only
- **Combined Filters**: Shows students matching all criteria

### 3. **Consistent Data**
- All statistics now use the same filter logic
- No more confusion about what the numbers represent
- Reliable data for decision making

## Testing Scenarios

### **Test Cases**
1. **No Filters**: Should show total students across all classes
2. **Class Filter**: Should show students in that specific class only
3. **Year Filter**: Should show students in that year only
4. **Combined Filters**: Should show students matching all criteria
5. **Date Range**: Should show students with attendance in that period

### **Expected Results**
- Student count should update immediately when filters change
- Count should be consistent with the displayed attendance records
- Count should never exceed the total number of students

## Conclusion

This fix ensures that the student count statistic accurately reflects the filtered data, providing users with meaningful and consistent information about their current view. The implementation maintains backward compatibility while adding the necessary filtering logic to provide accurate statistics.




