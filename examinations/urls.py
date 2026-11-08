from django.urls import path
from . import views

urlpatterns = [
    path('', views.ExaminationListView.as_view(), name='examination_list'),
    path('add/', views.exam_create_view, name='exam_create'),
    path('<int:pk>/delete/', views.exam_delete_view, name='exam_delete'),
    path('<int:pk>/toggle-publish/', views.toggle_exam_publish, name='toggle_exam_publish'),
    path('component/<int:component_id>/marks/', views.marks_entry_view, name='marks_entry'),
    path('results/', views.student_results_view, name='student_results'),
    path('results/exam/<int:exam_id>/pdf/', views.download_marksheet_pdf_view, name='download_marksheet_pdf'),
]
