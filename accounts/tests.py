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
        from django.core.cache import cache
        cache.clear()
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

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

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

    def test_college_setting_logo_and_media_routing(self):
        """Verify uploaded logo or external logo URL resolves and media endpoint serves files."""
        from accounts.models import CollegeSetting
        import os
        from django.conf import settings
        setting = CollegeSetting.get_settings()
        setting.logo_url = "https://example.com/logo.png"
        setting.save()
        self.assertEqual(setting.effective_logo_url, "https://example.com/logo.png")

        # Test media serving endpoint
        media_test_path = os.path.join(settings.MEDIA_ROOT, 'test_media.txt')
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        with open(media_test_path, 'w') as f:
            f.write('media ok')
        try:
            resp = self.client.get('/media/test_media.txt')
            self.assertEqual(resp.status_code, 200)
            file_data = b"".join(resp.streaming_content).decode().strip()
            self.assertEqual(file_data, 'media ok')
            resp.close()
        finally:
            if os.path.exists(media_test_path):
                try:
                    os.remove(media_test_path)
                except Exception:
                    pass

    def test_login_captcha_challenge_generated_on_get(self):
        """Visiting login page creates dynamic arithmetic puzzle in session."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('captcha', response.context)
        self.assertIn('captcha_answer', self.client.session)
        self.assertContains(response, "Security Verification:")
        self.assertContains(response, "Automated bot defense enabled")

    def test_login_blocks_bot_when_honeypot_filled(self):
        """If invisible honeypot trap field is filled, request is blocked as bot attack."""
        # Get login page first
        self.client.get(reverse('login'))
        valid_answer = self.client.session.get('captcha_answer')

        from reports.models import AuditLog
        init_bot_logs = AuditLog.objects.filter(action="BOT_ATTACK_BLOCKED").count()

        # Bot posts with honeypot field filled
        response = self.client.post(reverse('login'), {
            'username': 'admin_test',
            'password': 'Password123',
            'captcha_answer': valid_answer,
            'portal_auth_trap': 'I am a web scraping bot'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Automated bot activity detected and blocked.")

        # Verify security audit log was written
        new_bot_logs = AuditLog.objects.filter(action="BOT_ATTACK_BLOCKED").count()
        self.assertEqual(new_bot_logs, init_bot_logs + 1)

    def test_login_rejects_incorrect_captcha(self):
        """Incorrect math challenge response rejects authentication and logs audit."""
        self.client.get(reverse('login'))

        from reports.models import AuditLog
        init_captcha_logs = AuditLog.objects.filter(action="CAPTCHA_FAILED").count()

        response = self.client.post(reverse('login'), {
            'username': 'admin_test',
            'password': 'Password123',
            'captcha_answer': '999999'  # Deliberately incorrect
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Incorrect security verification answer")

        new_captcha_logs = AuditLog.objects.filter(action="CAPTCHA_FAILED").count()
        self.assertEqual(new_captcha_logs, init_captcha_logs + 1)

    def test_login_succeeds_with_valid_credentials_and_captcha(self):
        """Valid login + solved challenge logs user in and generates LOGIN_SUCCESS audit."""
        self.client.get(reverse('login'))
        answer = self.client.session.get('captcha_answer')

        from reports.models import AuditLog
        init_success_logs = AuditLog.objects.filter(action="LOGIN_SUCCESS").count()

        response = self.client.post(reverse('login'), {
            'username': 'admin_test',
            'password': 'Password123',
            'captcha_answer': answer
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard_redirect'))

        new_success_logs = AuditLog.objects.filter(action="LOGIN_SUCCESS").count()
        self.assertEqual(new_success_logs, init_success_logs + 1)

    def test_login_rate_limiting_locks_out_after_repeated_failures(self):
        """Repeated bad logins trigger brute-force lockout and audit event."""
        from django.core.cache import cache
        cache.clear()

        from reports.models import AuditLog
        init_lockouts = AuditLog.objects.filter(action="BRUTE_FORCE_LOCKOUT").count()

        # Submit 5 failed attempts
        for i in range(5):
            self.client.get(reverse('login'))
            ans = self.client.session.get('captcha_answer')
            self.client.post(reverse('login'), {
                'username': 'victim_user',
                'password': 'WrongPassword!',
                'captcha_answer': ans
            })

        # 6th attempt must be locked out
        self.client.get(reverse('login'))
        ans = self.client.session.get('captcha_answer')
        res = self.client.post(reverse('login'), {
            'username': 'victim_user',
            'password': 'WrongPassword!',
            'captcha_answer': ans
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Too many failed login attempts")

        new_lockouts = AuditLog.objects.filter(action="BRUTE_FORCE_LOCKOUT").count()
        self.assertTrue(new_lockouts >= init_lockouts + 1)

    def test_refresh_captcha_ajax_endpoint(self):
        """AJAX endpoint returns new arithmetic challenge as JSON."""
        response = self.client.get(reverse('refresh_captcha'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('question', data)
        self.assertIn('token', data)
        self.assertIn('answer', data)
        # Verify session was updated with this answer
        self.assertEqual(self.client.session.get('captcha_answer'), data['answer'])
