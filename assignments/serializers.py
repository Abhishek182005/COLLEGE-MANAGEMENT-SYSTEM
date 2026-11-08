from rest_framework import serializers
from .models import Assignment, Submission


class SubmissionSerializer(serializers.ModelSerializer):
    student_roll = serializers.CharField(source='student.roll_number', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)

    class Meta:
        model = Submission
        fields = ['id', 'assignment', 'student', 'student_roll', 'student_name', 'submission_file', 'student_notes', 'submitted_at', 'is_late', 'marks_obtained', 'faculty_feedback', 'status']


class AssignmentSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    faculty_name = serializers.CharField(source='faculty.full_name', read_only=True)
    submissions_count = serializers.IntegerField(source='total_submissions', read_only=True)

    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'description', 'subject', 'subject_code', 'subject_name',
            'faculty', 'faculty_name', 'semester', 'batch', 'attachment',
            'assigned_date', 'due_date', 'max_score', 'submissions_count', 'is_expired'
        ]
