from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView
from .models import Department, Course, Semester, Subject, AcademicSession, SubjectAllocation
from faculty.models import Faculty
from students.models import Student
from attendance.models import AttendanceSession
from accounts.permissions import AdminRequiredMixin, role_required
from reports.utils import log_audit


class DepartmentListView(ListView):
    model = Department
    template_name = 'academics/department_list.html'
    context_object_name = 'departments'


class DepartmentDetailView(DetailView):
    model = Department
    template_name = 'academics/department_detail.html'
    context_object_name = 'department'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dept = self.object
        ctx['courses'] = dept.courses.all()
        ctx['faculty_members'] = dept.faculty_members.filter(is_active=True).select_related('user')
        ctx['students'] = dept.students.filter(is_archived=False).select_related('user', 'course', 'current_semester')[:25]
        ctx['subjects'] = Subject.objects.filter(semester__course__department=dept).select_related('semester__course')[:30]
        ctx['total_students_count'] = dept.students.filter(is_archived=False).count()
        return ctx


@login_required
@role_required('ADMIN')
def department_create_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code').upper()
        year = request.POST.get('established_year', 2000)
        desc = request.POST.get('description', '')

        if Department.objects.filter(code=code).exists():
            messages.error(request, f"Department code '{code}' already exists.")
            return render(request, 'academics/department_form.html')

        dept = Department.objects.create(name=name, code=code, established_year=year, description=desc)
        log_audit(request, "DEPARTMENT_CREATED", "Department", dept.id, f"Created {name} ({code})")
        messages.success(request, f"Department '{name}' created successfully.")
        return redirect('department_detail', pk=dept.pk)
    return render(request, 'academics/department_form.html')


