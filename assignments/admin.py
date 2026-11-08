from django.contrib import admin
from .models import Assignment, Submission


class SubmissionInline(admin.TabularInline):
    model = Submission
    extra = 0
    fields = ['student', 'submitted_at', 'is_late', 'marks_obtained', 'status']
    readonly_fields = ['submitted_at', 'is_late']


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'faculty', 'semester', 'due_date', 'max_score']
    list_filter = ['semester', 'subject']
    search_fields = ['title', 'subject__code']
    inlines = [SubmissionInline]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['assignment', 'student', 'submitted_at', 'is_late', 'marks_obtained', 'status']
    list_filter = ['status', 'is_late']
    search_fields = ['student__roll_number', 'assignment__title']
