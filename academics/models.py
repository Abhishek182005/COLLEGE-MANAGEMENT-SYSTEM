from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    established_year = models.PositiveIntegerField(default=2000)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Course(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    duration_years = models.PositiveSmallIntegerField(default=4)
    total_semesters = models.PositiveSmallIntegerField(default=8)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code})"


class AcademicSession(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g. "2026-2027"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        status = " (Active)" if self.is_current else ""
        return f"{self.name}{status}"

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicSession.objects.exclude(id=self.id).update(is_current=False)
        super().save(*args, **kwargs)


class Semester(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='semesters')
    semester_number = models.PositiveSmallIntegerField()  # 1 to 8
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='semesters')

    class Meta:
        ordering = ['course', 'semester_number']
        unique_together = ('course', 'semester_number', 'academic_session')

    def __str__(self):
        return f"{self.course.code} - Sem {self.semester_number} ({self.academic_session.name})"


class Subject(models.Model):
    TYPE_THEORY = 'THEORY'
    TYPE_PRACTICAL = 'PRACTICAL'
    TYPE_HYBRID = 'HYBRID'
    TYPE_CHOICES = [
        (TYPE_THEORY, 'Theory'),
        (TYPE_PRACTICAL, 'Practical / Lab'),
        (TYPE_HYBRID, 'Hybrid'),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='subjects')
    credits = models.PositiveSmallIntegerField(default=4)
    subject_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_THEORY)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class SubjectAllocation(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='allocations')
    faculty = models.ForeignKey('faculty.Faculty', on_delete=models.CASCADE, related_name='allocated_subjects')
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='allocations')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('subject', 'faculty', 'academic_session')

    def __str__(self):
        return f"{self.subject.code} -> {self.faculty.user.get_full_name()} ({self.academic_session.name})"
