from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import CustomUser
from academics.models import Department, Course, Semester, Subject, AcademicSession

class AcademicsInteractiveAndCRUDTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(
            username='test_admin',
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
        self.dept = Department.objects.create(name='Computer Science', code='CSE', established_year=2005)
        self.course = Course.objects.create(department=self.dept, name='B.Tech CSE', code='BT-CS', duration_years=4, total_semesters=8)
        self.sem = Semester.objects.create(course=self.course, semester_number=1, academic_session=self.session)
        self.subject = Subject.objects.create(semester=self.sem, name='Data Structures', code='CS101', credits=4, subject_type='THEORY')

    def test_department_detail_view(self):
        url = reverse('department_detail', args=[self.dept.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Computer Science')
        self.assertContains(resp, 'BT-CS')

    def test_course_detail_view(self):
        url = reverse('course_detail', args=[self.course.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'B.Tech CSE')

    def test_subject_detail_view(self):
        url = reverse('subject_detail', args=[self.subject.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Data Structures')

    def test_department_delete_flow(self):
        del_confirm_url = reverse('department_delete', args=[self.dept.id])
        get_resp = self.client.get(del_confirm_url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Confirm Deletion')

        # Post delete
        post_resp = self.client.post(del_confirm_url)
        self.assertEqual(post_resp.status_code, 302)
        self.assertFalse(Department.objects.filter(id=self.dept.id).exists())
