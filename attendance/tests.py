from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from academics.models import Department, Course, AcademicSession, Semester, Subject
from faculty.models import Faculty
from students.models import Batch, Student
from attendance.models import AttendanceSession, AttendanceRecord

User = get_user_model()


class AttendanceManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = AcademicSession.objects.create(name="2026-2027", start_date=date(2026, 7, 1), end_date=date(2027, 6, 30), is_current=True)
        self.dept = Department.objects.create(name="CSE", code="CSE")
        self.course = Course.objects.create(name="B.Tech CSE", code="BT-CSE", department=self.dept)
        self.sem = Semester.objects.create(course=self.course, semester_number=5, academic_session=self.session)
        self.batch = Batch.objects.create(name="Batch 2026", course=self.course, academic_session=self.session)
        self.subj = Subject.objects.create(code="CS501", name="OS", semester=self.sem)

        u_fac = User.objects.create_user(username='prof_test', password='Password123', role='FACULTY')
        self.faculty = Faculty.objects.create(user=u_fac, employee_id="FAC01", department=self.dept)

        # 2 Students
        self.u_s1 = User.objects.create_user(username='st1', password='Password123', role='STUDENT')
        self.st1 = Student.objects.create(user=self.u_s1, roll_number="R001", registration_number="REG001", department=self.dept, course=self.course, current_semester=self.sem, batch=self.batch)

        self.u_s2 = User.objects.create_user(username='st2', password='Password123', role='STUDENT')
        self.st2 = Student.objects.create(user=self.u_s2, roll_number="R002", registration_number="REG002", department=self.dept, course=self.course, current_semester=self.sem, batch=self.batch)

    def test_attendance_session_and_record_creation(self):
        """AttendanceSession and AttendanceRecord work with calculations."""
        sess = AttendanceSession.objects.create(
            subject=self.subj,
            faculty=self.faculty,
            semester=self.sem,
            batch=self.batch,
            date=date.today(),
            lecture_slot="09:00 - 10:00"
        )

        AttendanceRecord.objects.create(session=sess, student=self.st1, status='PRESENT')
        AttendanceRecord.objects.create(session=sess, student=self.st2, status='ABSENT')

        self.assertEqual(sess.total_students, 2)
        self.assertEqual(sess.present_count, 1)
        self.assertEqual(sess.absent_count, 1)
        self.assertEqual(sess.attendance_percentage, 50.0)

    def test_student_attendance_stats_and_shortage_alert(self):
        """Student attendance percentage and shortage threshold (< 75%) logic."""
        for i in range(4):
            s = AttendanceSession.objects.create(
                subject=self.subj, faculty=self.faculty, semester=self.sem, batch=self.batch,
                date=date.today() - timedelta(days=i), lecture_slot="09:00 - 10:00"
            )
            AttendanceRecord.objects.create(session=s, student=self.st1, status='PRESENT')
            status = 'PRESENT' if i == 0 else 'ABSENT'
            AttendanceRecord.objects.create(session=s, student=self.st2, status=status)

        stats1 = self.st1.get_attendance_stats()
        self.assertEqual(stats1['percentage'], 100.0)
        self.assertFalse(stats1['shortage'])

        stats2 = self.st2.get_attendance_stats()
        self.assertEqual(stats2['percentage'], 25.0)
        self.assertTrue(stats2['shortage'])

    def test_qr_token_expiration(self):
        """QR tokens expire after designated timestamp."""
        sess = AttendanceSession.objects.create(
            subject=self.subj, faculty=self.faculty, semester=self.sem, batch=self.batch,
            date=date.today(), qr_expires_at=timezone.now() - timedelta(minutes=1)
        )
        self.assertFalse(sess.is_qr_valid())

        sess.qr_expires_at = timezone.now() + timedelta(minutes=10)
        self.assertTrue(sess.is_qr_valid())

    def test_qr_generation_and_student_mark_api(self):
        """Test the end-to-end QR code generation by faculty and student marking via API."""
        sess = AttendanceSession.objects.create(
            subject=self.subj, faculty=self.faculty, semester=self.sem, batch=self.batch,
            date=date.today()
        )

        # Faculty generates QR
        self.client.login(username='prof_test', password='Password123')
        gen_res = self.client.post(reverse('api_qr_generate', kwargs={'session_id': sess.id}))
        self.assertEqual(gen_res.status_code, 200)
        data = gen_res.json()
        self.assertIn('qr_token', data)
        self.assertIn('qr_base64', data)
        token = data['qr_token']

        # Student marks attendance using token
        self.client.login(username='st1', password='Password123')
        mark_res = self.client.post(reverse('api_qr_mark'), {'token': token}, content_type='application/json')
        self.assertEqual(mark_res.status_code, 200)
        self.assertTrue(mark_res.json()['success'])

        # Verify record was created
        record = AttendanceRecord.objects.get(session=sess, student=self.st1)
        self.assertEqual(record.status, 'PRESENT')
        self.assertEqual(record.marked_via, 'QR_CODE')

    def test_shortage_report_view(self):
        """Shortage report view renders successfully for faculty."""
        self.client.login(username='prof_test', password='Password123')
        res = self.client.get(reverse('attendance_shortage_report'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Attendance Shortages")

    def test_offline_sync_api(self):
        """Faculty can sync cached offline records seamlessly."""
        self.client.login(username='prof_test', password='Password123')
        payload = {
            'sessions': [
                {
                    'subject_id': self.subj.id,
                    'semester_id': self.sem.id,
                    'batch_id': self.batch.id,
                    'date': date.today().isoformat(),
                    'lecture_slot': "11:15 - 12:15",
                    'records': [
                        {'student_id': self.st1.id, 'status': 'PRESENT', 'remarks': 'Offline cached'},
                        {'student_id': self.st2.id, 'status': 'LATE', 'remarks': 'Offline cached'}
                    ]
                }
            ]
        }
        res = self.client.post(reverse('api_offline_sync'), payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['synced_count'], 1)

        sync_sess = AttendanceSession.objects.filter(subject=self.subj, lecture_slot="11:15 - 12:15").first()
        self.assertIsNotNone(sync_sess)
        self.assertEqual(sync_sess.records.count(), 2)

    def test_student_attendance_view_and_monthly_register(self):
        """Student can view their official attendance register with monthly demarcation & benefits."""
        # July session (Theory)
        sess_july = AttendanceSession.objects.create(
            subject=self.subj, faculty=self.faculty, semester=self.sem, batch=self.batch,
            date=date(2026, 7, 20), lecture_slot="09:00 - 10:00", session_type="TE"
        )
        AttendanceRecord.objects.create(session=sess_july, student=self.st1, status='PRESENT')

        # August session (Practical with Medical Benefit)
        sess_aug = AttendanceSession.objects.create(
            subject=self.subj, faculty=self.faculty, semester=self.sem, batch=self.batch,
            date=date(2026, 8, 15), lecture_slot="10:00 - 11:00", session_type="PR"
        )
        AttendanceRecord.objects.create(session=sess_aug, student=self.st1, status='EXCUSED', benefit_type='MED')

        # September session (Theory with Sports Benefit)
        sess_sep = AttendanceSession.objects.create(
            subject=self.subj, faculty=self.faculty, semester=self.sem, batch=self.batch,
            date=date(2026, 9, 10), lecture_slot="09:00 - 10:00", session_type="TE"
        )
        AttendanceRecord.objects.create(session=sess_sep, student=self.st1, status='EXCUSED', benefit_type='SPORTS')

        # Login as student
        self.client.login(username='st1', password='Password123')
        res = self.client.get(reverse('student_attendance'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Monthly Academic Attendance Register")
        self.assertContains(res, "CS501")
        self.assertContains(res, "July")
        self.assertContains(res, "August")
        self.assertContains(res, "September")
        self.assertContains(res, "Bft. Med")
        self.assertContains(res, "Bft. Sports")
        self.assertContains(res, "Note: Medical Benefit (Bft. Med) will not be added into the Attendance Marks.")

    def test_quick_mark_loads_existing_session_and_saves_benefits(self):
        """Quick mark detects already recorded session and updates without duplicates."""
        self.client.login(username='prof_test', password='Password123')

        today_str = date.today().isoformat()
        post_data = {
            'subject_id': self.subj.id,
            'semester_id': self.sem.id,
            'batch_id': self.batch.id,
            'date': today_str,
            'lecture_slot': "09:00 - 10:00",
            'session_type': "PR",
            'topic_covered': "Unit 2 Practical",
            f'status_{self.st1.id}': "PRESENT",
            f'benefit_{self.st1.id}': "NONE",
            f'remarks_{self.st1.id}': "Active participant",
            f'status_{self.st2.id}': "EXCUSED",
            f'benefit_{self.st2.id}': "SPORTS",
            f'remarks_{self.st2.id}': "College tournament",
        }
        res = self.client.post(reverse('quick_mark_attendance'), post_data)
        self.assertEqual(res.status_code, 302)

        # Check session was created with PR session_type
        sess = AttendanceSession.objects.get(subject=self.subj, date=date.today(), lecture_slot="09:00 - 10:00")
        self.assertEqual(sess.session_type, "PR")

        rec2 = AttendanceRecord.objects.get(session=sess, student=self.st2)
        self.assertEqual(rec2.status, "EXCUSED")
        self.assertEqual(rec2.benefit_type, "SPORTS")

        # Now GET request for the same slot loads existing session and indicates already marked
        get_res = self.client.get(reverse('quick_mark_attendance'), {
            'subject_id': self.subj.id,
            'date': today_str,
            'lecture_slot': "09:00 - 10:00",
        })
        self.assertEqual(get_res.status_code, 200)
        self.assertTrue(get_res.context['is_already_marked'])
        self.assertEqual(get_res.context['existing_session'], sess)
