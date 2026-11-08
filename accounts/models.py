from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    ROLE_ADMIN = 'ADMIN'
    ROLE_FACULTY = 'FACULTY'
    ROLE_STUDENT = 'STUDENT'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrator'),
        (ROLE_FACULTY, 'Faculty / Professor'),
        (ROLE_STUDENT, 'Student'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STUDENT)
    phone = models.CharField(max_length=15, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    def __str__(self):
        full_name = self.get_full_name()
        display = full_name if full_name else self.username
        return f"{display} ({self.get_role_display()})"

    @property
    def is_admin_role(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def is_faculty_role(self):
        return self.role == self.ROLE_FACULTY

    @property
    def is_student_role(self):
        return self.role == self.ROLE_STUDENT

    @property
    def avatar_url(self):
        if self.profile_picture and hasattr(self.profile_picture, 'url'):
            return self.profile_picture.url
        return f"https://ui-avatars.com/api/?name={self.username}&background=4f46e5&color=fff&size=128"


class CollegeSetting(models.Model):
    """
    Singleton model storing Institutional Identity, Branding, and Global ERP Settings.
    Allows administrators to white-label the software for any college or university.
    """
    name = models.CharField(max_length=200, default="CampusConnect Institute of Technology")
    short_name = models.CharField(max_length=50, default="CampusConnect")
    college_code = models.CharField(max_length=30, default="CCIT-092")
    tagline = models.CharField(max_length=255, default="Excellence in Academic Innovation & Leadership")
    logo = models.ImageField(upload_to='college_branding/', blank=True, null=True)
    address = models.TextField(default="Academic City, Knowledge Park III, Tech District")
    email = models.EmailField(default="admin@campusconnect.edu")
    phone = models.CharField(max_length=30, default="+91 11 2345 6789")
    website = models.URLField(default="https://campusconnect.edu")
    affiliation = models.CharField(
        max_length=255,
        default="Approved by AICTE & Affiliated to State Technological University | NAAC 'A+' Accredited"
    )
    established_year = models.PositiveIntegerField(default=2000)
    attendance_threshold = models.PositiveIntegerField(default=75)
    principal_name = models.CharField(max_length=150, default="Dr. Alok Mukherjee (Principal)")
    footer_text = models.CharField(max_length=255, default="CampusConnect ERP - Complete Academic Management Platform")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "College Setting"
        verbose_name_plural = "College Settings"

    def __str__(self):
        return f"{self.name} ({self.college_code})"

    @classmethod
    def get_settings(cls):
        """Returns the active settings singleton or initializes default entry."""
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
