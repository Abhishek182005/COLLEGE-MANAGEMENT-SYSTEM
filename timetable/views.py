from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import TemplateView
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Timetable, Classroom
from academics.models import Subject, Semester, Course, Department
from faculty.models import Faculty
from students.models import Batch, Student
from accounts.permissions import role_required, AdminRequiredMixin
from reports.utils import log_audit


class TimetableMasterView(TemplateView):
    template_name = 'timetable/timetable_master.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sem_id = self.request.GET.get('semester')
        batch_id = self.request.GET.get('batch')
        fac_id = self.request.GET.get('faculty')

        qs = Timetable.objects.select_related('subject', 'faculty__user', 'classroom', 'semester', 'batch')

        if sem_id:
            qs = qs.filter(semester_id=sem_id)
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        if fac_id:
            qs = qs.filter(faculty_id=fac_id)

        # Build grid data: days x slots
        days = Timetable.DAYS_OF_WEEK  # [(0, 'Monday'), ...]
        slots = [s[0] for s in Timetable.SLOT_CHOICES]

        # schedule_grid: {day: {slot: [entries]}}
        grid = {day_num: {s: [] for s in slots} for day_num, _ in days}
        for entry in qs:
            if entry.day_of_week in grid and entry.time_slot in grid[entry.day_of_week]:
                grid[entry.day_of_week][entry.time_slot].append(entry)

        ctx['days'] = days
        ctx['slots'] = slots
        ctx['grid'] = grid
        ctx['semesters'] = Semester.objects.select_related('course').all()
        ctx['batches'] = Batch.objects.all()
        ctx['faculty_list'] = Faculty.objects.filter(is_active=True).select_related('user')
        ctx['selected_sem'] = int(sem_id) if sem_id else ''
        ctx['selected_batch'] = int(batch_id) if batch_id else ''
        ctx['selected_faculty'] = int(fac_id) if fac_id else ''
        return ctx


@login_required
def my_timetable_view(request):
    """Shows personalized schedule for logged-in faculty or student."""
    user = request.user
    days = Timetable.DAYS_OF_WEEK
    slots = [s[0] for s in Timetable.SLOT_CHOICES]
    grid = {day_num: {s: [] for s in slots} for day_num, _ in days}

    title = "My Academic Timetable"

    if user.is_faculty_role and hasattr(user, 'faculty_profile'):
        fac = user.faculty_profile
        title = f"Teaching Timetable - {fac.full_name}"
        entries = Timetable.objects.filter(faculty=fac).select_related('subject', 'classroom', 'semester', 'batch')
    elif user.is_student_role and hasattr(user, 'student_profile'):
        student = user.student_profile
        title = f"Class Timetable - {student.course.code} Sem {student.current_semester.semester_number}"
        entries = Timetable.objects.filter(
            semester=student.current_semester
        ).filter(Q(batch=student.batch) | Q(batch__isnull=True)).select_related('subject', 'faculty', 'classroom')
    else:
        entries = Timetable.objects.all().select_related('subject', 'faculty', 'classroom')[:30]

    for entry in entries:
        if entry.day_of_week in grid and entry.time_slot in grid[entry.day_of_week]:
            grid[entry.day_of_week][entry.time_slot].append(entry)

    context = {
        'days': days,
        'slots': slots,
        'grid': grid,
        'page_title': title,
    }
    return render(request, 'timetable/my_timetable.html', context)


@login_required
@role_required('ADMIN')
def timetable_create_view(request):
    if request.method == 'POST':
        day = request.POST.get('day_of_week')
        slot = request.POST.get('time_slot')
        class_type = request.POST.get('class_type', 'TE')
        subj_id = request.POST.get('subject')
        fac_id = request.POST.get('faculty')
        room_id = request.POST.get('classroom')
        sem_id = request.POST.get('semester')
        batch_id = request.POST.get('batch')

        entry = Timetable(
            day_of_week=int(day),
            time_slot=slot,
            class_type=class_type,
            subject_id=subj_id,
            faculty_id=fac_id,
            classroom_id=room_id,
            semester_id=sem_id,
            batch_id=batch_id if batch_id else None
        )

        try:
            entry.save()
            log_audit(
                request=request,
                action="TIMETABLE_CREATED",
                entity_type="Timetable",
                entity_id=entry.id,
                details=f"Scheduled {entry.subject.code} on {entry.get_day_of_week_display()} at {entry.time_slot}."
            )
            messages.success(request, "Timetable entry scheduled without conflicts.")
            return redirect('timetable_master')
        except ValidationError as e:
            messages.error(request, str(e.messages[0] if hasattr(e, 'messages') else e))

    context = {
        'days': Timetable.DAYS_OF_WEEK,
        'slots': Timetable.SLOT_CHOICES,
        'subjects': Subject.objects.all(),
        'faculty_members': Faculty.objects.filter(is_active=True).select_related('user'),
        'classrooms': Classroom.objects.all(),
        'semesters': Semester.objects.select_related('course').all(),
        'batches': Batch.objects.all(),
    }
    return render(request, 'timetable/timetable_form.html', context)

@login_required
@role_required('ADMIN')
def timetable_delete_view(request, pk):
    entry = get_object_or_404(Timetable, pk=pk)
    if request.method == 'POST':
        subj_code = entry.subject.code
        slot = entry.time_slot
        day = entry.get_day_of_week_display()
        entry_id = entry.id
        entry.delete()
        log_audit(
            request=request,
            action="TIMETABLE_DELETED",
            entity_type="Timetable",
            entity_id=entry_id,
            details=f"Removed timetable schedule: {subj_code} on {day} ({slot})."
        )
        messages.success(request, f"Schedule for {subj_code} ({day} {slot}) removed successfully.")
        return redirect('timetable_master')

    return render(request, 'academics/confirm_delete.html', {'object': entry, 'type': 'Timetable Class Slot', 'cancel_url': 'timetable_master'})
