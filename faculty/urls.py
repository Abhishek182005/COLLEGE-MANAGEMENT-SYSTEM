from django.urls import path
from . import views

urlpatterns = [
    path('', views.FacultyListView.as_view(), name='faculty_list'),
    path('add/', views.faculty_create_view, name='faculty_create'),
    path('<int:pk>/', views.FacultyDetailView.as_view(), name='faculty_detail'),
]
