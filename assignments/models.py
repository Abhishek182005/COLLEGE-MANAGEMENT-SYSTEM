from django.db import models
from django.utils import timezone
from academics.models import Subject, Semester
from faculty.models import Faculty
from students.models import Student, Batch


class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='created_assignments')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='assignments')
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name='assignments')
    attachment = models.FileField(upload_to='assignments/tasks/', blank=True, null=True)
    assigned_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField()
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-due_date']

    def __str__(self):
        return f"{self.subject.code}: {self.title} (Due: {self.due_date.strftime('%Y-%m-%d')})"

    @property
    def total_submissions(self):
        return self.submissions.count()

    @property
    def is_expired(self):
        return timezone.now() > self.due_date


class Submission(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Evaluation'),
        ('GRADED', 'Graded'),
        ('RESUBMIT_REQUESTED', 'Resubmission Requested'),
    ]

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='assignment_submissions')
    submission_file = models.FileField(upload_to='assignments/submissions/')
    student_notes = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    is_late = models.BooleanField(default=False)
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    faculty_feedback = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='PENDING')

    class Meta:
        unique_together = ('assignment', 'student')
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.student.roll_number} - {self.assignment.title} ({self.status})"

    def save(self, *args, **kwargs):
        if self.submitted_at and self.assignment.due_date:
            self.is_late = self.submitted_at > self.assignment.due_date
        super().save(*args, **kwargs)
