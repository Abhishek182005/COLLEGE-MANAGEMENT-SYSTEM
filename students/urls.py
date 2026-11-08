from django.urls import path
from . import views

urlpatterns = [
    path('', views.StudentListView.as_view(), name='student_list'),
    path('add/', views.student_create_view, name='student_create'),
    path('<int:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('<int:pk>/edit/', views.student_edit_view, name='student_edit'),
    path('<int:pk>/delete/', views.student_delete_view, name='student_delete'),
    path('<int:pk>/archive/', views.student_archive_view, name='student_archive'),
    path('<int:pk>/id-card/', views.student_id_card_pdf_view, name='student_id_card_pdf'),
    path('export/excel/', views.export_students_excel_view, name='export_students_excel'),
    path('import/excel/', views.import_students_excel_view, name='import_students_excel'),
]
