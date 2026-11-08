from rest_framework import serializers
from .models import Classroom, Timetable


class ClassroomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = ['id', 'room_number', 'building', 'floor', 'capacity', 'room_type']


class TimetableSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    faculty_name = serializers.CharField(source='faculty.full_name', read_only=True)
    room_number = serializers.CharField(source='classroom.room_number', read_only=True)

    class Meta:
        model = Timetable
        fields = [
            'id', 'day_of_week', 'day_name', 'time_slot', 'subject', 'subject_code',
            'subject_name', 'faculty', 'faculty_name', 'classroom', 'room_number',
            'semester', 'batch'
        ]
