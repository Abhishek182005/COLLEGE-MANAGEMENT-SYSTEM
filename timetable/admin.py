from django.contrib import admin
from .models import Classroom, Timetable


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ['room_number', 'building', 'floor', 'capacity', 'room_type']
    list_filter = ['room_type', 'building']


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ['day_of_week', 'time_slot', 'subject', 'faculty', 'classroom', 'semester', 'batch']
    list_filter = ['day_of_week', 'time_slot', 'classroom', 'semester']
    search_fields = ['subject__code', 'faculty__user__first_name', 'classroom__room_number']
