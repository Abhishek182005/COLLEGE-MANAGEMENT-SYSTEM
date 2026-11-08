from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from academics.models import Department, Course, AcademicSession, Semester, Subject
from students.models import Batch, Student
from examinations.models import Examination, AssessmentComponent, Marks
from reports.utils import generate_marksheet_pdf, generate_student_id_card_pdf, export_students_to_excel

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
