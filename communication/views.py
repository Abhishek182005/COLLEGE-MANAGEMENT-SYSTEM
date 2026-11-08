from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Notice, NoticeRead
from academics.models import Department, Semester
from students.models import Batch
from accounts.permissions import role_required
from reports.utils import log_audit


class NoticeListView(ListView):
    model = Notice
    template_name = 'communication/notice_list.html'
    context_object_name = 'notices'
    paginate_by = 15

    def get_queryset(self):
        user = self.request.user
        qs = Notice.objects.select_related('published_by', 'department', 'semester', 'batch')

        if user.is_student_role and hasattr(user, 'student_profile'):
            student = user.student_profile
            qs = qs.filter(
                Q(audience_type='ALL') |
                Q(audience_type='STUDENTS_ONLY') |
                Q(audience_type='DEPARTMENT', department=student.department) |
                Q(audience_type='SEMESTER', semester=student.current_semester) |
                Q(audience_type='BATCH', batch=student.batch)
            )
        elif user.is_faculty_role and hasattr(user, 'faculty_profile'):
            faculty = user.faculty_profile
            qs = qs.filter(
                Q(audience_type='ALL') |
                Q(audience_type='FACULTY_ONLY') |
                Q(audience_type='DEPARTMENT', department=faculty.department)
            )

        priority = self.request.GET.get('priority')
        if priority:
            qs = qs.filter(priority=priority)

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            ctx['read_notice_ids'] = set(NoticeRead.objects.filter(user=self.request.user).values_list('notice_id', flat=True))
        ctx['selected_priority'] = self.request.GET.get('priority', '')
        return ctx


class NoticeDetailView(DetailView):
    model = Notice
    template_name = 'communication/notice_detail.html'
    context_object_name = 'notice'

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        if request.user.is_authenticated:
            NoticeRead.objects.get_or_create(notice=self.object, user=request.user)
        return response


@login_required
@role_required('ADMIN', 'FACULTY')
def notice_create_view(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        audience = request.POST.get('audience_type', 'ALL')
        dept_id = request.POST.get('department')
        sem_id = request.POST.get('semester')
        batch_id = request.POST.get('batch')
        priority = request.POST.get('priority', 'NORMAL')
        expiry = request.POST.get('expiry_date')
        attachment = request.FILES.get('attachment')

        notice = Notice.objects.create(
            title=title,
            content=content,
            published_by=request.user,
            audience_type=audience,
            department_id=dept_id if dept_id else None,
            semester_id=sem_id if sem_id else None,
            batch_id=batch_id if batch_id else None,
            priority=priority,
            expiry_date=expiry if expiry else None,
            attachment=attachment
        )
        log_audit(request, "NOTICE_PUBLISHED", "Notice", notice.id, f"Published [{priority}] notice '{title}'.")
        messages.success(request, f"Notice '{title}' published successfully.")
        return redirect('notice_detail', pk=notice.pk)

    context = {
        'departments': Department.objects.all(),
        'semesters': Semester.objects.select_related('course').all(),
        'batches': Batch.objects.all(),
        'priorities': Notice.PRIORITY_CHOICES,
        'audience_choices': Notice.AUDIENCE_CHOICES,
    }
    return render(request, 'communication/notice_form.html', context)

@login_required
@role_required('ADMIN', 'FACULTY')
def notice_delete_view(request, pk):
    notice = get_object_or_404(Notice, pk=pk)
    if request.method == 'POST':
        title = notice.title
        n_id = notice.id
        notice.delete()
        log_audit(request, "NOTICE_DELETED", "Notice", n_id, f"Deleted notice '{title}'.")
        messages.success(request, f"Notice '{title}' deleted successfully.")
        return redirect('notice_list')
    return render(request, 'academics/confirm_delete.html', {'object': notice, 'type': 'Campus Notice', 'cancel_url': 'notice_detail'})
