from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import CustomUser
from academics.models import Department, Course, Semester, AcademicSession
from students.models import Student, Batch

class StudentManagementAndInteractiveTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(
            username='admin_tester',
            email='admin@test.com',
            password='Password@123',
            role=CustomUser.ROLE_ADMIN
        )
        self.client = Client()
        self.client.force_login(self.admin)

        self.session = AcademicSession.objects.create(
            name='2026-2027',
            start_date='2026-07-01',
            end_date='2027-06-30',
            is_current=True
        )
        self.dept = Department.objects.create(name='Mechanical Engineering', code='ME', established_year=2010)
        self.course = Course.objects.create(department=self.dept, name='B.Tech ME', code='BT-ME', duration_years=4, total_semesters=8)
        self.sem = Semester.objects.create(course=self.course, semester_number=1, academic_session=self.session)
        self.batch = Batch.objects.create(course=self.course, academic_session=self.session, name='ME-A', section='A')

        self.student_user = CustomUser.objects.create_user(
            username='student_test',
            email='student@test.com',
            password='Student@123',
            role=CustomUser.ROLE_STUDENT,
            first_name='Karan',
            last_name='Mehra'
        )
        self.student = Student.objects.create(
            user=self.student_user,
            roll_number='ME-2026-001',
            registration_number='REG-ME-001',
            department=self.dept,
            course=self.course,
            current_semester=self.sem,
            batch=self.batch
        )

    def test_student_detail_renders(self):
        url = reverse('student_detail', args=[self.student.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Karan Mehra')
        self.assertContains(resp, 'ME-2026-001')

    def test_student_delete_flow(self):
        del_url = reverse('student_delete', args=[self.student.id])
        get_resp = self.client.get(del_url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Confirm Deletion')

        # POST delete
        post_resp = self.client.post(del_url)
        self.assertEqual(post_resp.status_code, 302)
        self.assertFalse(Student.objects.filter(id=self.student.id).exists())
        self.assertFalse(CustomUser.objects.filter(id=self.student_user.id).exists())


    def test_download_student_excel_sample(self):
        url = reverse('download_student_excel_sample')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertIn('Student_Bulk_Enrollment_Template.xlsx', resp['Content-Disposition'])

    def test_bulk_student_excel_import(self):
        from reports.utils import generate_student_excel_template
        import io

        sample_excel_bytes = generate_student_excel_template()
        file_obj = io.BytesIO(sample_excel_bytes)
        file_obj.name = 'sample.xlsx'

        url = reverse('import_students_excel')
        resp = self.client.post(url, {
            'department': self.dept.id,
            'course': self.course.id,
            'semester': self.sem.id,
            'batch': self.batch.id,
            'excel_file': file_obj,
        })
        self.assertEqual(resp.status_code, 302)

        # Verify sample students were created (CS-2026-101, EC-2026-102, ME-2026-103)
        self.assertTrue(Student.objects.filter(roll_number='CS-2026-101').exists())
        self.assertTrue(Student.objects.filter(roll_number='EC-2026-102').exists())
        self.assertTrue(Student.objects.filter(roll_number='ME-2026-103').exists())
