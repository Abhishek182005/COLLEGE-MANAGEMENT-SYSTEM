from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from academics.models import Department, Course, AcademicSession, Semester, Subject
from students.models import Batch, Student
from faculty.models import Faculty
from examinations.models import Examination, AssessmentComponent, Marks, InternalAssessmentRecord
from reports.utils import generate_marksheet_pdf, generate_student_id_card_pdf, export_students_to_excel
from reports.ia_utils import build_final_ia_report_data, generate_final_ia_report_pdf, export_final_ia_report_excel

User = get_user_model()


class ExaminationAndReportGenerationTests(TestCase):
    def setUp(self):
        self.session = AcademicSession.objects.create(name="2026-2027", start_date=date(2026, 7, 1), end_date=date(2027, 6, 30), is_current=True)
        self.dept = Department.objects.create(name="CSE", code="CSE")
        self.course = Course.objects.create(name="B.Tech CSE", code="BT-CSE", department=self.dept)
        self.sem = Semester.objects.create(course=self.course, semester_number=5, academic_session=self.session)
        self.batch = Batch.objects.create(name="Batch 2026", course=self.course, academic_session=self.session)
        self.subj = Subject.objects.create(code="CS501", name="Operating Systems", semester=self.sem)

        u_st = User.objects.create_user(username='exam_st', first_name='Test', last_name='Student', password='Password123', role='STUDENT')
        self.student = Student.objects.create(
            user=u_st, roll_number="2026CS999", registration_number="REG2026999",
            department=self.dept, course=self.course, current_semester=self.sem, batch=self.batch
        )

        self.exam = Examination.objects.create(
            name="Mid-Term Autumn 2026", academic_session=self.session, start_date=date(2026, 9, 10), end_date=date(2026, 9, 20), is_published=True
        )

        self.comp = AssessmentComponent.objects.create(
            examination=self.exam, subject=self.subj, title="Theory Test", max_marks=Decimal('100.00'), pass_marks=Decimal('40.00')
        )

    def test_automatic_grade_calculation(self):
        """Marks model calculates letter grade automatically on save."""
        # 95 marks -> A+
        m1 = Marks.objects.create(assessment_component=self.comp, student=self.student, marks_obtained=Decimal('95.00'))
        self.assertEqual(m1.grade, 'A+')

        # 82 marks -> A
        m1.marks_obtained = Decimal('82.00')
        m1.save()
        self.assertEqual(m1.grade, 'A')

        # 65 marks -> B
        m1.marks_obtained = Decimal('65.00')
        m1.save()
        self.assertEqual(m1.grade, 'B')

        # 35 marks -> F (below pass mark)
        m1.marks_obtained = Decimal('35.00')
        m1.save()
        self.assertEqual(m1.grade, 'F')

    def test_reportlab_marksheet_pdf_generation(self):
        """ReportLab creates a valid PDF document with %PDF magic header."""
        Marks.objects.create(assessment_component=self.comp, student=self.student, marks_obtained=Decimal('88.50'))
        pdf_bytes = generate_marksheet_pdf(self.student, self.exam)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertGreater(len(pdf_bytes), 1000)

    def test_reportlab_student_id_card_pdf_generation(self):
        """ReportLab generates an official student identity card PDF."""
        pdf_bytes = generate_student_id_card_pdf(self.student)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_openpyxl_students_excel_export(self):
        """OpenPyXL exports student directory to a valid Excel binary."""
        excel_bytes = export_students_to_excel(Student.objects.all())
        self.assertIsInstance(excel_bytes, bytes)
        # Excel zip magic signature is PK (0x50, 0x4B)
        self.assertTrue(excel_bytes.startswith(b'PK'))

    def test_final_ia_report_access_calculation_and_downloads(self):
        """Faculty/Admin can view, edit, confirm, and download Final IA Report (PDF & Excel); Students are blocked."""
        # Create faculty user
        u_fac = User.objects.create_user(username='ia_fac', first_name='Dr', last_name='Sharma', password='Password123', role='FACULTY')
        Faculty.objects.create(user=u_fac, employee_id='FAC_IA_1', department=self.dept)

        # Create attendance & exam marks
        from attendance.models import AttendanceSession, AttendanceRecord
        sess = AttendanceSession.objects.create(
            subject=self.subj, faculty=u_fac.faculty_profile, semester=self.sem, batch=self.batch,
            date=date.today(), lecture_slot="09:00 - 10:00"
        )
        AttendanceRecord.objects.create(session=sess, student=self.student, status='PRESENT')
        Marks.objects.create(assessment_component=self.comp, student=self.student, marks_obtained=Decimal('80.00'))

        # Student should NOT access Final IA Report
        self.client.login(username='exam_st', password='Password123')
        st_resp = self.client.get(reverse('final_ia_report'))
        self.assertEqual(st_resp.status_code, 302)
        self.client.logout()

        # Faculty CAN view Final IA Report
        self.client.login(username='ia_fac', password='Password123')
        fac_resp = self.client.get(reverse('final_ia_report'), {'course': self.course.id})
        self.assertEqual(fac_resp.status_code, 200)
        self.assertContains(fac_resp, "Final IA Report (Course Wise)")
        self.assertContains(fac_resp, self.student.roll_number)
        self.assertContains(fac_resp, self.subj.code)
        self.assertContains(fac_resp, "100.00")

        # Faculty saves and confirms IA row inline
        rk = f"{self.student.id}_{self.subj.id}"
        post_resp = self.client.post(reverse('final_ia_report'), {
            'row_keys': [rk],
            'action_type': 'confirm_all',
            f'max_ia_{rk}': '30',
            f'attd_max_{rk}': '6.0',
            f'final_attd_{rk}': '6',
            f'marks_ct_{rk}': '11',
            f'marks_assi_{rk}': '12',
            f'mod_{rk}': '1',
            f'confirm_{rk}': '1',
            'course': str(self.course.id),
        })
        self.assertEqual(post_resp.status_code, 302)

        ia_rec = InternalAssessmentRecord.objects.get(student=self.student, subject=self.subj)
        self.assertEqual(ia_rec.confirm_status, 'CONFIRMED')
        self.assertIsNotNone(ia_rec.confirm_date)

        # Verify PDF and Excel exports
        pdf_resp = self.client.get(reverse('final_ia_report_pdf'), {'course': self.course.id})
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertEqual(pdf_resp['Content-Type'], 'application/pdf')
        self.assertTrue(pdf_resp.content.startswith(b'%PDF'))

        xlsx_resp = self.client.get(reverse('final_ia_report_excel'), {'course': self.course.id})
        self.assertEqual(xlsx_resp.status_code, 200)
        self.assertTrue(xlsx_resp.content.startswith(b'PK'))

    def test_student_portal_has_no_id_card_or_marksheet_downloads(self):
        """Ensure ID card and marksheet PDF downloads are removed/disabled for student accounts."""
        self.client.login(username='exam_st', password='Password123')

        dash_resp = self.client.get(reverse('student_dashboard'))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertNotContains(dash_resp, "ID Card (PDF)")

        res_resp = self.client.get(reverse('student_results'))
        self.assertEqual(res_resp.status_code, 200)
        self.assertNotContains(res_resp, "Download Official Marksheet")

        # Direct endpoint hits redirect students away
        id_pdf_resp = self.client.get(reverse('student_id_card_pdf', args=[self.student.id]))
        self.assertEqual(id_pdf_resp.status_code, 302)

        ms_pdf_resp = self.client.get(reverse('download_marksheet_pdf', args=[self.exam.id]))
        self.assertEqual(ms_pdf_resp.status_code, 302)
