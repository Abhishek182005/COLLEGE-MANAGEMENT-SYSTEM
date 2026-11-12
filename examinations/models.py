from django.db import models
from decimal import Decimal
from academics.models import AcademicSession, Subject
from students.models import Student
from faculty.models import Faculty


class Examination(models.Model):
    EXAM_TYPES = [
        ('MID_TERM', 'Mid-Term Examination'),
        ('END_TERM', 'End-Term / Semester Final'),
        ('CLASS_TEST', 'Class Test / Quiz'),
        ('PRACTICAL', 'Practical / Lab Exam'),
    ]

    name = models.CharField(max_length=150)
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='examinations')
    exam_type = models.CharField(max_length=30, choices=EXAM_TYPES, default='MID_TERM')
    start_date = models.DateField()
    end_date = models.DateField()
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        status = " (Published)" if self.is_published else " (Draft)"
        return f"{self.name} - {self.academic_session.name}{status}"


class AssessmentComponent(models.Model):
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name='components')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assessment_components')
    title = models.CharField(max_length=120)  # e.g., "Written Exam", "Practical / Viva", "Internal Test"
    max_marks = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))
    pass_marks = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('40.00'))
    weightage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'), help_text="Weightage percentage")

    class Meta:
        ordering = ['subject', 'title']
        unique_together = ('examination', 'subject', 'title')

    def __str__(self):
        return f"{self.examination.name}: {self.subject.code} - {self.title} (Max: {self.max_marks})"


class Marks(models.Model):
    assessment_component = models.ForeignKey(AssessmentComponent, on_delete=models.CASCADE, related_name='marks_records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_marks')
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=5, blank=True)
    remarks = models.CharField(max_length=200, blank=True, null=True)
    graded_by = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('assessment_component', 'student')
        ordering = ['student__roll_number']

    def __str__(self):
        return f"{self.student.roll_number} - {self.assessment_component.subject.code}: {self.marks_obtained}/{self.assessment_component.max_marks} ({self.grade})"

    def calculate_grade(self):
        max_m = self.assessment_component.max_marks
        if max_m <= 0:
            return 'F'
        pct = (self.marks_obtained / max_m) * 100
        if pct >= 90:
            return 'A+'
        elif pct >= 80:
            return 'A'
        elif pct >= 70:
            return 'B+'
        elif pct >= 60:
            return 'B'
        elif pct >= 50:
            return 'C'
        elif pct >= 40:
            return 'D'
        else:
            return 'F'

    def save(self, *args, **kwargs):
        self.grade = self.calculate_grade()
        super().save(*args, **kwargs)


class InternalAssessmentRecord(models.Model):
    """Stores customizable/confirmed Internal Assessment (IA) marks for Final IA Report (Course Wise)."""
    CONFIRM_CHOICES = [
        ('', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='ia_records')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='ia_records')
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.SET_NULL, null=True, blank=True)
    max_ia_marks = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('30.00'))
    attd_max_marks = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal('6.0'))
    final_attd_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    marks_ct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    marks_assi = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    moderation_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    confirm_status = models.CharField(max_length=20, choices=CONFIRM_CHOICES, blank=True, default='')
    confirm_date = models.DateField(null=True, blank=True)
    updated_by = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'subject')
        ordering = ['student__roll_number', 'subject__code']

    def __str__(self):
        return f"IA: {self.student.roll_number} - {self.subject.code}"
