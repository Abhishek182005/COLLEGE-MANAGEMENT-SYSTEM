from rest_framework import serializers
from .models import Student, Batch
from accounts.serializers import CustomUserSerializer


class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = ['id', 'name', 'section', 'course']


class StudentSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)
    semester_num = serializers.IntegerField(source='current_semester.semester_number', read_only=True)
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    attendance_stats = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'user', 'roll_number', 'registration_number', 'department', 'department_name',
            'course', 'course_code', 'current_semester', 'semester_num', 'batch', 'batch_name',
            'blood_group', 'is_archived', 'attendance_stats'
        ]

    def get_attendance_stats(self, obj):
        return obj.get_attendance_stats()
