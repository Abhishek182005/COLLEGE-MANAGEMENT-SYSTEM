from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from academics.models import Department, Course, AcademicSession, Semester, Subject, SubjectAllocation
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
        # Create faculty user and allocate CS501 to them
        u_fac = User.objects.create_user(username='ia_fac', first_name='Dr', last_name='Sharma', password='Password123', role='FACULTY')
        fac_profile = Faculty.objects.create(user=u_fac, employee_id='FAC_IA_1', department=self.dept)
        SubjectAllocation.objects.create(subject=self.subj, faculty=fac_profile, academic_session=self.session, is_active=True)

        # Create attendance & exam marks
        from attendance.models import AttendanceSession, AttendanceRecord
        sess = AttendanceSession.objects.create(
            subject=self.subj, faculty=u_fac.faculty_profile, semester=self.sem, batch=self.batch,
            date=date.today(), lecture_slot="09:00 - 10:00"
        )
        AttendanceRecord.objects.create(session=sess, student=self.student, status='PRESENT')
        Marks.objects.create(assessment_component=self.comp, student=self.student, marks_obtained=Decimal('80.00'))

        # Student should NOT access IA Evaluation Ledger
        self.client.login(username='exam_st', password='Password123')
        st_resp = self.client.get(reverse('final_ia_report'))
        self.assertEqual(st_resp.status_code, 302)
        self.client.logout()

        # Faculty CAN view IA Evaluation Ledger for their allocated course/subject
        self.client.login(username='ia_fac', password='Password123')
        fac_resp = self.client.get(reverse('final_ia_report'), {'course': self.course.id})
        self.assertEqual(fac_resp.status_code, 200)
        self.assertContains(fac_resp, "Internal Assessment (IA) Evaluation")
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

    def test_faculty_strictly_scoped_to_assigned_course_marks_and_ia(self):
        """Faculty can only view, enter, and export marks/IA for courses and subjects allocated to them."""
        dept2 = Department.objects.create(name="ECE", code="ECE")
        course2 = Course.objects.create(name="B.Tech ECE", code="BT-ECE", department=dept2)
        sem2 = Semester.objects.create(course=course2, semester_number=3, academic_session=self.session)
        batch2 = Batch.objects.create(name="ECE 2026", course=course2, academic_session=self.session)
        subj2 = Subject.objects.create(code="EC301", name="Digital Electronics", semester=sem2)
        comp2 = AssessmentComponent.objects.create(
            examination=self.exam, subject=subj2, title="Mid-Term Theory", max_marks=Decimal('100.00'), pass_marks=Decimal('40.00')
        )

        u_st2 = User.objects.create_user(username='ece_st', first_name='Other', last_name='Learner', password='Password123', role='STUDENT')
        student2 = Student.objects.create(
            user=u_st2, roll_number="2026EC001", registration_number="REG2026EC1",
            department=dept2, course=course2, current_semester=sem2, batch=batch2
        )

        # Faculty A teaches ONLY self.subj (CS501 in BT-CSE)
        u_fac_a = User.objects.create_user(username='fac_a', first_name='Prof', last_name='Alpha', password='Password123', role='FACULTY')
        fac_a = Faculty.objects.create(user=u_fac_a, employee_id='FAC_A', department=self.dept)
        SubjectAllocation.objects.create(subject=self.subj, faculty=fac_a, academic_session=self.session, is_active=True)

        self.client.login(username='fac_a', password='Password123')

        # 1. Examination list only displays CS501, not EC301
        exam_list_resp = self.client.get(reverse('examination_list'))
        self.assertEqual(exam_list_resp.status_code, 200)
        self.assertContains(exam_list_resp, self.subj.code)
        self.assertNotContains(exam_list_resp, subj2.code)

        # 2. Marks entry allowed for CS501, blocked (403) for EC301 (both HTML view & bulk API)
        ok_entry = self.client.get(reverse('marks_entry', args=[self.comp.id]))
        self.assertEqual(ok_entry.status_code, 200)

        blocked_get = self.client.get(reverse('marks_entry', args=[comp2.id]))
        self.assertEqual(blocked_get.status_code, 403)

        blocked_post = self.client.post(reverse('marks_entry', args=[comp2.id]), {
            f'marks_{student2.id}': '85',
        })
        self.assertEqual(blocked_post.status_code, 403)
        self.assertFalse(Marks.objects.filter(assessment_component=comp2, student=student2).exists())

        api_resp = self.client.post(
            reverse('api_bulk_marks_entry'),
            data={'component_id': comp2.id, 'records': [{'student_id': student2.id, 'marks_obtained': 90}]},
            content_type='application/json'
        )
        self.assertEqual(api_resp.status_code, 403)

        # 3. IA Evaluation Ledger shows only Faculty A's course & rejects access/edits for course2/subj2
        ia_ok = self.client.get(reverse('final_ia_report'))
        self.assertEqual(ia_ok.status_code, 200)
        self.assertContains(ia_ok, self.subj.code)
        self.assertNotContains(ia_ok, subj2.code)
        self.assertNotContains(ia_ok, course2.code)

        for url_name in ('final_ia_report', 'final_ia_report_pdf', 'final_ia_report_excel'):
            r_course = self.client.get(reverse(url_name), {'course': course2.id})
            self.assertEqual(r_course.status_code, 403)
            r_subj = self.client.get(reverse(url_name), {'subject': subj2.id})
            self.assertEqual(r_subj.status_code, 403)

        bad_rk = f"{student2.id}_{subj2.id}"
        tamper_post = self.client.post(reverse('final_ia_report'), {
            'row_keys': [bad_rk],
            'action_type': 'save',
            f'marks_ct_{bad_rk}': '12',
        })
        self.assertEqual(tamper_post.status_code, 403)
        self.assertFalse(InternalAssessmentRecord.objects.filter(student=student2, subject=subj2).exists())
        self.client.logout()

        # 4. Admin can still view both courses on IA Evaluation Ledger
        u_admin = User.objects.create_user(username='ia_admin', password='Password123', role='ADMIN')
        self.client.login(username='ia_admin', password='Password123')
        admin_ia = self.client.get(reverse('final_ia_report'), {'course': course2.id})
        self.assertEqual(admin_ia.status_code, 200)
        self.assertContains(admin_ia, subj2.code)
        self.assertContains(admin_ia, student2.roll_number)
