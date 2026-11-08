from django.urls import path
from . import views

urlpatterns = [
    # Departments
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/add/', views.department_create_view, name='department_create'),
    path('departments/<int:pk>/', views.DepartmentDetailView.as_view(), name='department_detail'),
    path('departments/<int:pk>/edit/', views.department_edit_view, name='department_edit'),
    path('departments/<int:pk>/delete/', views.department_delete_view, name='department_delete'),

    # Courses
    path('courses/', views.CourseListView.as_view(), name='course_list'),
    path('courses/add/', views.course_create_view, name='course_create'),
    path('courses/<int:pk>/', views.CourseDetailView.as_view(), name='course_detail'),
    path('courses/<int:pk>/edit/', views.course_edit_view, name='course_edit'),
    path('courses/<int:pk>/delete/', views.course_delete_view, name='course_delete'),

    # Subjects
    path('subjects/', views.SubjectListView.as_view(), name='subject_list'),
    path('subjects/add/', views.subject_create_view, name='subject_create'),
    path('subjects/<int:pk>/', views.SubjectDetailView.as_view(), name='subject_detail'),
    path('subjects/<int:pk>/edit/', views.subject_edit_view, name='subject_edit'),
    path('subjects/<int:pk>/delete/', views.subject_delete_view, name='subject_delete'),
]
