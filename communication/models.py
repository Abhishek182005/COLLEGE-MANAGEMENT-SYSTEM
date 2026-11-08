from django.db import models
from django.conf import settings
from django.utils import timezone
from academics.models import Department, Semester
from students.models import Batch


class Notice(models.Model):
    AUDIENCE_CHOICES = [
        ('ALL', 'All College Members'),
        ('FACULTY_ONLY', 'Faculty Only'),
        ('STUDENTS_ONLY', 'Students Only'),
        ('DEPARTMENT', 'Specific Department'),
        ('SEMESTER', 'Specific Semester'),
        ('BATCH', 'Specific Batch'),
    ]

    PRIORITY_CHOICES = [
        ('NORMAL', 'Normal'),
        ('HIGH', 'High Priority'),
        ('URGENT', 'Urgent / Important'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='published_notices')
    audience_type = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='ALL')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='notices')
    semester = models.ForeignKey(Semester, on_delete=models.SET_NULL, null=True, blank=True, related_name='notices')
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name='notices')
    priority = models.CharField(max_length=15, choices=PRIORITY_CHOICES, default='NORMAL')
    attachment = models.FileField(upload_to='notices/', blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.priority}] {self.title} ({self.get_audience_type_display()})"

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return timezone.now().date() > self.expiry_date


class NoticeRead(models.Model):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='reads')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='read_notices')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('notice', 'user')
        ordering = ['-read_at']

    def __str__(self):
        return f"{self.user.username} read notice #{self.notice.id} at {self.read_at.strftime('%Y-%m-%d %H:%M')}"
