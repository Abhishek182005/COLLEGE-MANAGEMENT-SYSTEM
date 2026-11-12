from django.urls import path
from . import views

urlpatterns = [
    path('analytics/', views.ReportsDashboardView.as_view(), name='reports_analytics'),
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_log_list'),
    path('final-ia/', views.final_ia_report_view, name='final_ia_report'),
    path('final-ia/pdf/', views.final_ia_report_pdf_view, name='final_ia_report_pdf'),
    path('final-ia/excel/', views.final_ia_report_excel_view, name='final_ia_report_excel'),
]
