from django.db import models
from django.conf import settings
from academics.models import Department, Course, Semester, AcademicSession


class Batch(models.Model):
    name = models.CharField(max_length=100)  # e.g. "Batch 2024-2028"
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='batches')
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='batches')
    section = models.CharField(max_length=10, default="A")

    class Meta:
        verbose_name_plural = "Batches"
        ordering = ['course', 'name', 'section']
        unique_together = ('name', 'course', 'section')

    def __str__(self):
        return f"{self.name} - Sec {self.section} ({self.course.code})"


class Student(models.Model):
    BLOOD_GROUPS = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_profile')
    roll_number = models.CharField(max_length=30, unique=True)
    registration_number = models.CharField(max_length=50, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='students')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='students')
    current_semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='enrolled_students')
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='students')
    admission_date = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUPS, blank=True, null=True)
    guardian_name = models.CharField(max_length=120, blank=True, null=True)
    guardian_phone = models.CharField(max_length=20, blank=True, null=True)
    documents = models.FileField(upload_to='student_docs/', blank=True, null=True)
    is_archived = models.BooleanField(default=False)  # Safe archival / soft delete

    class Meta:
        ordering = ['roll_number']

    def __str__(self):
        name = self.user.get_full_name() or self.user.username
        return f"{self.roll_number} - {name} ({self.course.code})"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def email(self):
        return self.user.email

    @property
    def phone(self):
        return self.user.phone

    def get_attendance_stats(self):
        from attendance.models import AttendanceRecord
        records = AttendanceRecord.objects.filter(student=self)
        total = records.count()
        if total == 0:
            return {'total': 0, 'present': 0, 'absent': 0, 'late': 0, 'percentage': 0.0, 'shortage': False}
        present_count = records.filter(status__in=['PRESENT', 'LATE']).count()
        absent_count = records.filter(status='ABSENT').count()
        late_count = records.filter(status='LATE').count()
        pct = round((present_count / total) * 100, 2)
        shortage = pct < getattr(settings, 'ATTENDANCE_SHORTAGE_THRESHOLD', 75.0)
        return {
            'total': total,
            'present': present_count,
            'absent': absent_count,
            'late': late_count,
            'percentage': pct,
            'shortage': shortage,
        }
