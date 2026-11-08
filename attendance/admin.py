from django.contrib import admin
from .models import AttendanceSession, AttendanceRecord


class AttendanceRecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0
    fields = ['student', 'status', 'marked_via', 'remarks', 'marked_at']
    readonly_fields = ['marked_at']


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ['subject', 'faculty', 'date', 'lecture_slot', 'batch', 'attendance_percentage', 'is_locked']
    list_filter = ['date', 'lecture_slot', 'is_locked']
    search_fields = ['subject__code', 'faculty__user__first_name', 'topic_covered']
    inlines = [AttendanceRecordInline]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['session', 'student', 'status', 'marked_via', 'marked_at']
    list_filter = ['status', 'marked_via', 'session__date']
    search_fields = ['student__roll_number', 'student__user__first_name']
