from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=60)  # e.g., ATTENDANCE_CORRECTION, MARKS_MODIFIED, STUDENT_ARCHIVED
    entity_type = models.CharField(max_length=60)  # e.g., AttendanceRecord, Marks, Student
    entity_id = models.CharField(max_length=60)
    details = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        user_name = self.user.username if self.user else "System"
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {user_name} - {self.action} on {self.entity_type} #{self.entity_id}"
