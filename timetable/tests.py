from datetime import date
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from academics.models import Department, Course, AcademicSession, Semester, Subject
from faculty.models import Faculty
from students.models import Batch
from timetable.models import Classroom, Timetable

User = get_user_model()


class TimetableConflictDetectionTests(TestCase):
    def setUp(self):
        self.session = AcademicSession.objects.create(
            name="2026-2027", start_date=date(2026, 7, 1), end_date=date(2027, 6, 30), is_current=True
        )
        self.dept = Department.objects.create(name="Computer Science", code="CSE")
        self.course = Course.objects.create(name="B.Tech CSE", code="BT-CSE", department=self.dept)
        self.sem = Semester.objects.create(course=self.course, semester_number=5, academic_session=self.session)
        self.batch_a = Batch.objects.create(name="Batch A", course=self.course, academic_session=self.session, section="A")
        self.batch_b = Batch.objects.create(name="Batch B", course=self.course, academic_session=self.session, section="B")

        self.subj1 = Subject.objects.create(code="CS501", name="Operating Systems", semester=self.sem)
        self.subj2 = Subject.objects.create(code="CS502", name="Computer Networks", semester=self.sem)

        self.room1 = Classroom.objects.create(room_number="LH-101", capacity=60)
        self.room2 = Classroom.objects.create(room_number="LH-102", capacity=60)

        # Faculty 1
        u1 = User.objects.create_user(username='fac1', password='Password123', role='FACULTY')
        self.fac1 = Faculty.objects.create(user=u1, employee_id="FAC001", department=self.dept)

        # Faculty 2
        u2 = User.objects.create_user(username='fac2', password='Password123', role='FACULTY')
        self.fac2 = Faculty.objects.create(user=u2, employee_id="FAC002", department=self.dept)

        # Baseline entry: Monday 09:00 - 10:00, fac1, room1, sem, batch_a, subj1
        self.entry1 = Timetable.objects.create(
            day_of_week=0,
            time_slot="09:00 - 10:00",
            subject=self.subj1,
            faculty=self.fac1,
            classroom=self.room1,
            semester=self.sem,
            batch=self.batch_a
        )

    def test_faculty_conflict_detection(self):
        """A faculty member cannot be scheduled in two places at the same day & time slot."""
        clashing_entry = Timetable(
            day_of_week=0,
            time_slot="09:00 - 10:00",
            subject=self.subj2,
            faculty=self.fac1,  # Same faculty!
            classroom=self.room2,  # Different room
            semester=self.sem,
            batch=self.batch_b
        )
        with self.assertRaises(ValidationError) as ctx:
            clashing_entry.clean()
        self.assertIn("Faculty Conflict", str(ctx.exception))

    def test_classroom_conflict_detection(self):
        """A classroom cannot be double-booked at the same day & time slot."""
        clashing_entry = Timetable(
            day_of_week=0,
            time_slot="09:00 - 10:00",
            subject=self.subj2,
            faculty=self.fac2,  # Different faculty
            classroom=self.room1,  # Same classroom!
            semester=self.sem,
            batch=self.batch_b
        )
        with self.assertRaises(ValidationError) as ctx:
            clashing_entry.clean()
        self.assertIn("Room Conflict", str(ctx.exception))

    def test_non_conflicting_schedule_success(self):
        """A class scheduled at a different time slot or day should succeed without errors."""
        valid_entry = Timetable(
            day_of_week=1,  # Tuesday
            time_slot="09:00 - 10:00",
            subject=self.subj2,
            faculty=self.fac1,
            classroom=self.room1,
            semester=self.sem,
            batch=self.batch_a
        )
        valid_entry.full_clean()
        valid_entry.save()
        self.assertIsNotNone(valid_entry.id)
