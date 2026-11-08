from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Timetable, Classroom
from faculty.models import Faculty
from academics.models import Semester, Subject
from students.models import Batch


class TimetableConflictCheckAPIView(APIView):
    """
    Checks for conflicts in faculty, classroom, and semester/batch before saving a timetable entry.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        day = request.data.get('day_of_week')
        slot = request.data.get('time_slot')
        faculty_id = request.data.get('faculty_id')
        classroom_id = request.data.get('classroom_id')
        semester_id = request.data.get('semester_id')
        batch_id = request.data.get('batch_id')
        exclude_id = request.data.get('exclude_id')

        if day is None or not slot:
            return Response({'error': 'day_of_week and time_slot are required.'}, status=status.HTTP_400_BAD_REQUEST)

        conflicts = []

        # 1. Faculty Conflict
        if faculty_id:
            qs = Timetable.objects.filter(day_of_week=day, time_slot=slot, faculty_id=faculty_id)
            if exclude_id:
                qs = qs.exclude(id=exclude_id)
            if qs.exists():
                c = qs.first()
                conflicts.append({
                    'type': 'FACULTY_CLASH',
                    'message': f"Faculty {c.faculty.full_name} is already teaching {c.subject.code} in Room {c.classroom.room_number}."
                })

        # 2. Classroom Conflict
        if classroom_id:
            qs = Timetable.objects.filter(day_of_week=day, time_slot=slot, classroom_id=classroom_id)
            if exclude_id:
                qs = qs.exclude(id=exclude_id)
            if qs.exists():
                c = qs.first()
                conflicts.append({
                    'type': 'ROOM_CLASH',
                    'message': f"Room {c.classroom.room_number} is already occupied by {c.subject.name} (Faculty: {c.faculty.full_name})."
                })

        # 3. Semester / Batch Conflict
        if semester_id:
            qs = Timetable.objects.filter(day_of_week=day, time_slot=slot, semester_id=semester_id)
            if batch_id:
                qs = qs.filter(batch_id=batch_id)
            if exclude_id:
                qs = qs.exclude(id=exclude_id)
            if qs.exists():
                c = qs.first()
                conflicts.append({
                    'type': 'BATCH_CLASH',
                    'message': f"Semester {c.semester.semester_number} is already scheduled for {c.subject.name}."
                })

        return Response({
            'has_conflict': len(conflicts) > 0,
            'conflicts': conflicts
        }, status=status.HTTP_200_OK)
