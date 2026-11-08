from rest_framework import serializers
from .models import Examination, AssessmentComponent, Marks


class AssessmentComponentSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = AssessmentComponent
        fields = ['id', 'examination', 'subject', 'subject_code', 'subject_name', 'title', 'max_marks', 'pass_marks', 'weightage']


class ExaminationSerializer(serializers.ModelSerializer):
    components = AssessmentComponentSerializer(many=True, read_only=True)
    session_name = serializers.CharField(source='academic_session.name', read_only=True)

    class Meta:
        model = Examination
        fields = ['id', 'name', 'academic_session', 'session_name', 'exam_type', 'start_date', 'end_date', 'is_published', 'components']


class MarksSerializer(serializers.ModelSerializer):
    student_roll = serializers.CharField(source='student.roll_number', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    component_title = serializers.CharField(source='assessment_component.title', read_only=True)
    max_marks = serializers.DecimalField(source='assessment_component.max_marks', max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = Marks
        fields = ['id', 'assessment_component', 'component_title', 'max_marks', 'student', 'student_roll', 'student_name', 'marks_obtained', 'grade', 'remarks']
