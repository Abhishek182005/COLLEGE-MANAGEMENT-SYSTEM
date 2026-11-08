from django.contrib import admin
from .models import Batch, Student


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'section', 'academic_session']
    list_filter = ['course', 'academic_session']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['roll_number', 'registration_number', 'user', 'department', 'course', 'current_semester', 'batch', 'is_archived']
    list_filter = ['department', 'course', 'current_semester', 'is_archived', 'batch']
    search_fields = ['roll_number', 'registration_number', 'user__first_name', 'user__last_name', 'user__username']
