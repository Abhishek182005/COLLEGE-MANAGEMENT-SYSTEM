from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from accounts.models import CustomUser
from academics.models import Department, Course, AcademicSession, Semester
from faculty.models import Faculty
from students.models import Batch, Student

User = get_user_model()


class AccountsSecurityAndRoleTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.session = AcademicSession.objects.create(
            name="2026-2027", start_date=date(2026, 7, 1), end_date=date(2027, 6, 30), is_current=True
        )
        self.dept = Department.objects.create(name="Computer Science", code="CSE")
        self.course = Course.objects.create(name="B.Tech CSE", code="BT-CSE", department=self.dept)
        self.sem = Semester.objects.create(course=self.course, semester_number=5, academic_session=self.session)
        self.batch = Batch.objects.create(name="Batch A", course=self.course, academic_session=self.session, section="A")

        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='Password123',
            role=CustomUser.ROLE_ADMIN,
            is_staff=True,
            is_superuser=True
        )

        self.faculty_user = User.objects.create_user(
            username='faculty_test',
            email='faculty@test.com',
            password='Password123',
            role=CustomUser.ROLE_FACULTY,
            is_staff=True
        )
        self.faculty_profile = Faculty.objects.create(
            user=self.faculty_user,
            employee_id="FAC999",
            department=self.dept
        )

        self.student_user = User.objects.create_user(
            username='student_test',
            email='student@test.com',
            password='Password123',
            role=CustomUser.ROLE_STUDENT
        )
        self.student_profile = Student.objects.create(
            user=self.student_user,
            roll_number="2026TEST01",
            registration_number="REGTEST01",
            department=self.dept,
            course=self.course,
            current_semester=self.sem,
            batch=self.batch
        )

    def test_unauthenticated_redirect(self):
        """Unauthenticated requests must be redirected to login page."""
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_student_cannot_access_admin_dashboard(self):
        """Students must be denied access to administrative portals."""
        self.client.login(username='student_test', password='Password123')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard_redirect'))

    def test_student_cannot_access_faculty_quick_attendance(self):
        """Students must be denied access to faculty attendance marking."""
        self.client.login(username='student_test', password='Password123')
        response = self.client.get(reverse('quick_mark_attendance'))
        self.assertEqual(response.status_code, 302)

    def test_role_based_dashboard_redirects(self):
        """Ensure dashboard_redirect directs each role to its correct specialized portal."""
        # Admin
        self.client.login(username='admin_test', password='Password123')
        res = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(res, reverse('admin_dashboard'))

        # Faculty
        self.client.login(username='faculty_test', password='Password123')
        res = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(res, reverse('faculty_dashboard'))

        # Student
        self.client.login(username='student_test', password='Password123')
        res = self.client.get(reverse('dashboard_redirect'))
        self.assertRedirects(res, reverse('student_dashboard'))

    def test_inactive_user_cannot_login(self):
        """Deactivated accounts cannot authenticate."""
        self.student_user.is_active = False
        self.student_user.save()

        response = self.client.post(reverse('login'), {
            'username': 'student_test',
            'password': 'Password123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "inactive")


    def test_college_settings_update(self):
        """Admin can update institutional name and settings for white-labeling."""
        self.client.login(username='admin_test', password='Password123')
        url = reverse('college_settings')

        # GET settings page
        get_resp = self.client.get(url)
        self.assertEqual(get_resp.status_code, 200)

        # POST new college name
        post_resp = self.client.post(url, {
            'name': "St. Xavier's Engineering College",
            'short_name': "SXEC",
            'college_code': "SXEC-101",
            'tagline': "Excellence in Engineering",
            'address': "123 Tech Campus Road",
            'email': "info@sxec.edu",
            'phone': "+91 9999888877",
            'website': "https://sxec.edu",
            'affiliation': "Affiliated to State University | NAAC A+",
            'established_year': 2005,
            'attendance_threshold': 75,
            'principal_name': "Dr. Xavier Roy",
            'footer_text': "Powered by CampusConnect ERP"
        })
        self.assertEqual(post_resp.status_code, 302)

        from accounts.models import CollegeSetting
        active_settings = CollegeSetting.get_settings()
        self.assertEqual(active_settings.name, "St. Xavier's Engineering College")
        self.assertEqual(active_settings.short_name, "SXEC")

        # Verify context processor renders new name on login page for guest
        self.client.logout()
        login_resp = self.client.get(reverse('login'))
        self.assertEqual(login_resp.status_code, 200)
        self.assertContains(login_resp, "Excellence in Engineering")
        self.assertContains(login_resp, "St. Xavier&#x27;s Engineering College")
