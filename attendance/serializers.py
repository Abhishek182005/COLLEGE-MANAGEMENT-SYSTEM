from rest_framework import serializers
from .models import AttendanceSession, AttendanceRecord
from students.serializers import StudentSerializer


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_roll = serializers.CharField(source='student.roll_number', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = ['id', 'session', 'student', 'student_roll', 'student_name', 'status', 'marked_via', 'remarks', 'marked_at']


class AttendanceSessionSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    faculty_name = serializers.CharField(source='faculty.full_name', read_only=True)
    records = AttendanceRecordSerializer(many=True, read_only=True)

    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'subject', 'subject_code', 'subject_name', 'faculty', 'faculty_name',
            'semester', 'batch', 'date', 'lecture_slot', 'topic_covered',
            'qr_token', 'qr_expires_at', 'is_locked', 'records', 'total_students',
            'present_count', 'absent_count', 'attendance_percentage'
        ]