@login_required
@role_required('ADMIN')
def department_edit_view(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        dept.name = request.POST.get('name', dept.name)
        new_code = request.POST.get('code', dept.code).upper()
        if Department.objects.filter(code=new_code).exclude(pk=pk).exists():
            messages.error(request, f"Department code '{new_code}' already exists.")
            return render(request, 'academics/department_form.html', {'department': dept, 'is_edit': True})
        dept.code = new_code
        dept.established_year = request.POST.get('established_year', dept.established_year)
        dept.description = request.POST.get('description', dept.description)
        dept.save()

        log_audit(request, "DEPARTMENT_EDITED", "Department", dept.id, f"Updated department {dept.name} ({dept.code})")
        messages.success(request, f"Department '{dept.name}' updated successfully.")
        return redirect('department_detail', pk=dept.pk)

    return render(request, 'academics/department_form.html', {'department': dept, 'is_edit': True})


@login_required
@role_required('ADMIN')
def department_delete_view(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        name = dept.name
        code = dept.code
        dept_id = dept.id
        dept.delete()
        log_audit(request, "DEPARTMENT_DELETED", "Department", dept_id, f"Deleted department {name} ({code})")
        messages.success(request, f"Department '{name}' ({code}) and its associated references deleted successfully.")
        return redirect('department_list')
    return render(request, 'academics/confirm_delete.html', {'object': dept, 'type': 'Department', 'cancel_url': 'department_detail'})


# ==========================================
# COURSE VIEWS
# ==========================================

class CourseListView(ListView):
    model = Course
    template_name = 'academics/course_list.html'
    context_object_name = 'courses'


class CourseDetailView(DetailView):
    model = Course
    template_name = 'academics/course_detail.html'
    context_object_name = 'course'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        course = self.object
        ctx['semesters'] = course.semesters.prefetch_related('subjects').all()
        ctx['batches'] = course.batches.all()
        ctx['students'] = course.students.filter(is_archived=False).select_related('user', 'current_semester', 'batch')[:30]
        ctx['total_students_count'] = course.students.filter(is_archived=False).count()
        return ctx


@login_required
@role_required('ADMIN')
def course_create_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code').upper()
        dept_id = request.POST.get('department')
        duration = request.POST.get('duration_years', 4)
        total_sems = request.POST.get('total_semesters', 8)

        if Course.objects.filter(code=code).exists():
            messages.error(request, f"Course code '{code}' already exists.")
            return render(request, 'academics/course_form.html', {'departments': Department.objects.all()})

        course = Course.objects.create(
            name=name, code=code, department_id=dept_id,
            duration_years=duration, total_semesters=total_sems
        )
        curr_session = AcademicSession.objects.filter(is_current=True).first()
        if curr_session:
            for s_num in range(1, int(total_sems) + 1):
                Semester.objects.get_or_create(course=course, semester_number=s_num, academic_session=curr_session)

        log_audit(request, "COURSE_CREATED", "Course", course.id, f"Created course {name} ({code})")
        messages.success(request, f"Course '{name}' and semesters created successfully.")
        return redirect('course_detail', pk=course.pk)

    preselected_dept = request.GET.get('department')
    context = {
        'departments': Department.objects.all(),
        'preselected_dept': int(preselected_dept) if preselected_dept else ''
    }
    return render(request, 'academics/course_form.html', context)


@login_required
@role_required('ADMIN')
def course_edit_view(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        course.name = request.POST.get('name', course.name)
        new_code = request.POST.get('code', course.code).upper()
        if Course.objects.filter(code=new_code).exclude(pk=pk).exists():
            messages.error(request, f"Course code '{new_code}' already exists.")
            return render(request, 'academics/course_form.html', {'course': course, 'departments': Department.objects.all(), 'is_edit': True})
        course.code = new_code
        course.department_id = request.POST.get('department', course.department_id)
        course.duration_years = request.POST.get('duration_years', course.duration_years)
        course.total_semesters = request.POST.get('total_semesters', course.total_semesters)
        course.save()

        log_audit(request, "COURSE_EDITED", "Course", course.id, f"Updated course {course.name} ({course.code})")
        messages.success(request, f"Course '{course.name}' updated successfully.")
        return redirect('course_detail', pk=course.pk)

    context = {
        'course': course,
        'departments': Department.objects.all(),
        'is_edit': True
    }
    return render(request, 'academics/course_form.html', context)


@login_required
@role_required('ADMIN')
def course_delete_view(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        name = course.name
        code = course.code
        course_id = course.id
        course.delete()
        log_audit(request, "COURSE_DELETED", "Course", course_id, f"Deleted course {name} ({code})")
        messages.success(request, f"Course '{name}' ({code}) deleted successfully.")
        return redirect('course_list')
    return render(request, 'academics/confirm_delete.html', {'object': course, 'type': 'Course', 'cancel_url': 'course_detail'})


# ==========================================
# SUBJECT VIEWS
# ==========================================

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


class SubjectDetailView(DetailView):
    model = Subject
    template_name = 'academics/subject_detail.html'
    context_object_name = 'subject'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        subj = self.object
        ctx['allocations'] = subj.allocations.filter(is_active=True).select_related('faculty__user')
        ctx['attendance_sessions'] = subj.attendance_sessions.select_related('faculty__user', 'batch')[:15]
        ctx['enrolled_students'] = Student.objects.filter(current_semester=subj.semester, is_archived=False).select_related('user', 'batch')[:30]
        ctx['enrolled_count'] = Student.objects.filter(current_semester=subj.semester, is_archived=False).count()
        return ctx


@login_required
@role_required('ADMIN')
def subject_create_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code').upper()
        sem_id = request.POST.get('semester')
        credits = request.POST.get('credits', 4)
        subj_type = request.POST.get('subject_type', 'THEORY')
        fac_id = request.POST.get('faculty')

        if Subject.objects.filter(code=code).exists():
            messages.error(request, f"Subject code '{code}' already exists.")
            return render(request, 'academics/subject_form.html', {
                'semesters': Semester.objects.select_related('course', 'academic_session').all(),
                'faculty_members': Faculty.objects.filter(is_active=True).select_related('user', 'department'),
                'subject_types': Subject.TYPE_CHOICES,
            })

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
        messages.success(request, f"Subject '{name}' created successfully.")
        return redirect('subject_detail', pk=subj.pk)

    context = {
        'semesters': Semester.objects.select_related('course', 'academic_session').all(),
        'faculty_members': Faculty.objects.filter(is_active=True).select_related('user', 'department'),
        'subject_types': Subject.TYPE_CHOICES,
    }
    return render(request, 'academics/subject_form.html', context)


@login_required
@role_required('ADMIN')
def subject_edit_view(request, pk):
    subj = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        subj.name = request.POST.get('name', subj.name)
        new_code = request.POST.get('code', subj.code).upper()
        if Subject.objects.filter(code=new_code).exclude(pk=pk).exists():
            messages.error(request, f"Subject code '{new_code}' already exists.")
            return render(request, 'academics/subject_form.html', {
                'subject': subj,
                'semesters': Semester.objects.select_related('course').all(),
                'faculty_members': Faculty.objects.filter(is_active=True).select_related('user'),
                'subject_types': Subject.TYPE_CHOICES,
                'is_edit': True
            })
        subj.code = new_code
        subj.semester_id = request.POST.get('semester', subj.semester_id)
        subj.credits = request.POST.get('credits', subj.credits)
        subj.subject_type = request.POST.get('subject_type', subj.subject_type)
        subj.save()

        fac_id = request.POST.get('faculty')
        if fac_id:
            curr_session = subj.semester.academic_session
            SubjectAllocation.objects.filter(subject=subj).update(is_active=False)
            alloc, created = SubjectAllocation.objects.get_or_create(
                subject=subj, faculty_id=fac_id, academic_session=curr_session
            )
            alloc.is_active = True
            alloc.save()

        log_audit(request, "SUBJECT_EDITED", "Subject", subj.id, f"Updated subject {subj.name} ({subj.code})")
        messages.success(request, f"Subject '{subj.name}' updated successfully.")
        return redirect('subject_detail', pk=subj.pk)

    curr_alloc = subj.allocations.filter(is_active=True).first()
    context = {
        'subject': subj,
        'semesters': Semester.objects.select_related('course').all(),
        'faculty_members': Faculty.objects.filter(is_active=True).select_related('user'),
        'subject_types': Subject.TYPE_CHOICES,
        'current_faculty_id': curr_alloc.faculty_id if curr_alloc else '',
        'is_edit': True
    }
    return render(request, 'academics/subject_form.html', context)


@login_required
@role_required('ADMIN')
def subject_delete_view(request, pk):
    subj = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        name = subj.name
        code = subj.code
        subj_id = subj.id
        subj.delete()
        log_audit(request, "SUBJECT_DELETED", "Subject", subj_id, f"Deleted subject {name} ({code})")
        messages.success(request, f"Subject '{name}' ({code}) deleted successfully.")
        return redirect('subject_list')
    return render(request, 'academics/confirm_delete.html', {'object': subj, 'type': 'Subject', 'cancel_url': 'subject_detail'})
