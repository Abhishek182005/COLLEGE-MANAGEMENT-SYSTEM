from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView
from .models import Department, Course, Semester, Subject, AcademicSession, SubjectAllocation
from faculty.models import Faculty
from accounts.permissions import AdminRequiredMixin, role_required
from reports.utils import log_audit


class DepartmentListView(ListView):
    model = Department
    template_name = 'academics/department_list.html'
    context_object_name = 'departments'


@login_required
@role_required('ADMIN')
def department_create_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        year = request.POST.get('established_year', 2000)
        desc = request.POST.get('description', '')

        dept = Department.objects.create(name=name, code=code, established_year=year, description=desc)
        log_audit(request, "DEPARTMENT_CREATED", "Department", dept.id, f"Created {name} ({code})")
        messages.success(request, f"Department '{name}' created successfully.")
        return redirect('department_list')
    return render(request, 'academics/department_form.html')


class CourseListView(ListView):
    model = Course
    template_name = 'academics/course_list.html'
    context_object_name = 'courses'


@login_required
@role_required('ADMIN')
def course_create_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        dept_id = request.POST.get('department')
        duration = request.POST.get('duration_years', 4)
        total_sems = request.POST.get('total_semesters', 8)

        course = Course.objects.create(
            name=name, code=code, department_id=dept_id,
            duration_years=duration, total_semesters=total_sems
        )
        # Automatically generate semesters for current academic session
        curr_session = AcademicSession.objects.filter(is_current=True).first()
        if curr_session:
            for s_num in range(1, int(total_sems) + 1):
                Semester.objects.get_or_create(course=course, semester_number=s_num, academic_session=curr_session)

        log_audit(request, "COURSE_CREATED", "Course", course.id, f"Created course {name} ({code})")
        messages.success(request, f"Course '{name}' and semesters generated successfully.")
        return redirect('course_list')

    context = {'departments': Department.objects.all()}
    return render(request, 'academics/course_form.html', context)


class SubjectListView(ListView):
    model = Subject
    template_name = 'academics/subject_list.html'
    context_object_name = 'subjects'
    paginate_by = 25

    def get_queryset(self):
        qs = Subject.objects.select_related('semester__course', 'semester__academic_session')
        dept_id = self.request.GET.get('department')
        if dept_id:
            qs = qs.filter(semester__course__department_id=dept_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['departments'] = Department.objects.all()
        ctx['selected_dept'] = self.request.GET.get('department', '')
        return ctx


@login_required
@role_required('ADMIN')
def subject_create_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        sem_id = request.POST.get('semester')
        credits = request.POST.get('credits', 4)
        subj_type = request.POST.get('subject_type', 'THEORY')
        fac_id = request.POST.get('faculty')

        subj = Subject.objects.create(
            name=name, code=code, semester_id=sem_id,
            credits=credits, subject_type=subj_type
        )
        if fac_id:
            curr_session = subj.semester.academic_session
            SubjectAllocation.objects.get_or_create(
                subject=subj, faculty_id=fac_id, academic_session=curr_session
            )

        log_audit(request, "SUBJECT_CREATED", "Subject", subj.id, f"Created subject {name} ({code})")
        messages.success(request, f"Subject '{name}' created and allocated successfully.")
        return redirect('subject_list')

    context = {
        'semesters': Semester.objects.select_related('course', 'academic_session').all(),
        'faculty_members': Faculty.objects.filter(is_active=True).select_related('user', 'department'),
        'subject_types': Subject.TYPE_CHOICES,
    }
    return render(request, 'academics/subject_form.html', context)
