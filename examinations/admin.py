from django.contrib import admin
from .models import Examination, AssessmentComponent, Marks


class AssessmentComponentInline(admin.TabularInline):
    model = AssessmentComponent
    extra = 1


@admin.register(Examination)
class ExaminationAdmin(admin.ModelAdmin):
    list_display = ['name', 'academic_session', 'exam_type', 'start_date', 'end_date', 'is_published']
    list_filter = ['exam_type', 'is_published', 'academic_session']
    inlines = [AssessmentComponentInline]


@admin.register(AssessmentComponent)
class AssessmentComponentAdmin(admin.ModelAdmin):
    list_display = ['examination', 'subject', 'title', 'max_marks', 'pass_marks', 'weightage']
    list_filter = ['examination', 'subject']


@admin.register(Marks)
class MarksAdmin(admin.ModelAdmin):
    list_display = ['assessment_component', 'student', 'marks_obtained', 'grade', 'graded_by', 'updated_at']
    list_filter = ['grade', 'assessment_component__examination']
    search_fields = ['student__roll_number', 'student__user__first_name']
