from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import View, TemplateView
from django.db.models import Count, Avg, Q
from django.utils import timezone
from .models import CustomUser
from .permissions import AdminRequiredMixin, FacultyRequiredMixin, StudentRequiredMixin, role_required
from academics.models import Department, Course, Subject, AcademicSession, Semester
from faculty.models import Faculty
from students.models import Student, Batch
from attendance.models import AttendanceSession, AttendanceRecord
from timetable.models import Timetable
from examinations.models import Examination, Marks
from assignments.models import Assignment, Submission
from communication.models import Notice
from reports.models import AuditLog
from reports.utils import log_audit


class LoginCustomView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard_redirect')
        form = AuthenticationForm()
        return render(request, 'accounts/login.html', {'form': form})

    def post(self, request):
        username = request.POST.get('username')
        user_check = CustomUser.objects.filter(username=username).first()
        if user_check and not user_check.is_active:
            messages.error(request, "This account is inactive. Please contact the administrator.")
            form = AuthenticationForm(request)
            return render(request, 'accounts/login.html', {'form': form})

        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect('dashboard_redirect')
        else:
            messages.error(request, "Invalid username or password.")
            return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out safely.")
    return redirect('login')


@login_required
def dashboard_redirect(request):
    """Directs user to their specialized portal based on their role."""
    user = request.user
    if user.is_admin_role:
        return redirect('admin_dashboard')
    elif user.is_faculty_role:
        return redirect('faculty_dashboard')
    elif user.is_student_role:
        return redirect('student_dashboard')
    return redirect('login')


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    template_name = 'dashboards/admin_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()

        # Key metrics
        ctx['total_students'] = Student.objects.filter(is_archived=False).count()
        ctx['total_faculty'] = Faculty.objects.filter(is_active=True).count()
        ctx['total_departments'] = Department.objects.count()
        ctx['total_courses'] = Course.objects.count()

        # Today's attendance overview
        today_sessions = AttendanceSession.objects.filter(date=today)
        ctx['today_sessions_count'] = today_sessions.count()

        # Shortage students (< 75%)
        shortage_students = []
        for s in Student.objects.filter(is_archived=False).select_related('user', 'department', 'course', 'current_semester')[:30]:
            stats = s.get_attendance_stats()
            if stats['shortage'] and stats['total'] > 0:
                shortage_students.append({
                    'student': s,
                    'percentage': stats['percentage'],
                    'total': stats['total'],
                    'present': stats['present'],
                })
        ctx['shortage_students'] = shortage_students[:10]
        ctx['shortage_count'] = len(shortage_students)

        # Recent notices
        ctx['recent_notices'] = Notice.objects.all().order_by('-created_at')[:5]

        # Recent audit logs
        ctx['recent_audits'] = AuditLog.objects.select_related('user').all()[:8]

        # Department distribution
        dept_dist = Department.objects.annotate(student_count=Count('students')).values('name', 'code', 'student_count')
        ctx['dept_distribution'] = list(dept_dist)

        return ctx


class FacultyDashboardView(FacultyRequiredMixin, TemplateView):
    template_name = 'dashboards/faculty_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        faculty = getattr(self.request.user, 'faculty_profile', None)
        ctx['faculty'] = faculty

        if faculty:
            # Allocated subjects
            ctx['allocated_subjects'] = faculty.allocated_subjects.filter(is_active=True).select_related('subject', 'subject__semester')

            # Today's Timetable
            today_weekday = timezone.now().weekday()  # 0=Monday
            ctx['today_schedule'] = Timetable.objects.filter(
                faculty=faculty,
                day_of_week=today_weekday
            ).select_related('subject', 'classroom', 'semester', 'batch').order_by('time_slot')

            # Recent attendance sessions taken
            ctx['recent_sessions'] = AttendanceSession.objects.filter(
                faculty=faculty
            ).select_related('subject', 'semester', 'batch').order_by('-date', '-created_at')[:5]

            # Pending assignment submissions to grade
            ctx['pending_submissions'] = Submission.objects.filter(
                assignment__faculty=faculty,
                status='PENDING'
            ).select_related('assignment', 'student__user').count()

            # Active assignments
            ctx['my_assignments'] = Assignment.objects.filter(
                faculty=faculty
            ).select_related('subject', 'semester').order_by('-created_at')[:5]

        # Notices relevant to faculty
        ctx['notices'] = Notice.objects.filter(
            Q(audience_type='ALL') |
            Q(audience_type='FACULTY_ONLY') |
            (Q(audience_type='DEPARTMENT') & Q(department=faculty.department if faculty else None))
        ).order_by('-created_at')[:5]

        return ctx


