# Admin Web Panel — AI Build Brief

> **Purpose:** Give any AI assistant (Claude, ChatGPT, etc.) full context to help build the admin panel inside `lec_panel` — even with zero prior knowledge of this project.
>
> **Last updated:** 2026-07-10  
> **Update this file** as you complete each phase (check boxes, fill "Current task").

---

## How to use this document

1. Start a **new AI chat** for each major phase.
2. Paste this entire document (or link to it).
3. Attach the **reference files** listed for the current phase.
4. End with a scoped task: *"Implement Phase X only. Output complete file contents."*
5. After implementing, update the **Implementation status** section below.

### Minimal starter prompt

```text
I'm building an admin web panel inside an existing Flask app (lec_panel).
You have no prior context. I'm attaching ADMIN_BUILD_BRIEF.md plus reference files.

Task: [Phase N — describe scope]
Match existing lecturer conventions exactly.
Output complete files, not snippets. List all files created/changed.
Do not create a separate Flask app. Do not use raw sqlite3.
```

---

## Project overview

**Face Recognition Attendance System** — a campus attendance platform with three user roles:

| Role | Interface | Status |
|------|-----------|--------|
| Admin | Web (to be built in `lec_panel`) | **Not started** |
| Lecturer | Web (`lec_panel`) | **Implemented** |
| Student | Web (`student_portal` — separate app, same DB) | Partial |

### Background / why admin is web now

- An earlier **PyQt desktop admin** (`admin/` at project root) was a working prototype with face recognition.
- The project expanded to lecturer + student web panels sharing `attendance.db`.
- Schema evolved on the web side; PyQt admin used raw SQL and **stopped working**.
- **Decision:** Build admin inside `lec_panel` (same Flask app, same SQLAlchemy models) — do not revive PyQt.

---

## Technology stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.8+ |
| Web framework | Flask (app factory pattern) |
| ORM | Flask-SQLAlchemy |
| Migrations | Flask-Migrate (Alembic) — set up if not yet initialized |
| Auth | Flask-Login |
| Templates | Jinja2 + Bootstrap 5 |
| Database | SQLite — `attendance.db` at **project root** |
| Face recognition | `face_recognition`, OpenCV — via existing services |
| Background tasks | Celery + Redis (optional) |
| Entry point | `lec_panel/run.py` → `python run.py` |

---

## Project layout

```
attendance system/                    # project root
├── attendance.db                     # shared SQLite database
├── new_schema.sql                    # reference schema (may drift from models)
├── admin/                            # LEGACY PyQt desktop — reference only, DO NOT extend
│   ├── admin_dashboard.py
│   ├── register_student.py
│   ├── academic_resources/           # instructor, student, course, class, session managers
│   ├── settings_window.py
│   └── view_attendance.py
├── student_portal/                   # separate Flask app (future: merge into lec_panel)
└── lec_panel/                        # THE web app — extend this for admin
    ├── run.py                        # python run.py (port 8080 default)
    ├── config/
    │   ├── config.py                 # BASE_DIR, DB_PATH, upload folders
    │   └── constants.py            # UserType, ActivityType, SessionStatus, etc.
    ├── docs/
    │   └── ADMIN_BUILD_BRIEF.md      # this file
    └── app/
        ├── __init__.py               # create_app(), register_blueprints(), user_loader
        ├── models/                   # SQLAlchemy models — schema source of truth
        ├── routes/
        │   ├── auth.py               # lecturer login today
        │   ├── help.py
        │   ├── lecturer/             # EXISTING — copy patterns from here
        │   └── admin/                # TO CREATE — mirror lecturer/ structure
        ├── services/                 # business logic — not in routes
        ├── decorators/auth.py        # @admin_required (placeholder), @instructor_required, etc.
        ├── templates/
        │   ├── base.html
        │   ├── partials/
        │   ├── lecturer/             # EXISTING — copy UI patterns
        │   └── admin/                # TO CREATE
        └── static/
            └── js/                   # camera_handler.js exists for lecturer
```

### Where admin code goes (critical)

