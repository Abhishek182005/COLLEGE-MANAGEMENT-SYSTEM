from django.urls import path
from . import views

urlpatterns = [
    path('analytics/', views.ReportsDashboardView.as_view(), name='reports_analytics'),
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_log_list'),
]
