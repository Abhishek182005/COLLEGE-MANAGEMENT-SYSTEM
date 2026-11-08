import os
from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from academics.models import Department, Course, AcademicSession, Semester, Subject, SubjectAllocation
from faculty.models import Faculty
from students.models import Batch, Student
from attendance.models import AttendanceSession, AttendanceRecord
from timetable.models import Classroom, Timetable
from examinations.models import Examination, AssessmentComponent, Marks
from assignments.models import Assignment, Submission
from communication.models import Notice
from reports.models import AuditLog

User = get_user_model()


class Command(BaseCommand):
    help = "Populate realistic sample data for CampusConnect College Management System"

    def handle(self, *args, **options):
        self.stdout.write("Starting CampusConnect database population...")

        # 1. Academic Session
        session, _ = AcademicSession.objects.get_or_create(
            name="2026-2027",
            defaults={
                'start_date': date(2026, 7, 15),
                'end_date': date(2027, 6, 30),
                'is_current': True
            }
        )

        # 2. Departments
        cse, _ = Department.objects.get_or_create(
            code="CSE",
            defaults={'name': "Computer Science & Engineering", 'established_year': 2004, 'description': "Department of Computing, AI and Software Engineering."}
        )
        ece, _ = Department.objects.get_or_create(
            code="ECE",
            defaults={'name': "Electronics & Communication Engineering", 'established_year': 2006, 'description': "Department of Electronics, Embedded Systems & IoT."}
        )
        me, _ = Department.objects.get_or_create(
            code="ME",
            defaults={'name': "Mechanical Engineering", 'established_year': 2008, 'description': "Department of Mechanical & Robotics."}
        )

        # 3. Courses
        btech_cse, _ = Course.objects.get_or_create(
            code="BT-CSE",
            defaults={'name': "B.Tech Computer Science & Engineering", 'department': cse, 'duration_years': 4, 'total_semesters': 8}
        )
        btech_ece, _ = Course.objects.get_or_create(
            code="BT-ECE",
            defaults={'name': "B.Tech Electronics & Communication", 'department': ece, 'duration_years': 4, 'total_semesters': 8}
        )

        # 4. Semesters (focus on Sem 5 for CSE)
        sem5_cse, _ = Semester.objects.get_or_create(
            course=btech_cse,
            semester_number=5,
            academic_session=session
        )
        # also create sem 1 and 3 for variety
        Semester.objects.get_or_create(course=btech_cse, semester_number=1, academic_session=session)
        Semester.objects.get_or_create(course=btech_cse, semester_number=3, academic_session=session)

        # 5. Batches
        batch_a, _ = Batch.objects.get_or_create(
            name="Batch 2024-2028",
            course=btech_cse,
            section="A",
            defaults={'academic_session': session}
        )
        batch_b, _ = Batch.objects.get_or_create(
            name="Batch 2024-2028",
            course=btech_cse,
            section="B",
            defaults={'academic_session': session}
        )

        # 6. Subjects for Sem 5
        os_subj, _ = Subject.objects.get_or_create(
            code="CS501",
            defaults={'name': "Operating Systems", 'semester': sem5_cse, 'credits': 4, 'subject_type': 'THEORY'}
        )
        cn_subj, _ = Subject.objects.get_or_create(
            code="CS502",
            defaults={'name': "Computer Networks", 'semester': sem5_cse, 'credits': 4, 'subject_type': 'THEORY'}
        )
        db_subj, _ = Subject.objects.get_or_create(
            code="CS503",
            defaults={'name': "Database Management Systems", 'semester': sem5_cse, 'credits': 4, 'subject_type': 'THEORY'}
        )
        lab_subj, _ = Subject.objects.get_or_create(
            code="CS504",
            defaults={'name': "OS & Networks Laboratory", 'semester': sem5_cse, 'credits': 2, 'subject_type': 'PRACTICAL'}
        )

        # 7. Create Users & Profiles
        # Admin
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                'email': "admin@campusconnect.edu",
                'first_name': "Dr. Alok",
                'last_name': "Mukherjee",
                'role': User.ROLE_ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password("Admin@123")
            admin_user.save()

        # Faculty 1 (Dr. Rajesh Sharma)
        f1_user, created = User.objects.get_or_create(
            username="prof_sharma",
            defaults={
                'email': "rsharma@campusconnect.edu",
                'first_name': "Dr. Rajesh",
                'last_name': "Sharma",
                'role': User.ROLE_FACULTY,
                'phone': "+91 9876543210",
                'is_staff': True,
            }
        )
        if created:
            f1_user.set_password("Faculty@123")
            f1_user.save()

        fac_sharma, _ = Faculty.objects.get_or_create(
            user=f1_user,
            defaults={
                'employee_id': "FAC-CS-001",
                'department': cse,
                'designation': "HOD",
                'qualification': "Ph.D. in Distributed Operating Systems (IIT Delhi)",
                'joining_date': date(2015, 8, 1),
                'cabin_number': "Block C - Room 304",
                'emergency_contact': "+91 9876500001",
            }
        )

        # Faculty 2 (Dr. Anita Verma)
        f2_user, created = User.objects.get_or_create(
            username="prof_verma",
            defaults={
                'email': "averma@campusconnect.edu",
                'first_name': "Dr. Anita",
                'last_name': "Verma",
                'role': User.ROLE_FACULTY,
                'phone': "+91 9876543211",
                'is_staff': True,
            }
        )
        if created:
            f2_user.set_password("Faculty@123")
            f2_user.save()

        fac_verma, _ = Faculty.objects.get_or_create(
            user=f2_user,
            defaults={
                'employee_id': "FAC-CS-002",
                'department': cse,
                'designation': "ASSOC_PROF",
                'qualification': "Ph.D. in Computer Networks & Wireless Comms",
                'joining_date': date(2018, 1, 10),
                'cabin_number': "Block C - Room 308",
                'emergency_contact': "+91 9876500002",
            }
        )

        # Subject Allocations
        SubjectAllocation.objects.get_or_create(subject=os_subj, faculty=fac_sharma, academic_session=session)
        SubjectAllocation.objects.get_or_create(subject=db_subj, faculty=fac_sharma, academic_session=session)
        SubjectAllocation.objects.get_or_create(subject=cn_subj, faculty=fac_verma, academic_session=session)
        SubjectAllocation.objects.get_or_create(subject=lab_subj, faculty=fac_verma, academic_session=session)

        # Students
        students_info = [
            ("student_rohit", "Rohit", "Kumar", "2026CS101", "REG2026001", "B+", "+91 9123456780", "Mr. S. Kumar", "+91 9123456789"),
            ("student_priya", "Priya", "Singh", "2026CS102", "REG2026002", "O+", "+91 9123456781", "Mrs. R. Singh", "+91 9123456790"),
            ("student_arjun", "Arjun", "Mehta", "2026CS103", "REG2026003", "A+", "+91 9123456782", "Mr. P. Mehta", "+91 9123456791"),
            ("student_sneha", "Sneha", "Nair", "2026CS104", "REG2026004", "AB+", "+91 9123456783", "Dr. K. Nair", "+91 9123456792"),
            ("student_rahul", "Rahul", "Das", "2026CS105", "REG2026005", "O-", "+91 9123456784", "Mr. M. Das", "+91 9123456793"),
        ]

        created_students = []
        for uname, fname, lname, roll, reg, bg, phone, gname, gphone in students_info:
            u, created = User.objects.get_or_create(
                username=uname,
                defaults={
                    'email': f"{uname}@campusconnect.edu",
                    'first_name': fname,
                    'last_name': lname,
                    'role': User.ROLE_STUDENT,
                    'phone': phone,
                }
            )
            if created:
                u.set_password("Student@123")
                u.save()

            s, _ = Student.objects.get_or_create(
                user=u,
                defaults={
                    'roll_number': roll,
                    'registration_number': reg,
                    'department': cse,
                    'course': btech_cse,
                    'current_semester': sem5_cse,
                    'batch': batch_a,
                    'blood_group': bg,
                    'guardian_name': gname,
                    'guardian_phone': gphone,
                    'admission_date': date(2024, 8, 1),
                }
            )
            created_students.append(s)

        # 8. Classrooms & Timetable
        lh101, _ = Classroom.objects.get_or_create(room_number="LH-101", defaults={'building': "Main Academic Wing", 'capacity': 70, 'room_type': 'LECTURE_HALL'})
        lh102, _ = Classroom.objects.get_or_create(room_number="LH-102", defaults={'building': "Main Academic Wing", 'capacity': 65, 'room_type': 'LECTURE_HALL'})
        cslab1, _ = Classroom.objects.get_or_create(room_number="CS-LAB-1", defaults={'building': "Computing Annex", 'capacity': 40, 'room_type': 'COMPUTER_LAB'})

        timetable_data = [
            (0, '09:00 - 10:00', os_subj, fac_sharma, lh101, sem5_cse, batch_a),
            (0, '10:00 - 11:00', cn_subj, fac_verma, lh101, sem5_cse, batch_a),
            (1, '09:00 - 10:00', db_subj, fac_sharma, lh101, sem5_cse, batch_a),
            (1, '11:15 - 12:15', lab_subj, fac_verma, cslab1, sem5_cse, batch_a),
            (2, '10:00 - 11:00', os_subj, fac_sharma, lh101, sem5_cse, batch_a),
            (3, '09:00 - 10:00', cn_subj, fac_verma, lh101, sem5_cse, batch_a),
            (4, '02:00 - 03:00', db_subj, fac_sharma, lh102, sem5_cse, batch_a),
        ]
        for day, slot, subj, fac, room, sem, batch in timetable_data:
            Timetable.objects.get_or_create(
                day_of_week=day,
                time_slot=slot,
                subject=subj,
                faculty=fac,
                classroom=room,
                semester=sem,
                batch=batch
            )

        # 9. Attendance Sessions & Records
        # Create 5 historical sessions across past 2 weeks
        base_date = timezone.now().date()
        for day_offset in range(5, 0, -1):
            sess_date = base_date - timedelta(days=day_offset * 2)
            sess, _ = AttendanceSession.objects.get_or_create(
                subject=os_subj,
                faculty=fac_sharma,
                semester=sem5_cse,
                batch=batch_a,
                date=sess_date,
                lecture_slot="09:00 - 10:00",
                defaults={'topic_covered': f"Lecture {6 - day_offset}: Virtual Memory & Paging Algorithms"}
            )
            # Create records: Arjun is frequently absent to show shortage
            for i, st in enumerate(created_students):
                status = 'PRESENT'
                if st.roll_number == '2026CS103' and day_offset in [1, 2, 3]:  # Arjun absent
                    status = 'ABSENT'
                elif st.roll_number == '2026CS105' and day_offset == 2:  # Rahul late
                    status = 'LATE'
                AttendanceRecord.objects.get_or_create(
                    session=sess,
                    student=st,
                    defaults={'status': status, 'marked_via': 'MANUAL'}
                )

        # Active Session for QR code demonstration
        active_qr_sess, _ = AttendanceSession.objects.get_or_create(
            subject=cn_subj,
            faculty=fac_verma,
            semester=sem5_cse,
            batch=batch_a,
            date=base_date,
            lecture_slot="10:00 - 11:00",
            defaults={
                'topic_covered': "Transport Layer Protocols & TCP Congestion Control",
                'qr_expires_at': timezone.now() + timedelta(hours=2)
            }
        )

        # 10. Examination & Marks
        exam, _ = Examination.objects.get_or_create(
            name="Mid-Term Examination Autumn 2026",
            academic_session=session,
            defaults={
                'exam_type': 'MID_TERM',
                'start_date': date(2026, 9, 20),
                'end_date': date(2026, 9, 30),
                'is_published': True
            }
        )

        comp_os, _ = AssessmentComponent.objects.get_or_create(
            examination=exam,
            subject=os_subj,
            title="Written Theory",
            defaults={'max_marks': Decimal('50.00'), 'pass_marks': Decimal('20.00')}
        )
        comp_cn, _ = AssessmentComponent.objects.get_or_create(
            examination=exam,
            subject=cn_subj,
            title="Written Theory",
            defaults={'max_marks': Decimal('50.00'), 'pass_marks': Decimal('20.00')}
        )

        marks_data_list = [
            (created_students[0], comp_os, Decimal('44.50'), fac_sharma),
            (created_students[1], comp_os, Decimal('47.00'), fac_sharma),
            (created_students[2], comp_os, Decimal('28.00'), fac_sharma),
            (created_students[3], comp_os, Decimal('42.00'), fac_sharma),
            (created_students[4], comp_os, Decimal('35.00'), fac_sharma),
            (created_students[0], comp_cn, Decimal('41.00'), fac_verma),
            (created_students[1], comp_cn, Decimal('46.50'), fac_verma),
            (created_students[2], comp_cn, Decimal('22.00'), fac_verma),
            (created_students[3], comp_cn, Decimal('38.50'), fac_verma),
            (created_students[4], comp_cn, Decimal('32.00'), fac_verma),
        ]
        for st, comp, marks_val, fac in marks_data_list:
            Marks.objects.get_or_create(
                assessment_component=comp,
                student=st,
                defaults={'marks_obtained': marks_val, 'graded_by': fac}
            )

        # 11. Assignments & Submissions
        assign1, _ = Assignment.objects.get_or_create(
            title="Multithreaded Banker's Algorithm Simulation",
            subject=os_subj,
            faculty=fac_sharma,
            semester=sem5_cse,
            defaults={
                'description': "Implement deadlock detection and avoidance using Banker's Algorithm with POSIX threads.",
                'due_date': timezone.now() + timedelta(days=5),
                'max_score': Decimal('100.00'),
                'batch': batch_a
            }
        )
        assign2, _ = Assignment.objects.get_or_create(
            title="Custom TCP Client-Server Socket Protocol",
            subject=cn_subj,
            faculty=fac_verma,
            semester=sem5_cse,
            defaults={
                'description': "Design a binary protocol for asynchronous file transfer using reliable TCP sockets.",
                'due_date': timezone.now() + timedelta(days=3),
                'max_score': Decimal('50.00'),
                'batch': batch_a
            }
        )

        Submission.objects.get_or_create(
            assignment=assign1,
            student=created_students[0],
            defaults={
                'student_notes': "Implemented in C++ using std::thread with comprehensive unit tests.",
                'status': 'GRADED',
                'marks_obtained': Decimal('95.00'),
                'faculty_feedback': "Clean synchronization logic and great documentation."
            }
        )

        # 12. Notices
        Notice.objects.get_or_create(
            title="Mid-Term Examination Schedule & Hall Guidelines",
            defaults={
                'content': "The autumn semester mid-term examinations commence next Monday. Students must carry valid college ID cards. Entry into examination halls is strictly prohibited after 15 minutes of commencement.",
                'published_by': admin_user,
                'audience_type': 'ALL',
                'priority': 'HIGH'
            }
        )
        Notice.objects.get_or_create(
            title="Internal Hackathon 2026 - Team Registrations Open",
            defaults={
                'content': "Department of Computer Science invites registrations for SmartCampus Hackathon 2026. Teams of 3-4 members can submit proposals in Web3, AI, and IoT domains.",
                'published_by': f1_user,
                'audience_type': 'DEPARTMENT',
                'department': cse,
                'priority': 'NORMAL'
            }
        )
        Notice.objects.get_or_create(
            title="URGENT: Mandatory 75% Attendance Compliance Advisory",
            defaults={
                'content': "As per university academic regulations, students with overall attendance below 75% will be debarred from appearing in end-semester examinations. Check your portal attendance immediately.",
                'published_by': admin_user,
                'audience_type': 'STUDENTS_ONLY',
                'priority': 'URGENT'
            }
        )

        # 13. Audit Log
        AuditLog.objects.get_or_create(
            action="SYSTEM_INIT",
            entity_type="CampusConnect",
            entity_id="0",
            defaults={
                'user': admin_user,
                'details': "CampusConnect system initialized with complete academic departments, sample student batches, faculty allocations, and seed records.",
                'ip_address': "127.0.0.1"
            }
        )

        self.stdout.write(self.style.SUCCESS("CampusConnect sample data seeded successfully!"))
        self.stdout.write("Credentials:")
        self.stdout.write("  Admin:   username='admin'        password='Admin@123'")
        self.stdout.write("  Faculty: username='prof_sharma'  password='Faculty@123'")
        self.stdout.write("  Faculty: username='prof_verma'   password='Faculty@123'")
        self.stdout.write("  Student: username='student_rohit' password='Student@123'")
        self.stdout.write("  Student: username='student_arjun' password='Student@123' (Low attendance < 75%)")
