from django.contrib import admin
from django.urls import path, include, re_path
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
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

# Media files serving (works seamlessly in local development and production cloud deployment e.g. Render)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
