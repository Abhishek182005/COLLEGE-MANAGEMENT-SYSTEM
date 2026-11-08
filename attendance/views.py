import json
from decimal import Decimal
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView, View
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Q
from .models import AttendanceSession, AttendanceRecord
from academics.models import Subject, Semester, SubjectAllocation, Department
from students.models import Student, Batch
from faculty.models import Faculty
from accounts.permissions import FacultyRequiredMixin, StudentRequiredMixin, role_required
from reports.utils import export_attendance_to_excel, log_audit


class AttendanceSessionListView(FacultyRequiredMixin, ListView):
    model = AttendanceSession
    template_name = 'attendance/session_list.html'
    context_object_name = 'sessions'
    paginate_by = 20

    def get_queryset(self):
        qs = AttendanceSession.objects.select_related('subject', 'faculty', 'semester', 'batch')
        if self.request.user.is_faculty_role:
            faculty = getattr(self.request.user, 'faculty_profile', None)
            if faculty:
                qs = qs.filter(faculty=faculty)

        date_val = self.request.GET.get('date')
        subj_id = self.request.GET.get('subject')
        if date_val:
            qs = qs.filter(date=date_val)
        if subj_id:
            qs = qs.filter(subject_id=subj_id)
        return qs.order_by('-date', '-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.is_faculty_role and hasattr(self.request.user, 'faculty_profile'):
            ctx['my_subjects'] = Subject.objects.filter(allocations__faculty=self.request.user.faculty_profile)
        else:
            ctx['my_subjects'] = Subject.objects.all()
        ctx['selected_date'] = self.request.GET.get('date', '')
        ctx['selected_subject'] = self.request.GET.get('subject', '')
        return ctx


class AttendanceSessionDetailView(FacultyRequiredMixin, DetailView):
    model = AttendanceSession
    template_name = 'attendance/session_detail.html'
    context_object_name = 'session'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['records'] = self.object.records.select_related('student__user').order_by('student__roll_number')
        return ctx


@login_required
@role_required('FACULTY', 'ADMIN')
def quick_mark_attendance_view(request):
    """
    SmartProf Quick Attendance Marking Interface:
    Displays enrolled students in a single screen for rapid marking with Present/Absent/Late toggles.
    """
    faculty = getattr(request.user, 'faculty_profile', None)
    if not faculty and not request.user.is_admin_role:
        messages.error(request, "Faculty profile required.")
        return redirect('dashboard_redirect')

    selected_subject_id = request.GET.get('subject_id')
    selected_batch_id = request.GET.get('batch_id')
    selected_date = request.GET.get('date', timezone.now().date().isoformat())
    selected_slot = request.GET.get('lecture_slot', '09:00 - 10:00')
    existing_session_id = request.GET.get('session_id')

    existing_session = None
    if existing_session_id:
        existing_session = get_object_or_404(AttendanceSession, id=existing_session_id)
        selected_subject_id = existing_session.subject_id
        selected_batch_id = existing_session.batch_id
        selected_date = existing_session.date.isoformat()
        selected_slot = existing_session.lecture_slot

    students_list = []
    subject = None
    if selected_subject_id:
        subject = get_object_or_404(Subject, id=selected_subject_id)
        students_qs = Student.objects.filter(current_semester=subject.semester, is_archived=False).select_related('user', 'batch')
        if selected_batch_id:
            students_qs = students_qs.filter(batch_id=selected_batch_id)

        # Existing record mapping if any
        status_map = {}
        remarks_map = {}
        if existing_session:
            for rec in existing_session.records.all():
                status_map[rec.student_id] = rec.status
                remarks_map[rec.student_id] = rec.remarks or ''

        for s in students_qs:
            students_list.append({
                'student': s,
                'status': status_map.get(s.id, 'PRESENT'),  # default to PRESENT
                'remarks': remarks_map.get(s.id, '')
            })

    if request.method == 'POST':
        subj_id = request.POST.get('subject_id')
        sem_id = request.POST.get('semester_id')
        batch_id = request.POST.get('batch_id')
        date_str = request.POST.get('date')
        slot_str = request.POST.get('lecture_slot')
        topic = request.POST.get('topic_covered', '')
        amendment_reason = request.POST.get('amendment_reason', '')

        # Fallback faculty if admin
        effective_faculty = faculty
        if not effective_faculty and request.user.is_admin_role:
            subj = Subject.objects.get(id=subj_id)
            alloc = subj.allocations.first()
            effective_faculty = alloc.faculty if alloc else Faculty.objects.first()

        session, created = AttendanceSession.objects.get_or_create(
            subject_id=subj_id,
            faculty=effective_faculty,
            semester_id=sem_id,
            batch_id=batch_id if batch_id else None,
            date=date_str,
            lecture_slot=slot_str,
            defaults={'topic_covered': topic}
        )
        if not created and topic:
            session.topic_covered = topic
            session.save()

        # Update records
        changes = []
        for key, val in request.POST.items():
            if key.startswith('status_'):
                student_id = key.replace('status_', '')
                remarks = request.POST.get(f'remarks_{student_id}', '')
                rec, r_created = AttendanceRecord.objects.get_or_create(
                    session=session,
                    student_id=student_id,
                    defaults={'status': val, 'remarks': remarks, 'marked_via': 'MANUAL'}
                )
                if not r_created and (rec.status != val or rec.remarks != remarks):
                    changes.append(f"Student #{student_id}: {rec.status} -> {val}")
                    rec.status = val
                    rec.remarks = remarks
                    rec.save()

        # Audit log if backdated or modified
        if changes or not created:
            log_audit(
                request=request,
                action="ATTENDANCE_MODIFIED",
                entity_type="AttendanceSession",
                entity_id=session.id,
                details=f"Attendance modified for {session.subject.code} ({session.date}). Reason: {amendment_reason or 'Direct faculty entry'}. Changes: {', '.join(changes) or 'Initial bulk save'}"
            )

        messages.success(request, f"Attendance recorded successfully! Overall Attendance: {session.attendance_percentage}%")
        return redirect('attendance_session_detail', pk=session.pk)

    # Faculty subjects
    if faculty:
        my_subjects = Subject.objects.filter(allocations__faculty=faculty, allocations__is_active=True).select_related('semester')
    else:
        my_subjects = Subject.objects.all().select_related('semester')

    context = {
        'my_subjects': my_subjects,
        'batches': Batch.objects.all(),
        'slots': AttendanceSession.SLOT_CHOICES,
        'selected_subject_id': int(selected_subject_id) if selected_subject_id else '',
        'selected_batch_id': int(selected_batch_id) if selected_batch_id else '',
        'selected_date': selected_date,
        'selected_slot': selected_slot,
        'subject': subject,
        'students_list': students_list,
        'existing_session': existing_session,
        'is_backdated': existing_session is not None or selected_date != timezone.now().date().isoformat(),
    }
    return render(request, 'attendance/quick_mark.html', context)


@login_required
@role_required('STUDENT')
def student_qr_attendance_view(request):
    """
    Student interface to mark attendance via QR code scan (camera) or manual dynamic token input.
    """
    student = getattr(request.user, 'student_profile', None)
    if not student:
        messages.error(request, "Student profile required.")
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        token = request.POST.get('qr_token', '').strip()
        if token.startswith("CAMPUSCONNECT_ATTENDANCE:"):
            token = token.replace("CAMPUSCONNECT_ATTENDANCE:", "")

        try:
            session = AttendanceSession.objects.get(qr_token=token)
            if not session.is_qr_valid():
                messages.error(request, "This QR code has expired. Please ask faculty for an updated code.")
            elif session.is_locked:
                messages.error(request, "This session is finalized and locked.")
            elif student.current_semester != session.semester:
                messages.error(request, "You are not enrolled in the semester for this subject.")
            elif session.batch and student.batch != session.batch:
                messages.error(request, "This lecture is restricted to a different batch section.")
            else:
                record, _ = AttendanceRecord.objects.get_or_create(
                    session=session,
                    student=student,
                    defaults={'status': 'PRESENT', 'marked_via': 'QR_CODE'}
                )
                if record.status != 'PRESENT':
                    record.status = 'PRESENT'
                    record.marked_via = 'QR_CODE'
                    record.save()
                messages.success(request, f"Attendance successfully verified for {session.subject.name} ({session.subject.code})!")
                return redirect('student_dashboard')
        except AttendanceSession.DoesNotExist:
            messages.error(request, "Invalid QR code token. Please try again.")

    return render(request, 'attendance/student_qr_scanner.html')


@login_required
@role_required('ADMIN', 'FACULTY')
def attendance_shortage_report_view(request):
    """List students below 75% threshold across departments."""
    threshold = getattr(settings, 'ATTENDANCE_SHORTAGE_THRESHOLD', 75.0)
    dept_id = request.GET.get('department')

    students = Student.objects.filter(is_archived=False).select_related('user', 'department', 'course', 'current_semester', 'batch')
    if dept_id:
        students = students.filter(department_id=dept_id)

    shortage_list = []
    for s in students:
        stats = s.get_attendance_stats()
        if stats['shortage'] and stats['total'] > 0:
            shortage_list.append({
                'student': s,
                'total': stats['total'],
                'present': stats['present'],
                'absent': stats['absent'],
                'percentage': stats['percentage'],
            })

    context = {
        'shortage_list': shortage_list,
        'threshold': threshold,
        'departments': Department.objects.all(),
        'selected_dept': dept_id or '',
    }
    return render(request, 'attendance/shortage_report.html', context)


@login_required
@role_required('ADMIN', 'FACULTY')
def export_attendance_excel_view(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id)
    excel_bytes = export_attendance_to_excel(session)
    response = HttpResponse(excel_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Attendance_{session.subject.code}_{session.date}.xlsx"'
    return response
