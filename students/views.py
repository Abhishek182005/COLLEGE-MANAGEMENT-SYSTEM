from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.urls import reverse_lazy
from django.http import HttpResponse
from django.db.models import Q
from .models import Student, Batch
from accounts.models import CustomUser
from academics.models import Department, Course, Semester
from accounts.permissions import AdminRequiredMixin, FacultyRequiredMixin, role_required
from reports.utils import (
    generate_student_id_card_pdf,
    export_students_to_excel,
    parse_and_import_students_excel,
    log_audit
)


class StudentListView(FacultyRequiredMixin, ListView):
    model = Student
    template_name = 'students/student_list.html'
    context_object_name = 'students'
    paginate_by = 25

    def get_queryset(self):
        qs = Student.objects.select_related('user', 'department', 'course', 'current_semester', 'batch')
        archived = self.request.GET.get('archived', 'false') == 'true'
        qs = qs.filter(is_archived=archived)

        dept_id = self.request.GET.get('department')
        course_id = self.request.GET.get('course')
        sem_id = self.request.GET.get('semester')
        batch_id = self.request.GET.get('batch')
        q = self.request.GET.get('q', '').strip()

        if dept_id:
            qs = qs.filter(department_id=dept_id)
        if course_id:
            qs = qs.filter(course_id=course_id)
        if sem_id:
            qs = qs.filter(current_semester_id=sem_id)
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        if q:
            qs = qs.filter(
                Q(roll_number__icontains=q) |
                Q(registration_number__icontains=q) |
                Q(user__first_name__icontains=q) |
                Q(user__last_name__icontains=q) |
                Q(user__email__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['departments'] = Department.objects.all()
        ctx['courses'] = Course.objects.all()
        ctx['semesters'] = Semester.objects.all()
        ctx['batches'] = Batch.objects.all()
        ctx['selected_dept'] = self.request.GET.get('department', '')
        ctx['selected_course'] = self.request.GET.get('course', '')
        ctx['selected_sem'] = self.request.GET.get('semester', '')
        ctx['selected_batch'] = self.request.GET.get('batch', '')
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['is_archived_view'] = self.request.GET.get('archived', 'false') == 'true'
        return ctx


class StudentDetailView(FacultyRequiredMixin, DetailView):
    model = Student
    template_name = 'students/student_detail.html'
    context_object_name = 'student'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        student = self.object
        ctx['attendance_stats'] = student.get_attendance_stats()

        from attendance.models import AttendanceRecord
        ctx['recent_attendance'] = AttendanceRecord.objects.filter(student=student).select_related('session__subject', 'session__faculty').order_by('-session__date')[:10]

        from examinations.models import Marks
        ctx['marks_list'] = Marks.objects.filter(student=student).select_related('assessment_component__examination', 'assessment_component__subject')

        from assignments.models import Submission
        ctx['submissions_list'] = Submission.objects.filter(student=student).select_related('assignment__subject')

        return ctx


@login_required
@role_required('ADMIN')
def student_create_view(request):
    if request.method == 'POST':
        roll = request.POST.get('roll_number')
        reg = request.POST.get('registration_number')
        fname = request.POST.get('first_name')
        lname = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        dept_id = request.POST.get('department')
        course_id = request.POST.get('course')
        sem_id = request.POST.get('semester')
        batch_id = request.POST.get('batch')
        blood_group = request.POST.get('blood_group')
        gname = request.POST.get('guardian_name')
        gphone = request.POST.get('guardian_phone')

        username = roll.lower().replace(" ", "_")
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, f"User account with username '{username}' already exists.")
            return redirect('student_list')

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password="Student@123",
            first_name=fname,
            last_name=lname,
            phone=phone,
            role=CustomUser.ROLE_STUDENT
        )

        student = Student.objects.create(
            user=user,
            roll_number=roll,
            registration_number=reg,
            department_id=dept_id,
            course_id=course_id,
            current_semester_id=sem_id,
            batch_id=batch_id,
            blood_group=blood_group,
            guardian_name=gname,
            guardian_phone=gphone
        )

        log_audit(
            request=request,
            action="STUDENT_CREATED",
            entity_type="Student",
            entity_id=student.id,
            details=f"Student record created for {roll} ({fname} {lname}) by admin."
        )
        messages.success(request, f"Student {roll} created successfully. Default password is 'Student@123'.")
        return redirect('student_detail', pk=student.pk)

    context = {
        'departments': Department.objects.all(),
        'courses': Course.objects.all(),
        'semesters': Semester.objects.all(),
        'batches': Batch.objects.all(),
        'blood_groups': Student.BLOOD_GROUPS,
    }
    return render(request, 'students/student_form.html', context)


@login_required
@role_required('ADMIN')
def student_archive_view(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.is_archived = not student.is_archived
    student.save()

    status_str = "archived" if student.is_archived else "restored"
    log_audit(
        request=request,
        action="STUDENT_ARCHIVED_TOGGLE",
        entity_type="Student",
        entity_id=student.id,
        details=f"Student {student.roll_number} ({student.full_name}) was {status_str}."
    )
    messages.success(request, f"Student {student.roll_number} has been {status_str}.")
    return redirect('student_list')


@login_required
def student_id_card_pdf_view(request, pk):
    student = get_object_or_404(Student, pk=pk)
    # Check permissions: Admin, Faculty, or the student themselves
    if not (request.user.is_admin_role or request.user.is_faculty_role or (hasattr(request.user, 'student_profile') and request.user.student_profile == student)):
        messages.error(request, "Permission denied.")
        return redirect('dashboard_redirect')

    pdf_bytes = generate_student_id_card_pdf(student)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ID_Card_{student.roll_number}.pdf"'
    return response


@login_required
@role_required('ADMIN', 'FACULTY')
def export_students_excel_view(request):
    students = Student.objects.filter(is_archived=False).select_related('user', 'department', 'course', 'current_semester', 'batch')
    excel_bytes = export_students_to_excel(students)
    response = HttpResponse(excel_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Students_Directory.xlsx"'
    return response


@login_required
@role_required('ADMIN')
def import_students_excel_view(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        file_obj = request.FILES['excel_file']
        dept_id = request.POST.get('department')
        course_id = request.POST.get('course')
        sem_id = request.POST.get('semester')
        batch_id = request.POST.get('batch')

        try:
            dept = Department.objects.get(id=dept_id)
            course = Course.objects.get(id=course_id)
            sem = Semester.objects.get(id=sem_id)
            batch = Batch.objects.get(id=batch_id)

            created_count, errors = parse_and_import_students_excel(file_obj, dept, course, sem, batch)
            if created_count > 0:
                messages.success(request, f"Successfully imported {created_count} students!")
            if errors:
                for err in errors[:5]:
                    messages.warning(request, err)
        except Exception as e:
            messages.error(request, f"Failed to import: {str(e)}")

        return redirect('student_list')

    context = {
        'departments': Department.objects.all(),
        'courses': Course.objects.all(),
        'semesters': Semester.objects.all(),
        'batches': Batch.objects.all(),
    }
    return render(request, 'students/student_import.html', context)
