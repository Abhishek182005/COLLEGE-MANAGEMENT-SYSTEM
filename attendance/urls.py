from django.urls import path
from . import views

urlpatterns = [
    path('sessions/', views.AttendanceSessionListView.as_view(), name='attendance_session_list'),
    path('sessions/<int:pk>/', views.AttendanceSessionDetailView.as_view(), name='attendance_session_detail'),
    path('quick-mark/', views.quick_mark_attendance_view, name='quick_mark_attendance'),
    path('qr-scanner/', views.student_qr_attendance_view, name='student_qr_scanner'),
    path('shortage-report/', views.attendance_shortage_report_view, name='attendance_shortage_report'),
    path('sessions/<int:session_id>/export/excel/', views.export_attendance_excel_view, name='export_attendance_excel'),
]
