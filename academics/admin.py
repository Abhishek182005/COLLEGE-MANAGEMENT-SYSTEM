from django.contrib import admin
from .models import Department, Course, AcademicSession, Semester, Subject, SubjectAllocation


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'established_year']
    search_fields = ['name', 'code']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'department', 'duration_years', 'total_semesters']
    list_filter = ['department']


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current']


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ['course', 'semester_number', 'academic_session']
    list_filter = ['course', 'academic_session']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'semester', 'credits', 'subject_type']
    list_filter = ['subject_type', 'semester__course']
    search_fields = ['code', 'name']


@admin.register(SubjectAllocation)
class SubjectAllocationAdmin(admin.ModelAdmin):
    list_display = ['subject', 'faculty', 'academic_session', 'is_active']
    list_filter = ['is_active', 'academic_session']
