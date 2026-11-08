from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.http import HttpResponse
from django.db.models import Q
from .models import Faculty
from accounts.models import CustomUser
from academics.models import Department, SubjectAllocation
from timetable.models import Timetable
from accounts.permissions import AdminRequiredMixin, FacultyRequiredMixin, role_required
from reports.utils import log_audit


class FacultyListView(ListView):
    model = Faculty
    template_name = 'faculty/faculty_list.html'
    context_object_name = 'faculty_list'
    paginate_by = 25

    def get_queryset(self):
        qs = Faculty.objects.select_related('user', 'department')
        dept_id = self.request.GET.get('department')
        q = self.request.GET.get('q', '').strip()

        if dept_id:
            qs = qs.filter(department_id=dept_id)
        if q:
            qs = qs.filter(
                Q(employee_id__icontains=q) |
                Q(user__first_name__icontains=q) |
                Q(user__last_name__icontains=q) |
                Q(user__email__icontains=q) |
                Q(designation__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['departments'] = Department.objects.all()
        ctx['selected_dept'] = self.request.GET.get('department', '')
        ctx['search_query'] = self.request.GET.get('q', '')
        return ctx


class FacultyDetailView(DetailView):
    model = Faculty
    template_name = 'faculty/faculty_detail.html'
    context_object_name = 'faculty'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fac = self.object
        ctx['allocations'] = fac.allocated_subjects.filter(is_active=True).select_related('subject', 'academic_session')
        ctx['weekly_classes'] = Timetable.objects.filter(faculty=fac).select_related('subject', 'classroom', 'semester').order_by('day_of_week', 'time_slot')
        ctx['workload_hours'] = ctx['weekly_classes'].count()
        return ctx


@login_required
@role_required('ADMIN')
def faculty_create_view(request):
    if request.method == 'POST':
        emp_id = request.POST.get('employee_id')
        fname = request.POST.get('first_name')
        lname = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        dept_id = request.POST.get('department')
        designation = request.POST.get('designation')
        qualification = request.POST.get('qualification')
        cabin = request.POST.get('cabin_number')
        emergency = request.POST.get('emergency_contact')

        username = emp_id.lower().replace("-", "_")
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, f"User account with username '{username}' already exists.")
            return redirect('faculty_list')

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password="Faculty@123",
            first_name=fname,
            last_name=lname,
            phone=phone,
            role=CustomUser.ROLE_FACULTY,
            is_staff=True
        )

        faculty = Faculty.objects.create(
            user=user,
            employee_id=emp_id,
            department_id=dept_id,
            designation=designation,
            qualification=qualification,
            cabin_number=cabin,
            emergency_contact=emergency
        )

        log_audit(
            request=request,
            action="FACULTY_CREATED",
            entity_type="Faculty",
            entity_id=faculty.id,
            details=f"Faculty {emp_id} ({fname} {lname}) created by admin."
        )
        messages.success(request, f"Faculty {fname} {lname} created successfully. Default password is 'Faculty@123'.")
        return redirect('faculty_detail', pk=faculty.pk)

    context = {
        'departments': Department.objects.all(),
        'designations': Faculty.DESIGNATION_CHOICES,
    }
    return render(request, 'faculty/faculty_form.html', context)

@login_required
@role_required('ADMIN')
def faculty_edit_view(request, pk):
    faculty = get_object_or_404(Faculty, pk=pk)
    user = faculty.user
    if request.method == 'POST':
        fname = request.POST.get('first_name')
        lname = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        dept_id = request.POST.get('department')
        designation = request.POST.get('designation')
        qualification = request.POST.get('qualification')
        cabin = request.POST.get('cabin_number')
        emergency = request.POST.get('emergency_contact')

        user.first_name = fname
        user.last_name = lname
        user.email = email
        user.phone = phone
        user.save()

        faculty.department_id = dept_id
        faculty.designation = designation
        faculty.qualification = qualification
        faculty.cabin_number = cabin
        faculty.emergency_contact = emergency
        faculty.save()

        log_audit(
            request=request,
            action="FACULTY_UPDATED",
            entity_type="Faculty",
            entity_id=faculty.id,
            details=f"Faculty details updated for {faculty.employee_id} ({fname} {lname}) by admin."
        )
        messages.success(request, f"Faculty {fname} {lname} updated successfully.")
        return redirect('faculty_detail', pk=faculty.pk)

    context = {
        'faculty': faculty,
        'departments': Department.objects.all(),
        'designations': Faculty.DESIGNATION_CHOICES,
        'is_edit': True,
    }
    return render(request, 'faculty/faculty_form.html', context)


@login_required
@role_required('ADMIN')
def faculty_delete_view(request, pk):
    faculty = get_object_or_404(Faculty, pk=pk)
    if request.method == 'POST':
        emp_id = faculty.employee_id
        name = faculty.full_name
        fac_id = faculty.id
        user = faculty.user
        faculty.delete()
        if user:
            user.delete()
        log_audit(
            request=request,
            action="FACULTY_DELETED",
            entity_type="Faculty",
            entity_id=fac_id,
            details=f"Permanently deleted faculty member {emp_id} ({name}) and user account."
        )
        messages.success(request, f"Faculty {name} ({emp_id}) deleted successfully.")
        return redirect('faculty_list')

    return render(request, 'academics/confirm_delete.html', {'object': faculty, 'type': 'Faculty Member', 'cancel_url': 'faculty_detail'})
