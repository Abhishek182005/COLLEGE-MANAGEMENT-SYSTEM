from django.db import models
from django.core.exceptions import ValidationError
from academics.models import Subject, Semester
from faculty.models import Faculty
from students.models import Batch


class Classroom(models.Model):
    ROOM_TYPES = [
        ('LECTURE_HALL', 'Lecture Hall'),
        ('COMPUTER_LAB', 'Computer Laboratory'),
        ('ELECTRONICS_LAB', 'Electronics Laboratory'),
        ('WORKSHOP', 'Workshop'),
        ('SEMINAR_HALL', 'Seminar Hall'),
    ]

    room_number = models.CharField(max_length=30, unique=True)
    building = models.CharField(max_length=100, default='Main Academic Block')
    floor = models.CharField(max_length=20, default='Ground Floor')
    capacity = models.PositiveIntegerField(default=60)
    room_type = models.CharField(max_length=30, choices=ROOM_TYPES, default='LECTURE_HALL')

    class Meta:
        ordering = ['building', 'room_number']

    def __str__(self):
        return f"{self.room_number} ({self.building} - Cap: {self.capacity})"


class Timetable(models.Model):
    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
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

    day_of_week = models.PositiveSmallIntegerField(choices=DAYS_OF_WEEK)
    time_slot = models.CharField(max_length=30, choices=SLOT_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='timetable_entries')
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='timetable_entries')
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='timetable_entries')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='timetable_entries')
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name='timetable_entries')

    class Meta:
        ordering = ['day_of_week', 'time_slot']

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.time_slot}: {self.subject.code} in {self.classroom.room_number}"

    def clean(self):
        # 1. Faculty Conflict Detection
        faculty_clashes = Timetable.objects.filter(
            day_of_week=self.day_of_week,
            time_slot=self.time_slot,
            faculty=self.faculty
        )
        if self.pk:
            faculty_clashes = faculty_clashes.exclude(pk=self.pk)
        if faculty_clashes.exists():
            clash = faculty_clashes.first()
            raise ValidationError(
                f"Faculty Conflict: {self.faculty.full_name} is already assigned to {clash.subject.name} in Room {clash.classroom.room_number} on {self.get_day_of_week_display()} at {self.time_slot}."
            )

        # 2. Classroom Conflict Detection
        room_clashes = Timetable.objects.filter(
            day_of_week=self.day_of_week,
            time_slot=self.time_slot,
            classroom=self.classroom
        )
        if self.pk:
            room_clashes = room_clashes.exclude(pk=self.pk)
        if room_clashes.exists():
            clash = room_clashes.first()
            raise ValidationError(
                f"Room Conflict: Classroom {self.classroom.room_number} is already occupied by {clash.subject.name} (Faculty: {clash.faculty.full_name}) on {self.get_day_of_week_display()} at {self.time_slot}."
            )

        # 3. Semester / Batch Conflict Detection
        batch_clashes = Timetable.objects.filter(
            day_of_week=self.day_of_week,
            time_slot=self.time_slot,
            semester=self.semester
        )
        if self.batch:
            batch_clashes = batch_clashes.filter(batch=self.batch)
        if self.pk:
            batch_clashes = batch_clashes.exclude(pk=self.pk)
        if batch_clashes.exists():
            clash = batch_clashes.first()
            raise ValidationError(
                f"Class/Batch Conflict: {self.semester} is already scheduled for {clash.subject.name} on {self.get_day_of_week_display()} at {self.time_slot}."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
