import uuid
from django.db import models
from django.utils import timezone
from academics.models import Subject, Semester
from faculty.models import Faculty
from students.models import Student, Batch


class AttendanceSession(models.Model):
    SESSION_THEORY = 'TE'
    SESSION_PRACTICAL = 'PR'
    SESSION_TUTORIAL = 'TU'
    SESSION_TYPE_CHOICES = [
        (SESSION_THEORY, 'Theory (TE)'),
        (SESSION_PRACTICAL, 'Practical (PR)'),
        (SESSION_TUTORIAL, 'Tutorial (TU)'),
    ]

    SLOT_CHOICES = [
        ('09:00 - 10:00', '09:00 AM - 10:00 AM'),
        ('10:00 - 11:00', '10:00 AM - 11:00 AM'),
        ('11:15 - 12:15', '11:15 AM - 12:15 PM'),
        ('12:15 - 01:15', '12:15 PM - 01:15 PM'),
        ('02:00 - 03:00', '02:00 PM - 03:00 PM'),
        ('03:00 - 04:00', '03:00 PM - 04:00 PM'),
        ('04:00 - 05:00', '04:00 PM - 05:00 PM'),
    ]

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='attendance_sessions')
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='conducted_sessions')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='attendance_sessions')
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_sessions')
    session_type = models.CharField(
        max_length=10,
        choices=SESSION_TYPE_CHOICES,
        default=SESSION_THEORY,
        help_text="Demarcation of lecture type: Theory (TE), Practical (PR), or Tutorial (TU)"
    )
    date = models.DateField(default=timezone.now)
    lecture_slot = models.CharField(max_length=30, choices=SLOT_CHOICES, default='09:00 - 10:00')
    topic_covered = models.CharField(max_length=255, blank=True, null=True)
    qr_token = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    qr_expires_at = models.DateTimeField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        batch_name = f" [{self.batch.name}]" if self.batch else ""
        return f"{self.subject.code} [{self.session_type}] - {self.date} ({self.lecture_slot}){batch_name} by {self.faculty.full_name}"

    def save(self, *args, **kwargs):
        # Auto-set session_type from subject paper_type_code if default
        if not self.session_type and self.subject:
            self.session_type = self.subject.paper_type_code
        super().save(*args, **kwargs)

    @property
    def total_students(self):
        return self.records.count()

    @property
    def present_count(self):
        return self.records.filter(status__in=['PRESENT', 'LATE']).count()

    @property
    def absent_count(self):
        return self.records.filter(status='ABSENT').count()

    @property
    def attendance_percentage(self):
        total = self.total_students
        if total == 0:
            return 0.0
        return round((self.present_count / total) * 100, 1)

    def is_qr_valid(self):
        if not self.qr_expires_at:
            return False
        return timezone.now() <= self.qr_expires_at


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
        ('EXCUSED', 'Excused / On Duty'),
    ]

    BENEFIT_NONE = 'NONE'
    BENEFIT_MED = 'MED'        # Bft. Med
    BENEFIT_ECA = 'ECA'        # Bft. ECA
    BENEFIT_SPORTS = 'SPORTS'  # Bft. Sports
    BENEFIT_NCC = 'NCC'        # Bft. NCC
    BENEFIT_NSS = 'NSS'        # Bft. NSS

    BENEFIT_CHOICES = [
        (BENEFIT_NONE, 'None'),
        (BENEFIT_MED, 'Medical (Bft. Med)'),
        (BENEFIT_ECA, 'ECA (Bft. ECA)'),
        (BENEFIT_SPORTS, 'Sports (Bft. Sports)'),
        (BENEFIT_NCC, 'NCC (Bft. NCC)'),
        (BENEFIT_NSS, 'NSS (Bft. NSS)'),
    ]

    METHOD_CHOICES = [
        ('MANUAL', 'Manual'),
        ('QR_CODE', 'QR Code Scan'),
        ('OFFLINE_SYNC', 'Offline Sync'),
    ]

    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PRESENT')
    benefit_type = models.CharField(
        max_length=10,
        choices=BENEFIT_CHOICES,
        default=BENEFIT_NONE,
        help_text="Official attendance benefit/waiver (Medical, ECA, Sports, NCC, NSS)"
    )
    marked_via = models.CharField(max_length=20, choices=METHOD_CHOICES, default='MANUAL')
    remarks = models.CharField(max_length=200, blank=True, null=True)
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('session', 'student')
        ordering = ['student__roll_number']

    def __str__(self):
        bft_label = f" [{self.get_benefit_type_display()}]" if self.benefit_type != 'NONE' else ""
        return f"{self.student.roll_number} - {self.session.subject.code}: {self.status}{bft_label}"

    @property
    def is_attended(self):
        return self.status in ['PRESENT', 'LATE']
