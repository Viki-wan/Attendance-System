import sqlite3, sys
db = sys.argv[1] if len(sys.argv) > 1 else "attendance.db"
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)

def show(title, sql):
    print(f"\n== {title}\n{sql}")
    try:
        cur = con.execute(sql)
        print([d[0] for d in cur.description])
        for r in cur.fetchall():
            print(r)
    except Exception as e:
        print("ERROR", e)

def cols(t):
    return [r[1] for r in con.execute(f"PRAGMA table_info({t})")]

for t in ("student_courses", "students", "activity_log", "timetable", "settings"):
    show(f"schema {t}", f"SELECT sql FROM sqlite_master WHERE tbl_name='{t}'")

show("settings", "SELECT setting_key, setting_value, is_system FROM settings")
show("student_courses count", "SELECT COUNT(*) FROM student_courses")

sc, st = cols("student_courses"), cols("students")
g = [c for c in ("semester", "year", "status") if c in sc]
if g:
    k = ", ".join(g)
    show("student_courses by " + k, f"SELECT {k}, COUNT(*) FROM student_courses GROUP BY {k}")
    if "year" in sc:
        show("NULL-year rows", "SELECT COUNT(*) FROM student_courses WHERE year IS NULL")
g = [c for c in ("is_active", "status", "current_semester", "year_of_study") if c in st]
if g:
    k = ", ".join(g)
    show("students by " + k, f"SELECT {k}, COUNT(*) FROM students GROUP BY {k}")
if "student_id" in sc and "is_active" in st:
    show("active students with no student_courses row",
         "SELECT COUNT(*) FROM students s WHERE s.is_active=1 AND NOT EXISTS "
         "(SELECT 1 FROM student_courses c WHERE c.student_id=s.student_id)")
show("student_courses sample", "SELECT * FROM student_courses LIMIT 5")
show("classes by semester/year", "SELECT semester, year, COUNT(*) FROM classes GROUP BY semester, year")
show("timetable dates", "SELECT COUNT(*), MIN(effective_from), MAX(effective_to) FROM timetable")
show("activity types in use", "SELECT activity_type, COUNT(*) FROM activity_log GROUP BY activity_type")