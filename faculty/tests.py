from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import CustomUser
from academics.models import Department
from faculty.models import Faculty

class FacultyInteractiveAndCRUDTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(
            username='admin_tester_fac',
            email='adminfac@test.com',
            password='Password@123',
            role=CustomUser.ROLE_ADMIN
        )
        self.client = Client()
        self.client.force_login(self.admin)

        self.dept = Department.objects.create(name='Civil Engineering', code='CE', established_year=2008)
        self.fac_user = CustomUser.objects.create_user(
            username='prof_patel',
            email='patel@test.com',
            password='Faculty@123',
            role=CustomUser.ROLE_FACULTY,
            first_name='Naveen',
            last_name='Patel'
        )
        self.faculty = Faculty.objects.create(
            user=self.fac_user,
            employee_id='FAC-CE-101',
            department=self.dept,
            designation='ASSISTANT_PROF',
            qualification='M.Tech Civil'
        )

    def test_faculty_detail_renders(self):
        url = reverse('faculty_detail', args=[self.faculty.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Naveen Patel')
        self.assertContains(resp, 'FAC-CE-101')
        self.assertContains(resp, 'Civil Engineering')

    def test_faculty_delete_flow(self):
        del_url = reverse('faculty_delete', args=[self.faculty.id])
        get_resp = self.client.get(del_url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Confirm Deletion')

        # POST delete
        post_resp = self.client.post(del_url)
        self.assertEqual(post_resp.status_code, 302)
        self.assertFalse(Faculty.objects.filter(id=self.faculty.id).exists())
        self.assertFalse(CustomUser.objects.filter(id=self.fac_user.id).exists())
