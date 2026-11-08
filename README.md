# CampusConnect – College ERP & Academic Management System
Inspired by **SmartProfessor** • Built with **Django 5.2**, **Django REST Framework**, **ReportLab**, and **OpenPyXL**

CampusConnect is a centralized academic and administrative management platform engineered for colleges and universities. It digitizes student records, faculty workloads, attendance, timetables, examinations, internal assessments, assignments, campus announcements, and compliance auditing.

---

## 🌟 Key Functional Highlights

### 1. Three Dedicated Role Portals
- **Administrator Portal**: Real-time overview of student registrations, active faculty, academic departments, timetable conflict prevention, low attendance shortage alerts (< 75%), audit trails, and user management.
- **Faculty Portal**: Subject allocation overview, today's lecture schedule with room assignments, assignments grading, assessment marks entry, and SmartProf-inspired Quick Attendance.
- **Student Portal**: Attendance tracker with shortage warnings, weekly timetable schedule, published examination marks & downloadable PDF transcripts, assignment submission with late detection, and live QR code attendance scanner.

### 2. SmartProf-Inspired Advanced Features
- **Quick Attendance Marking**: Single-screen rapid attendance marking with instant Present/Absent/Late toggle buttons and "Mark All Present" automation.
- **Dynamic QR Code Attendance**: Professors project a live dynamic QR code on screen with a 15-minute countdown timer. Students scan using their camera (HTML5-QRCode) or enter the dynamic code to register instant attendance.
- **Backdated Attendance with Audit Trail**: Faculty can correct historical attendance sessions with mandatory amendment reasons, automatically logged into immutable `AuditLog` records.
- **Offline Attendance Sync**: Faculty without internet connectivity can save attendance locally into browser storage and synchronize when connectivity is restored via `/api/attendance/offline-sync/`.
- **Automated Shortage Alerts**: Computes compliance percentages and flags students who fall below the university-mandated 75% threshold.
- **Timetable Conflict Detection**: Validates schedules across three independent dimensions (Faculty clashes, Classroom clashes, and Batch clashes) via Django validation and real-time REST API.
- **Official PDF Marksheets & ID Cards**: Generated server-side using **ReportLab** with official headers, pass/fail computations, barcodes, and signature blocks.
- **Excel Bulk Import & Export**: Fast spreadsheet data exchange using **OpenPyXL**.

---

## 🚀 Instant Demo Credentials (Pre-seeded)

Use the 1-click autofill buttons on the login page or enter the credentials below:

| Role | Username | Password | Notes |
|---|---|---|---|
| **Administrator** | `admin` | `Admin@123` | Dr. Alok Mukherjee (Full ERP Control) |
| **Faculty (HOD)** | `prof_sharma` | `Faculty@123` | Dr. Rajesh Sharma (CS501, CS503) |
| **Faculty (Assoc. Prof)** | `prof_verma` | `Faculty@123` | Dr. Anita Verma (CS502, CS504) |
| **Student (Normal)** | `student_rohit` | `Student@123` | Rohit Kumar (85% Attendance, Passed) |
| **Student (Shortage Alert)** | `student_arjun` | `Student@123` | Arjun Mehta (40% Attendance - Low Alert) |

---

## 📁 System Architecture & Directory Layout

```
College management system/
│
├── campusconnect_core/             # Project Settings & Root Routing
│   ├── settings.py                 # Installed apps, auth model, REST framework
│   ├── urls.py                     # Root routing
│   ├── api_urls.py                 # REST API endpoints
│   └── wsgi.py
│
├── accounts/                       # Authentication & User Management
│   ├── models.py                   # CustomUser (ADMIN, FACULTY, STUDENT)
│   ├── permissions.py              # Role-based mixins & DRF permissions
│   ├── context_processors.py       # Global college role context
│   └── management/commands/        # Sample data seeder (seed_data.py)
│
├── academics/                      # Academic Structure
│   └── models.py                   # Department, Course, Semester, Subject, Allocation
│
├── faculty/                        # Faculty & Teaching Workload
│   └── models.py                   # Faculty, qualifications, office, workload
│
├── students/                       # Student Records
│   └── models.py                   # Student, Batch, soft archival, attendance stats
│
├── attendance/                     # Attendance Hub
│   ├── models.py                   # AttendanceSession, AttendanceRecord
│   └── api_views.py                # Quick mark, QR generate, QR scan, Offline sync
│
├── timetable/                      # Timetable & Conflict Engine
│   ├── models.py                   # Classroom, Timetable with 3-way conflict checks
│   └── api_views.py                # Conflict verification API
│
├── examinations/                   # Exams & Results
│   ├── models.py                   # Examination, AssessmentComponent, Marks
│   └── api_views.py                # Bulk marks recording API
│
├── assignments/                    # Tasks & Submissions
│   └── models.py                   # Assignment, Submission with late detection
│
├── communication/                  # Notice Board & Communication
│   └── models.py                   # Notice with audience targeting, NoticeRead
│
├── reports/                        # Compliance & Analytics
│   ├── models.py                   # AuditLog
│   └── utils.py                    # ReportLab PDF & OpenPyXL Excel generators
│
├── templates/                      # Clean, Responsive Bootstrap 5 UI
│   ├── base.html                   # Sidebar layout with dark navy theme
│   ├── accounts/                   # Login, profile, password, user management
│   ├── dashboards/                 # Admin, Faculty, Student dashboards
│   ├── attendance/                 # Quick mark, QR scanner, shortage report
│   ├── timetable/                  # Matrix grid, scheduler
│   ├── examinations/               # Exam manager, marks entry, results
│   ├── assignments/                # Assignment submissions & grading
│   ├── communication/              # Circulars notice board
│   └── reports/                    # Analytics charts & audit log table
│
└── manage.py
```

---

## 🛠️ Quick Start Instructions

### 1. Run Database Migrations
```bash
python manage.py migrate
```

### 2. Populate Realistic Demo Data
```bash
python manage.py seed_data
```

### 3. Run Automated Tests
```bash
python manage.py test
```

### 4. Start the Development Server
```bash
python manage.py runserver 127.0.0.1:8000
```
Visit `http://127.0.0.1:8000` in your web browser.

---

## 🌐 Core REST API Endpoints

- `POST /api/attendance/quick-mark/` : Rapid batch attendance recording.
- `POST /api/attendance/qr-generate/<session_id>/` : Dynamic QR code generation with token.
- `POST /api/attendance/qr-mark/` : Student QR code verification.
- `POST /api/attendance/offline-sync/` : Batch synchronization of offline-stored records.
- `POST /api/timetable/conflict-check/` : Validates schedule availability for faculty, classroom, and batch.
- `POST /api/examinations/bulk-marks/` : Bulk assessment marks recording with automated grading.
