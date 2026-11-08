from django.urls import path
from . import views

urlpatterns = [
    path('', views.AssignmentListView.as_view(), name='assignment_list'),
    path('add/', views.assignment_create_view, name='assignment_create'),
    path('<int:pk>/', views.AssignmentDetailView.as_view(), name='assignment_detail'),
    path('<int:pk>/submit/', views.submit_assignment_view, name='submit_assignment'),
    path('submission/<int:submission_id>/grade/', views.grade_submission_view, name='grade_submission'),
]
