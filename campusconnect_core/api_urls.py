from django.urls import path
from attendance.api_views import (
    QuickMarkAttendanceAPIView,
    QRGenerateAPIView,
    QRMarkAttendanceAPIView,
    OfflineSyncAttendanceAPIView
)
from timetable.api_views import TimetableConflictCheckAPIView
from examinations.api_views import BulkMarksEntryAPIView

urlpatterns = [
    # Attendance APIs
    path('attendance/quick-mark/', QuickMarkAttendanceAPIView.as_view(), name='api_quick_mark_attendance'),
    path('attendance/qr-generate/<int:session_id>/', QRGenerateAPIView.as_view(), name='api_qr_generate'),
    path('attendance/qr-mark/', QRMarkAttendanceAPIView.as_view(), name='api_qr_mark'),
    path('attendance/offline-sync/', OfflineSyncAttendanceAPIView.as_view(), name='api_offline_sync'),

    # Timetable conflict checker
    path('timetable/conflict-check/', TimetableConflictCheckAPIView.as_view(), name='api_timetable_conflict_check'),

    # Examinations bulk marks entry
    path('examinations/bulk-marks/', BulkMarksEntryAPIView.as_view(), name='api_bulk_marks_entry'),
]
