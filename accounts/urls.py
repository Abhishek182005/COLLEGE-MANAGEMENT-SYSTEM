from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.LoginCustomView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('users/', views.UserManagementView.as_view(), name='user_management'),
    path('users/<int:user_id>/toggle/', views.toggle_user_active, name='toggle_user_active'),
    path('college-settings/', views.college_settings_view, name='college_settings'),
]
