from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages
from rest_framework import permissions


class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_admin_role

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        messages.error(self.request, "Access denied: Administrator privileges required.")
        return redirect('dashboard_redirect')


class FacultyRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_faculty_role or self.request.user.is_admin_role)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        messages.error(self.request, "Access denied: Faculty privileges required.")
        return redirect('dashboard_redirect')


class StudentRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_student_role or self.request.user.is_admin_role)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        messages.error(self.request, "Access denied: Student access only.")
        return redirect('dashboard_redirect')


def role_required(*allowed_roles):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.role in allowed_roles or request.user.is_superuser or ('ADMIN' in allowed_roles and request.user.is_staff):
                return view_func(request, *args, **kwargs)
            messages.error(request, "Permission denied for this operation.")
            return redirect('dashboard_redirect')
        return _wrapped_view
    return decorator


# DRF API Permissions
class IsAdminUserRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin_role)


class IsFacultyUserRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_faculty_role or request.user.is_admin_role))


class IsStudentUserRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_student_role)
