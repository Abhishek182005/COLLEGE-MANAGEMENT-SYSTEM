from rest_framework import serializers
from .models import Faculty
from accounts.serializers import CustomUserSerializer


class FacultySerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    designation_display = serializers.CharField(source='get_designation_display', read_only=True)

    class Meta:
        model = Faculty
        fields = [
            'id', 'user', 'employee_id', 'department', 'department_name',
            'designation', 'designation_display', 'qualification', 'cabin_number',
            'emergency_contact', 'is_active'
        ]
