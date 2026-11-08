from django.urls import path
from . import views

urlpatterns = [
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/add/', views.department_create_view, name='department_create'),
    path('courses/', views.CourseListView.as_view(), name='course_list'),
    path('courses/add/', views.course_create_view, name='course_create'),
    path('subjects/', views.SubjectListView.as_view(), name='subject_list'),
    path('subjects/add/', views.subject_create_view, name='subject_create'),
]