| Put here | Do NOT put here |
|----------|-----------------|
| `lec_panel/app/routes/admin/` | `lec_panel/admin/` (separate app) |
| `lec_panel/app/templates/admin/` | Root `admin/` folder (that's PyQt legacy) |
| `lec_panel/app/services/admin_*.py` | `admin_panel/` sibling folder |
| Register blueprints in `app/__init__.py` | New Flask application |

---

## Architecture rules (MUST follow)

1. **One Flask app** — extend `lec_panel`, same `attendance.db`, same models.
2. **URL prefix** — admin uses `/admin/...`; lecturer uses `/lecturer/...`.
3. **Thin routes, fat services** — routes call services; services use models.
4. **SQLAlchemy only** — no raw `sqlite3` in admin code.
5. **Every admin route** — `@login_required` + `@admin_required`.
6. **Activity logging** — log create/update/delete via `ActivityLog` with `user_type='admin'`.
7. **Admin sees all data** — no `instructor_id` filtering (unlike lecturer routes).
8. **Reuse existing services** — `AuthService`, `FaceRecognitionService`, `SchedulingService`, `ReportService`, etc.
9. **One phase per task** — do not big-bang the entire admin panel in one shot.
10. **Schema changes** — update `app/models/` first; run `flask db migrate` if using migrations.

---

## Existing SQLAlchemy models

Exported from `app/models/__init__.py`:

| Model | Table | Notes |
|-------|-------|-------|
| `Instructor` | `instructors` | Flask-Login user today |
| `Student` | `students` | Includes `face_encoding` BLOB |
| `Course` | `courses` | |
| `StudentCourse` | `student_courses` | Enrollment junction |
| `Class` | `classes` | |
| `ClassInstructor` | `class_instructors` | Lecturer-class assignment |
| `ClassSession` | `class_sessions` | Scheduled/ongoing/completed sessions |
| `Attendance` | `attendance` | Per student per session |
| `Timetable` | `timetable` | Recurring schedule (day_of_week, times) |
| `Holiday` | `holidays` | Skip on session generation |
| `Settings` | `settings` | Key-value system config |
| `ActivityLog` | `activity_log` | Audit trail |
| `Notification` | `notifications` | |
| `SessionDismissal` | `session_dismissals` | |
| `LecturerPreference` | `lecturer_preferences` | |
| `SystemMetric` | `system_metrics` | |

### Admin model — NOT YET IMPLEMENTED

The `admin` table exists in the database:

```sql
CREATE TABLE admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);
```

CLI command `flask create-admin` in `app/__init__.py` references `Admin` model, but **`Admin` is not defined in `app/models/user.py` yet**.

---

## Existing lecturer routes (patterns to copy)

| Blueprint | File | URL prefix |
|-----------|------|------------|
| `dashboard` | `routes/lecturer/dashboard.py` | `/lecturer/dashboard` |
| `lecturer_sessions` | `routes/lecturer/sessions.py` | `/lecturer/sessions` |
| `lecturer_attendance` | `routes/lecturer/attendance.py` | `/lecturer/attendance` |
| `reports` | `routes/lecturer/reports.py` | `/lecturer/reports` |
| `preferences` | `routes/lecturer/preferences.py` | `/lecturer/preferences` |
| `timetable` | `routes/lecturer/timetable.py` | `/lecturer/timetable` |
| `dismissals` | `routes/lecturer/dismissals.py` | `/lecturer/dismissals` |
| `auth` | `routes/auth.py` | `/auth` |

### Route pattern template

```python
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.decorators.auth import admin_required
from app.models.activity_log import ActivityLog
from config.constants import UserType, ActivityType

admin_xxx_bp = Blueprint('admin_xxx', __name__, url_prefix='/admin/xxx')


@admin_xxx_bp.route('/')
@login_required
@admin_required
def index():
    # Call service layer — no heavy logic here
    return render_template('admin/xxx/index.html')
```

### Lecturer route example (reference)

```python
# lec_panel/app/routes/lecturer/sessions.py
sessions_bp = Blueprint('lecturer_sessions', __name__, url_prefix='/lecturer/sessions')

@sessions_bp.route('/')
@login_required
@active_account_required
def list_sessions():
    sessions, total_count = session_service.get_instructor_sessions(
        instructor_id=current_user.instructor_id,  # ← admin version omits this filter
        ...
    )
```

---

## Existing services (reuse in admin)

| Service | File | Admin use |
|---------|------|-----------|
| `AuthService` | `services/auth_service.py` | `create_instructor()`, `reset_password()` |
| `DashboardService` | `services/dashboard_service.py` | Adapt for campus-wide stats |
| `SessionService` | `services/session_service.py` | Campus session oversight |
| `SchedulingService` | `services/scheduling_service.py` | Timetable → bulk session generation |
| `FaceRecognitionService` | `services/face_recognition_service.py` | Student registration encoding |
| `ReportService` | `services/report_service.py` | Campus-wide reports (no instructor filter) |
| `NotificationService` | `services/notification_service.py` | System notifications |
| `CameraService` | `services/camera_service.py` | Webcam capture (lecturer; reusable for admin registration) |

### New services to create

| Service | Purpose |
|---------|---------|
| `admin_service.py` | Dashboard stats, general admin orchestration |
| `lecturer_admin_service.py` | Lecturer CRUD + course/class assignments |
| `student_admin_service.py` | Student registration, enrollment, face capture |
| `timetable_admin_service.py` | Campus timetable CRUD + conflict detection |

---

## Auth system — current state and target

### Current (lecturer only)

- `user_loader` in `app/__init__.py` loads **Instructor only**.
- `auth.py` login redirects to `dashboard.index` (lecturer).
- `@admin_required` in `decorators/auth.py` is a **placeholder that always returns 403**.

### Target (multi-role)

| Concern | Implementation |
|---------|----------------|
| User IDs | `admin:1`, `instructor:L2025003` (prefixed strings in `get_id()`) |
| `user_loader` | Parse prefix → load `Admin` or `Instructor` |
| `user_type` property | `UserType.ADMIN` or `UserType.INSTRUCTOR` on each model |
| Login | Admin: username + password; Lecturer: identifier + password (existing) |
| Redirect after login | Admin → `/admin/dashboard`; Lecturer → `/lecturer/dashboard` |
| `@admin_required` | Check `current_user.user_type == UserType.ADMIN` |
| Create admin | `flask create-admin` CLI (already stubbed in `__init__.py`) |

### Constants (`config/constants.py`)

```python
class UserType:
    ADMIN = 'admin'
    INSTRUCTOR = 'instructor'
    STUDENT = 'student'
```

---

## PyQt admin → Web admin feature map

Use PyQt files as **feature specs only** — port behavior, not code.

| PyQt file (legacy `admin/`) | Web admin target | Notes |
|-----------------------------|------------------|-------|
| `login_window.py` | `routes/auth.py` | Extend for admin login |
| `home.py` | `routes/admin/dashboard.py` | Campus-wide stats |
| `register_student.py` | `routes/admin/students.py` | Webcam + face encoding |
| `academic_resources/instructor_manager.py` | `routes/admin/lecturers.py` | CRUD + assignments |
| `academic_resources/student_manager.py` | `routes/admin/students.py` | List, filter, enroll |
| `academic_resources/manage_courses.py` | `routes/admin/courses.py` | Course CRUD |
| `academic_resources/class_manager.py` | `routes/admin/courses.py` | Class CRUD |
| `academic_resources/session_manager.py` | `routes/admin/sessions.py` | Campus session oversight |
| `academic_resources/get_stats.py` | `services/admin_service.py` | Dashboard metrics |
| `view_attendance.py` | `routes/admin/attendance.py` | All-campus reports |
| `review_unknown_window.py` | `routes/admin/attendance.py` | Unknown faces review |
| `settings_window.py` | `routes/admin/settings.py` | System settings |
| `start_attendance_window.py` | — | **Stays with lecturer** |
| `webcam_window.py` | — | **Stays with lecturer** |

### Timetable ownership

- **Admin** owns campus-wide master timetable (`/admin/timetable`).
- **Lecturer** timetable routes (`/lecturer/timetable`) should become **view-only** eventually.
- Reuse `SchedulingService.create_sessions_from_timetable()` for bulk session generation.

---

## Build phases

### Phase 0 — Foundation

- [ ] Add `Admin` model to `app/models/user.py`
- [ ] Export `Admin` from `app/models/__init__.py`
- [ ] Update `user_loader` for multi-role (`admin:id`, `instructor:id`)
- [ ] Implement `@admin_required` (replace 403 placeholder)
- [ ] Extend `auth.py` — admin login + role-based redirect
- [ ] Create `routes/admin/dashboard.py` — empty welcome page
- [ ] Create `templates/admin/dashboard.html`
- [ ] Register admin blueprint in `app/__init__.py`
- [ ] Update `/` index redirect for admin vs lecturer
- [ ] Verify `flask create-admin` works

**Done when:** Admin can log in and see `/admin/dashboard`.

---

### Phase 1 — Admin shell + dashboard stats

- [ ] `templates/admin/base_admin.html` (admin navbar/sidebar)
- [ ] `partials/_navbar_admin.html`
- [ ] Dashboard cards: students, lecturers, courses, classes, today's sessions
- [ ] Recent activity from `ActivityLog`
- [ ] `services/admin_service.py`

**Done when:** Dashboard shows real counts from DB.

---

### Phase 2 — Lecturer management

- [ ] `routes/admin/lecturers.py`
- [ ] `services/lecturer_admin_service.py`
- [ ] List, create, edit, deactivate lecturers
- [ ] Reset password (reuse `AuthService.reset_password`)
- [ ] Assign courses (`instructor_courses`) and classes (`class_instructors`)
- [ ] Templates: `templates/admin/lecturers/`

**Done when:** Created lecturer can log into lecturer panel and see assigned data.

---

### Phase 3 — Student management + face registration

- [ ] `routes/admin/students.py`
- [ ] `services/student_admin_service.py`
- [ ] List, create, edit, deactivate students
- [ ] Enroll in courses (`student_courses`)
- [ ] Webcam capture + face encoding (reuse `FaceRecognitionService`, `camera_handler.js`)
- [ ] Templates: `templates/admin/students/`

**Done when:** Registered student has `face_encoding` and appears in lecturer attendance.

---

### Phase 4 — Courses and classes

- [ ] `routes/admin/courses.py`
- [ ] Course CRUD
- [ ] Class CRUD (linked to course)
- [ ] Assign lecturers to classes
- [ ] Templates: `templates/admin/courses/`

**Done when:** Full chain works: course → class → lecturer → student.

---

### Phase 5 — Campus timetable

- [ ] `routes/admin/timetable.py`
- [ ] `services/timetable_admin_service.py`
- [ ] Timetable CRUD with conflict detection
- [ ] Holiday management
- [ ] Bulk session generation for semester (`SchedulingService`)
- [ ] Templates: `templates/admin/timetable/`

**Done when:** Admin generates semester sessions; lecturers see them in dashboard.

---

### Phase 6 — Attendance oversight

- [ ] `routes/admin/attendance.py`
- [ ] Campus-wide attendance view (no instructor filter)
- [ ] Session detail + manual corrections
- [ ] Export (PDF/CSV/Excel)
- [ ] Unknown faces review
- [ ] Templates: `templates/admin/attendance/`

**Done when:** Admin can view and export attendance for any class/session.

---

### Phase 7 — Settings

- [ ] `routes/admin/settings.py`
- [ ] Face recognition tolerance, thresholds
- [ ] System preferences via `Settings` model
- [ ] Log changes with `ActivityType.SETTINGS_CHANGED`

**Done when:** Settings persist and affect system behavior.

---

## Implementation status (update as you go)

| Phase | Status | Date completed | Notes |
|-------|--------|----------------|-------|
| Phase 0 | Not started | | |
| Phase 1 | Not started | | |
| Phase 2 | Not started | | |
| Phase 3 | Not started | | |
| Phase 4 | Not started | | |
| Phase 5 | Not started | | |
| Phase 6 | Not started | | |
| Phase 7 | Not started | | |

---

## Current task

> **Update this section before each AI session.**

```
Phase: 0 — Foundation
Scope:
  - Admin model
  - Multi-role user_loader
  - admin_required decorator
  - Admin login + redirect
  - Empty /admin/dashboard

Do NOT implement: Phases 1–7, lecturer changes, student portal.
```

---

## Reference files to attach per phase

### Always attach

| File | Why |
|------|-----|
| `lec_panel/docs/ADMIN_BUILD_BRIEF.md` | This document |
| `lec_panel/app/routes/lecturer/sessions.py` | Blueprint + service pattern |
| `lec_panel/app/decorators/auth.py` | Auth decorators |
| `lec_panel/config/constants.py` | Enums |

### Phase 0

| File | Why |
|------|-----|
| `lec_panel/app/__init__.py` | `user_loader`, blueprint registration, `create_admin` CLI |
| `lec_panel/app/routes/auth.py` | Login flow to extend |
| `lec_panel/app/models/user.py` | Add Admin model here |
| `lec_panel/app/services/auth_service.py` | Auth patterns |

### Phase 2

| File | Why |
|------|-----|
| `admin/academic_resources/instructor_manager.py` | PyQt feature reference |
| `lec_panel/app/services/auth_service.py` | `create_instructor()` |

### Phase 3

| File | Why |
|------|-----|
| `admin/register_student.py` | PyQt registration flow |
| `lec_panel/app/models/student.py` | Student schema |
| `lec_panel/app/services/face_recognition_service.py` | Encoding logic |

### Phase 5

| File | Why |
|------|-----|
| `lec_panel/app/models/timetable.py` | Timetable model |
| `lec_panel/app/services/scheduling_service.py` | Session generation |
| `fakers/generate_timetable.py` | Conflict logic reference |

### Templates

| File | Why |
|------|-----|
| `lec_panel/app/templates/base.html` | Base layout |
| `lec_panel/app/templates/lecturer/dashboard.html` | Dashboard UI pattern |
| `lec_panel/app/templates/partials/_navbar.html` | Navbar pattern |

---

## What NOT to do

- Do **not** create a new Flask app or `admin_panel/` folder.
- Do **not** extend the PyQt `admin/` folder at project root.
- Do **not** use raw `sqlite3` — use SQLAlchemy models only.
- Do **not** filter admin queries by `instructor_id`.
- Do **not** move live attendance / face recognition session start to admin (lecturer feature).
- Do **not** implement multiple phases in one AI task.
- Do **not** invent new database tables without updating models and brief.

---

## Testing checklist (after each phase)

1. Admin flow works — create/edit without errors.
2. Lecturer panel still works — log in as lecturer, data unchanged.
3. Single database — `attendance.db`, no PyQt required.
4. Activity log — admin actions recorded with `user_type='admin'`.
5. Permissions — lecturer gets 403 on `/admin/*`; admin gets 403 on lecturer-only actions (if applicable).
6. No console/traceback errors on affected routes.

---

## Key config paths

| Setting | Location |
|---------|----------|
| Database | `{project_root}/attendance.db` |
| BASE_DIR | `lec_panel/config/config.py` → 3 levels up from config file |
| Student photos | `lec_panel/uploads/student_photos/` |
| Face encodings | `lec_panel/uploads/face_encodings/` |
| Legacy student images | `{project_root}/student_images/` |
| Run server | `cd lec_panel && python run.py` |
| Create admin | `flask create-admin` (from lec_panel dir) |

---

## Admin URL map (target)

| URL | Route module | Purpose |
|-----|--------------|---------|
| `/auth/login` | `auth.py` | Shared login (role-aware) |
| `/admin/dashboard` | `admin/dashboard.py` | Admin home |
| `/admin/lecturers` | `admin/lecturers.py` | Lecturer CRUD |
| `/admin/students` | `admin/students.py` | Student CRUD + face |
| `/admin/courses` | `admin/courses.py` | Courses + classes |
| `/admin/timetable` | `admin/timetable.py` | Campus schedule |
| `/admin/sessions` | `admin/sessions.py` | Session oversight |
| `/admin/attendance` | `admin/attendance.py` | Reports |
| `/admin/settings` | `admin/settings.py` | System config |

---

## Glossary

| Term | Meaning |
|------|---------|
| `lec_panel` | The Flask web application (lecturer today, admin soon) |
| `admin/` (root) | Legacy PyQt desktop app — reference only |
| Blueprint | Flask route module registered in `__init__.py` |
| Phase | One vertical slice of admin functionality |
| Campus-wide | All data, no per-instructor filtering |

---

*End of brief. Update Implementation status and Current task as you progress.*