class StudentDashboardView(StudentRequiredMixin, TemplateView):
    template_name = 'dashboards/student_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        student = getattr(self.request.user, 'student_profile', None)
        ctx['student'] = student

        if student:
            # Attendance Stats
            ctx['attendance_stats'] = student.get_attendance_stats()

            # Today's timetable
            today_weekday = timezone.now().weekday()
            ctx['today_classes'] = Timetable.objects.filter(
                semester=student.current_semester,
                day_of_week=today_weekday
            ).filter(Q(batch=student.batch) | Q(batch__isnull=True)).select_related('subject', 'faculty', 'classroom').order_by('time_slot')

            # Pending assignments
            submitted_ids = Submission.objects.filter(student=student).values_list('assignment_id', flat=True)
            ctx['pending_assignments'] = Assignment.objects.filter(
                semester=student.current_semester
            ).exclude(id__in=submitted_ids).order_by('due_date')[:5]

            # Recent exam marks
            ctx['recent_marks'] = Marks.objects.filter(
                student=student
            ).select_related('assessment_component__examination', 'assessment_component__subject').order_by('-assessment_component__examination__start_date')[:6]

            # Filtered notices
            ctx['notices'] = Notice.objects.filter(
                Q(audience_type='ALL') |
                Q(audience_type='STUDENTS_ONLY') |
                Q(audience_type='DEPARTMENT', department=student.department) |
                Q(audience_type='SEMESTER', semester=student.current_semester) |
                Q(audience_type='BATCH', batch=student.batch)
            ).order_by('-created_at')[:6]

        return ctx


@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', user.phone)
        user.address = request.POST.get('address', user.address)
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
        user.save()
        messages.success(request, "Profile updated successfully.")
        return redirect('profile')

    return render(request, 'accounts/profile.html', {'user': user})


@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully.")
            return redirect('profile')
        else:
            messages.error(request, "Please correct the error below.")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {'form': form})


class UserManagementView(AdminRequiredMixin, TemplateView):
    template_name = 'accounts/user_management.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        role_filter = self.request.GET.get('role', '')
        search_q = self.request.GET.get('q', '')

        users = CustomUser.objects.all().order_by('-date_joined')
        if role_filter:
            users = users.filter(role=role_filter)
        if search_q:
            users = users.filter(
                Q(username__icontains=search_q) |
                Q(first_name__icontains=search_q) |
                Q(last_name__icontains=search_q) |
                Q(email__icontains=search_q)
            )

        ctx['users_list'] = users[:50]
        ctx['current_role'] = role_filter
        ctx['search_query'] = search_q
        return ctx


@login_required
@role_required('ADMIN')
def toggle_user_active(request, user_id):
    target_user = get_object_or_404(CustomUser, id=user_id)
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect('user_management')

    target_user.is_active = not target_user.is_active
    target_user.save()

    status_str = "activated" if target_user.is_active else "deactivated"
    log_audit(
        request=request,
        action="USER_STATUS_TOGGLED",
        entity_type="CustomUser",
        entity_id=target_user.id,
        details=f"User {target_user.username} was {status_str} by admin {request.user.username}."
    )
    messages.success(request, f"User {target_user.username} has been {status_str}.")
    return redirect('user_management')
