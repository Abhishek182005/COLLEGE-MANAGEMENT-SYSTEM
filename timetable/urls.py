from django.urls import path
from . import views

urlpatterns = [
    path('', views.TimetableMasterView.as_view(), name='timetable_master'),
    path('my/', views.my_timetable_view, name='my_timetable'),
    path('add/', views.timetable_create_view, name='timetable_create'),
    path('<int:pk>/delete/', views.timetable_delete_view, name='timetable_delete'),
]
