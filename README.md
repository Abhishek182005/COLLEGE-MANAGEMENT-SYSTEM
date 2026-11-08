# 🎓 CampusConnect – Enterprise College Management System (ERP)

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2+-092E20?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/Django_REST_Framework-3.18+-red?style=flat)](https://www.django-rest-framework.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=flat&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![ReportLab](https://img.shields.io/badge/PDF_Engine-ReportLab-blue?style=flat)](https://www.reportlab.com/)
[![OpenPyXL](https://img.shields.io/badge/Excel_Engine-OpenPyXL-217346?style=flat&logo=microsoft-excel&logoColor=white)](https://openpyxl.readthedocs.io/)
[![Tests](https://img.shields.io/badge/Automated_Tests-29_Passing_✓-brightgreen?style=flat)]()

> **CampusConnect** is a comprehensive, production-ready collegiate ERP platform inspired by **SmartProfessor**. Engineered with high-reliability Django, it digitizes academic administration, faculty workload, daily lecture schedules, multi-channel attendance, grading, and compliance auditing. Built for easy white-labeling and commercial deployment to any university, college, or polytechnic institution.

---

## 🌟 Key Functional Highlights

### 🏛️ 1. Institutional White-Labeling & Reselling Engine
Designed for selling and deploying across multiple colleges with zero code changes:
- **Centralized Brand Portal** (`/accounts/college-settings/`): Custom College / University Full Name, Short Acronym, College Code, Seal/Logo, Tagline/Motto, Affiliation & Accreditation line, Campus Address, Contact Email, Helpline Phone, Website, and Principal / Authorized Signatory Name.
- **Dynamic System-Wide Propagation**: Changes immediately reflect across navigation bars, login screens, PDF Student ID Cards, PDF Marksheets, Excel exports, and footer notices without restarting the server.
- **Customizable Attendance Shortage Threshold**: Set compliance thresholds (default: 75%) institution-wide.

### 👥 2. Three Dedicated Role Portals
- **Administrator Portal**: College health metrics, student enrollment directories, active faculty workloads, departmental distributions, 3-dimensional timetable conflict prevention, shortage alerts (< 75%), user account toggling, and tamper-evident audit logs.
- **Faculty Portal**: Assigned subjects overview, today's schedule with room allocations, assignment creation and grading, examination marks entry, and SmartProf Quick Attendance.
- **Student Portal**: Real-time compliance percentage gauge with shortage warnings, daily lecture timeline, examination results with downloadable PDF marksheets, upcoming assignments submission with late-tracking, and a live QR code attendance scanner.

### ⚡ 3. SmartProf-Inspired Attendance Innovations
- **Quick Attendance Marking**: Single-screen rapid attendance marking with instant Present/Absent/Late toggle buttons and a "Mark All Present" shortcut.
- **Dynamic QR Code Attendance**: Professors project a dynamic QR code on screen with a live 15-minute countdown. Students scan using their camera (HTML5-QRCode) or enter dynamic tokens.
- **Backdated Attendance with Audit Trail**: Faculty can amend past attendance records with mandatory explanation reasons, logged into an immutable `AuditLog` (tracking user, IP address, timestamp, and amendment delta).
- **Offline Attendance Sync**: Faculty without active internet connectivity can record attendance locally in browser `localStorage` and synchronize when back online via `/api/attendance/offline-sync/`.
- **Shortage Detection (< 75%)**: Automatic compliance rate calculation flagging non-compliant students for exam eligibility enforcement.

### 📊 4. Bulk Student Excel Import & Sample Template
- **Downloadable Formatted Spreadsheet** (`/students/import/excel/sample/`): 1-click download of `Student_Bulk_Enrollment_Template.xlsx` pre-filled with styled headers, field notes, and realistic sample data.
- **Smart Column Detection**: Automatically maps standard headers (`Roll Number`, `Registration Number`, `First Name`, `Last Name`, `Email`, `Phone`, `Blood Group`, `Guardian Details`, `Dept/Course/Sem/Batch`).
- **Automated Account Provisioning**: Generates student login accounts with initial default password (`Student@123`), validates unique roll numbers, and records an audit log.

### 📅 5. Conflict-Free Master Timetable Matrix
- **3-Way Real-time Conflict Validation**: Prevents double-booking across **Faculty availability**, **Classroom availability**, and **Batch scheduling**.
- **Interactive Matrix Grid**: Schedule view categorized by day, time slot, room number, and assigned professor.

### 📄 6. Server-Side PDF & Excel Generators
- **Student Identity Cards (ReportLab)**: Printable photo ID cards with institutional headers, barcode/QR placeholders, academic details, and authorized signature lines.
- **Official Academic Marksheets (ReportLab)**: Transcripts with subject components, max marks, obtained marks, automated letter grades ($A+$, $A$, $B+$, $B$, $C$, $D$, $F$), pass/fail results, and official seal blocks.
- **Excel Data Exchange (OpenPyXL)**: Export student directories and attendance logs with custom widths, fills, and styling.

### 🗑️ 7. Full Interactive Navigation & Delete Workflows
- **Interactive Cards & Badges**: Every department card, course badge, subject tag, student roll number, and faculty profile is clickable, opening rich detail pages with related tabs and historical statistics.
- **Protected Deletion Workflows**: Deletion options across Departments, Courses, Subjects, Students, Faculty, Timetable Slots, Assignments, Exams, and Notices protected by role checks, confirmation dialogs, and audit logging.

---

## 🔐 Instant Demo Credentials (Pre-Seeded)

The login page at `/accounts/login/` features **1-Click Autofill Buttons** for immediate evaluation:

| Role | Username | Password | Identity & Context |
|---|---|---|---|
| **Administrator** | `admin` | `Admin@123` | **Dr. Alok Mukherjee** — Full College ERP & White-Labeling Control |
| **Faculty (HOD)** | `prof_sharma` | `Faculty@123` | **Dr. Rajesh Sharma** — HOD Computer Science (CS501, CS503) |
| **Faculty (Assoc. Prof)** | `prof_verma` | `Faculty@123` | **Dr. Anita Verma** — Assoc. Prof CSE (CS502, CS504) |
| **Student (Compliant)** | `student_rohit` | `Student@123` | **Rohit Kumar** — 85% Attendance, Passed Mid-Term Exams |
| **Student (Shortage Alert)** | `student_arjun` | `Student@123` | **Arjun Mehta** — 40% Attendance (Triggers Shortage Warning) |

---

## 📁 System Architecture & Directory Structure

```
College management system/
│
├── campusconnect_core/             # Core Project Configuration & Root Routing
│   ├── settings.py                 # Installed apps, auth user model, REST framework, media/static
│   ├── urls.py                     # Root URL router & dashboard routing
│   ├── api_urls.py                 # Central REST API registry
│   └── wsgi.py
│
├── accounts/                       # Authentication, Roles & White-Labeling
│   ├── models.py                   # CustomUser (ADMIN, FACULTY, STUDENT) & CollegeSetting
│   ├── permissions.py              # RoleRequiredMixin & API permissions
│   ├── context_processors.py       # Global institutional branding context
│   └── management/commands/        # Seed data command (seed_data.py)
│
├── academics/                      # Institutional Academic Tree
│   ├── models.py                   # Department, Course, AcademicSession, Semester, Subject
│   └── views.py                    # Detail views, CRUD operations, deletion confirmation
│
├── faculty/                        # Faculty Directory & Workload
│   ├── models.py                   # Faculty profile, designations, weekly workload calculations
│   └── views.py                    # Faculty directory, workload schedules, edit/delete
│
├── students/                       # Student Records & Enrollment
│   ├── models.py                   # Student, Batch, soft archival, attendance compliance
│   └── views.py                    # Student directory, Excel bulk import, sample download, ID card
│
├── attendance/                     # SmartProf Attendance Hub
│   ├── models.py                   # AttendanceSession, AttendanceRecord, Audit amendment fields
│   └── views.py                    # Quick roll-call, QR scanner, shortage reports, Excel export
│
├── timetable/                      # Timetable Engine & Conflict Detection
│   ├── models.py                   # Classroom, Timetable entry with 3-dimensional conflict validation
│   └── views.py                    # Master weekly grid, class scheduler, slot deletion
│
├── examinations/                   # Exams, Assessments & Grading
│   ├── models.py                   # Examination, AssessmentComponent, Marks
│   └── views.py                    # Exam manager, marks entry, student results, PDF download
│
├── assignments/                    # Coursework & Submissions
│   ├── models.py                   # Assignment, Submission with late submission detection
│   └── views.py                    # Assignment list, submission upload, faculty grading modal
│
├── communication/                  # Circulars & Notice Board
│   ├── models.py                   # Notice with audience targeting, NoticeRead
│   └── views.py                    # Notice board, circular details, publisher deletion
│
├── reports/                        # Compliance Auditing & Export Engines
│   ├── models.py                   # Immutable AuditLog model
│   └── utils.py                    # ReportLab PDF generators & OpenPyXL Excel handlers
│
├── templates/                      # Clean, Responsive Bootstrap 5 UI
│   ├── base.html                   # Dark navy sidebar layout with responsive toggle & branded footer
│   ├── accounts/                   # Login with autofill, profile, password, college branding settings
│   ├── dashboards/                 # Specialized Admin, Faculty, and Student dashboards
│   ├── academics/                  # Interactive cards, tabs, and confirmation dialogs
│   ├── students/                   # Directory, ID card download, Excel import with column legend
│   ├── attendance/                 # Quick attendance toggler, camera QR scanner, shortage reports
│   └── timetable/                  # Master schedule matrix with classroom & faculty filters
│
├── requirements.txt                # Pegged Python dependencies
├── manage.py                       # Django CLI management entrypoint
└── README.md                       # Documentation
```

---

## 🛠️ Installation & Setup Guide

### Prerequisites
- **Python 3.10+** (Tested on Python 3.11)
- **Git**

### 1. Clone the Repository
```bash
git clone https://github.com/Abhishek182005/College-Management-System.git
cd College-Management-System
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Migrations
```bash
python manage.py migrate
```

### 5. Seed Demo Database
Populates realistic sample data: departments (CSE, ECE, ME), courses, subjects, timetables, attendance sessions, exam marks, and demo credentials:
```bash
python manage.py seed_data
```

### 6. Run Automated Tests
```bash
python manage.py test
```
All **29 tests** will run and pass with `OK`.

### 7. Start Development Server
```bash
python manage.py runserver 127.0.0.1:8000
```
Open your browser and navigate to **`http://127.0.0.1:8000/`**.

---

## 🌐 Core REST API Reference

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/api/attendance/quick-mark/` | `POST` | Faculty / Admin | Batch records attendance with Present/Absent/Late status |
| `/api/attendance/qr-generate/<session_id>/` | `POST` | Faculty / Admin | Generates dynamic 15-minute expiring QR token |
| `/api/attendance/qr-mark/` | `POST` | Student | Validates student camera QR scan against session token |
| `/api/attendance/offline-sync/` | `POST` | Faculty / Admin | Bulk synchronizes locally cached offline attendance entries |
| `/api/timetable/conflict-check/` | `POST` | Admin | Real-time checks for faculty, classroom, or batch clashes |
| `/api/examinations/bulk-marks/` | `POST` | Faculty / Admin | Bulk records assessment marks and auto-computes letter grades |

---

## 🧪 Automated Test Suite

Run the comprehensive test suite verifying security checks, attendance calculations, conflict detection, PDF generation, and Excel engines:

```bash
python manage.py test
```

```
Creating test database for alias 'default'...
.............................
----------------------------------------------------------------------
Ran 29 tests in 21.879s

OK
Destroying test database for alias 'default'...
Found 29 test(s).
System check identified no issues (0 silenced).
```

---

## 📄 License & Attribution

Developed with ❤️ as a modular, production-ready collegiate ERP system. Licensed under the [MIT License](LICENSE).
