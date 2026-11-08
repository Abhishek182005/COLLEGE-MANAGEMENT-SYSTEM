from django.db import models
from django.conf import settings
from academics.models import Department


class Faculty(models.Model):
    DESIGNATION_CHOICES = [
        ('PROFESSOR', 'Professor'),
        ('ASSOC_PROF', 'Associate Professor'),
        ('ASST_PROF', 'Assistant Professor'),
        ('HOD', 'Head of Department (HOD)'),
        ('LECTURER', 'Lecturer / Adjunct Faculty'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='faculty_profile')
    employee_id = models.CharField(max_length=30, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='faculty_members')
    designation = models.CharField(max_length=30, choices=DESIGNATION_CHOICES, default='ASST_PROF')
    qualification = models.CharField(max_length=150, default='Ph.D. / M.Tech')
    joining_date = models.DateField(null=True, blank=True)
    cabin_number = models.CharField(max_length=50, blank=True, null=True)
    emergency_contact = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Faculty Members"
        ordering = ['department', 'employee_id']

    def __str__(self):
        full_name = self.user.get_full_name() or self.user.username
        return f"{full_name} ({self.employee_id}) - {self.get_designation_display()}"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def email(self):
        return self.user.email

    @property
    def phone(self):
        return self.user.phone

    @property
    def active_allocations(self):
        return self.allocated_subjects.filter(is_active=True)
