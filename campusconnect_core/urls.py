from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from accounts import views as account_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Redirect root to dashboard router
    path('', lambda request: redirect('dashboard_redirect'), name='home'),
    path('dashboard/', account_views.dashboard_redirect, name='dashboard_redirect'),
    path('dashboard/admin/', account_views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('dashboard/faculty/', account_views.FacultyDashboardView.as_view(), name='faculty_dashboard'),
    path('dashboard/student/', account_views.StudentDashboardView.as_view(), name='student_dashboard'),

    # Modular application routes
    path('accounts/', include('accounts.urls')),
    path('academics/', include('academics.urls')),
    path('students/', include('students.urls')),
    path('faculty/', include('faculty.urls')),
    path('attendance/', include('attendance.urls')),
    path('timetable/', include('timetable.urls')),
    path('examinations/', include('examinations.urls')),
    path('assignments/', include('assignments.urls')),
    path('communication/', include('communication.urls')),
    path('reports/', include('reports.urls')),

    # REST APIs
    path('api/', include('campusconnect_core.api_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
