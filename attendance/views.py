import json
from datetime import datetime, date
from decimal import Decimal
from collections import OrderedDict
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
from timetable.models import Timetable
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
    Displays enrolled students for rapid marking with Present/Absent/Late/Excused toggles and Benefits.
    Fixes:
    - Automatically detects if session on this date & slot is already recorded.
    - Demarcation of lecture type (Theory / Practical / Tutorial).
    - Prevents accidental duplicate session submissions.
    """
    faculty = getattr(request.user, 'faculty_profile', None)
    if not faculty and not request.user.is_admin_role:
        messages.error(request, "Faculty profile required.")
        return redirect('dashboard_redirect')

    selected_subject_id = request.GET.get('subject_id')
    selected_batch_id = request.GET.get('batch_id')
    selected_date = request.GET.get('date', timezone.now().date().isoformat())
    selected_slot = request.GET.get('lecture_slot', '09:00 - 10:00')
    selected_session_type = request.GET.get('session_type', '')
    existing_session_id = request.GET.get('session_id')

    existing_session = None
    if existing_session_id:
        existing_session = get_object_or_404(AttendanceSession, id=existing_session_id)
        selected_subject_id = existing_session.subject_id
        selected_batch_id = existing_session.batch_id
        selected_date = existing_session.date.isoformat()
        selected_slot = existing_session.lecture_slot
        selected_session_type = existing_session.session_type
    elif selected_subject_id:
        # Check if attendance has already been recorded for this date, subject, and slot
        existing_session_query = AttendanceSession.objects.filter(
            subject_id=selected_subject_id,
            date=selected_date,
            lecture_slot=selected_slot,
        )
        if selected_batch_id:
            existing_session_query = existing_session_query.filter(batch_id=selected_batch_id)
        if faculty:
            existing_session_query = existing_session_query.filter(faculty=faculty)

        existing_session = existing_session_query.first()

        if existing_session:
            if not selected_session_type:
                selected_session_type = existing_session.session_type
            if not selected_batch_id and existing_session.batch_id:
                selected_batch_id = existing_session.batch_id

    students_list = []
    subject = None
    is_scheduled_on_date = True

    if selected_subject_id:
        subject = get_object_or_404(Subject, id=selected_subject_id)
        if not selected_session_type:
            selected_session_type = subject.paper_type_code

        # Schedule check for this date
        try:
            d_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            dow = d_obj.weekday()
            tt_qs = Timetable.objects.filter(day_of_week=dow, subject=subject, time_slot=selected_slot)
            if faculty:
                tt_qs = tt_qs.filter(faculty=faculty)
            is_scheduled_on_date = tt_qs.exists()
        except Exception:
            is_scheduled_on_date = True

        students_qs = Student.objects.filter(current_semester=subject.semester, is_archived=False).select_related('user', 'batch')
        if selected_batch_id:
            students_qs = students_qs.filter(batch_id=selected_batch_id)

        # Existing record mapping if any
        status_map = {}
        benefit_map = {}
        remarks_map = {}
        if existing_session:
            for rec in existing_session.records.all():
                status_map[rec.student_id] = rec.status
                benefit_map[rec.student_id] = rec.benefit_type
                remarks_map[rec.student_id] = rec.remarks or ''

        for s in students_qs:
            students_list.append({
                'student': s,
                'status': status_map.get(s.id, 'PRESENT'),
                'benefit_type': benefit_map.get(s.id, 'NONE'),
                'remarks': remarks_map.get(s.id, '')
            })

    if request.method == 'POST':
        subj_id = request.POST.get('subject_id')
        sem_id = request.POST.get('semester_id')
        batch_id = request.POST.get('batch_id')
        date_str = request.POST.get('date')
        slot_str = request.POST.get('lecture_slot')
        session_type = request.POST.get('session_type', 'TE')
        topic = request.POST.get('topic_covered', '')
        amendment_reason = request.POST.get('amendment_reason', '')

        # Fallback faculty if admin
        effective_faculty = faculty
        if not effective_faculty and request.user.is_admin_role:
            subj = Subject.objects.get(id=subj_id)
            alloc = subj.allocations.first()
            effective_faculty = alloc.faculty if alloc else Faculty.objects.first()

        if existing_session:
            session = existing_session
            session.session_type = session_type
            if topic:
                session.topic_covered = topic
            session.save()
            created = False
        else:
            session, created = AttendanceSession.objects.get_or_create(
                subject_id=subj_id,
                faculty=effective_faculty,
                semester_id=sem_id,
                batch_id=batch_id if batch_id else None,
                date=date_str,
                lecture_slot=slot_str,
                defaults={'session_type': session_type, 'topic_covered': topic}
            )
            if not created:
                session.session_type = session_type
                if topic:
                    session.topic_covered = topic
                session.save()

        # Update records
        changes = []
        for key, val in request.POST.items():
            if key.startswith('status_'):
                student_id = key.replace('status_', '')
                remarks = request.POST.get(f'remarks_{student_id}', '').strip()
                benefit = request.POST.get(f'benefit_{student_id}', 'NONE').strip()

                rec, r_created = AttendanceRecord.objects.get_or_create(
                    session=session,
                    student_id=student_id,
                    defaults={'status': val, 'benefit_type': benefit, 'remarks': remarks, 'marked_via': 'MANUAL'}
                )
                if not r_created:
                    if rec.status != val or rec.remarks != remarks or rec.benefit_type != benefit:
                        changes.append(f"Student #{student_id}: {rec.status}->{val}, Bft={benefit}")
                        rec.status = val
                        rec.benefit_type = benefit
                        rec.remarks = remarks
                        rec.save()

        # Audit log if backdated or modified
        if changes or not created:
            log_audit(
                request=request,
                action="ATTENDANCE_MODIFIED",
                entity_type="AttendanceSession",
                entity_id=session.id,
                details=f"Attendance modified for {session.subject.code} [{session.session_type}] ({session.date}). Reason: {amendment_reason or 'Direct faculty entry'}. Changes: {', '.join(changes) or 'Initial bulk save'}"
            )

        messages.success(request, f"Attendance for {session.subject.code} [{session.get_session_type_display()}] recorded successfully! Overall Attendance: {session.attendance_percentage}%")
        return redirect('attendance_session_detail', pk=session.pk)

    # Faculty subjects
    if faculty:
        my_subjects = Subject.objects.filter(allocations__faculty=faculty, allocations__is_active=True).select_related('semester')
    else:
        my_subjects = Subject.objects.all().select_related('semester')

    is_already_marked = existing_session is not None

    context = {
        'my_subjects': my_subjects,
        'batches': Batch.objects.all(),
        'slots': AttendanceSession.SLOT_CHOICES,
        'session_type_choices': AttendanceSession.SESSION_TYPE_CHOICES,
        'benefit_choices': AttendanceRecord.BENEFIT_CHOICES,
        'selected_subject_id': int(selected_subject_id) if selected_subject_id else '',
        'selected_batch_id': int(selected_batch_id) if selected_batch_id else '',
        'selected_date': selected_date,
        'selected_slot': selected_slot,
        'selected_session_type': selected_session_type,
        'subject': subject,
        'students_list': students_list,
        'existing_session': existing_session,
        'is_already_marked': is_already_marked,
        'is_scheduled_on_date': is_scheduled_on_date,
        'is_backdated': existing_session is not None or selected_date != timezone.now().date().isoformat(),
    }
    return render(request, 'attendance/quick_mark.html', context)


@login_required
def student_attendance_view(request, student_id=None):
    """
    Comprehensive Student Attendance Register & Monthly Demarcation View:
    1. Monthly Aggregate Register (matching official university format):
       - Sr. No., Paper Code, Paper Name, Paper Type (TE/PR/TU), Month,
         Lectures Held, Lectures Attended, Medical/ECA/Sports/NCC/NSS Benefits,
         Final Lect Held, Final Lect Attended, Faculty Code & Name, %.
    2. Detailed Date-Wise Class Log:
       - Every lecture attended/absent/late/excused with date, slot, topic, status.
    """
    user = request.user
    student = None

    if user.is_student_role:
        student = getattr(user, 'student_profile', None)
    elif student_id and (user.is_faculty_role or user.is_admin_role):
        student = get_object_or_404(Student, id=student_id)
    elif user.is_admin_role or user.is_faculty_role:
        first_student = Student.objects.filter(is_archived=False).first()
        if first_student:
            return redirect('student_attendance_register', student_id=first_student.id)

    if not student:
        messages.error(request, "Student profile required.")
        return redirect('dashboard_redirect')

    # Fetch all records
    records_qs = AttendanceRecord.objects.filter(
        student=student
    ).select_related(
        'session__subject',
        'session__faculty__user',
        'session__semester',
        'session__batch'
    ).order_by('-session__date', '-session__lecture_slot')

    # 1. Build Monthly Aggregate Table (Matching University Format in Screenshot)
    monthly_groups = OrderedDict()

    # Sort chronological for the academic semester
    sorted_records = sorted(records_qs, key=lambda r: (r.session.subject.code, r.session.session_type, r.session.date))

    for rec in sorted_records:
        sess = rec.session
        subj = sess.subject
        stype = sess.session_type or subj.paper_type_code
        yr = sess.date.year
        mo = sess.date.month
        month_label = sess.date.strftime("%B")

        group_key = (subj.id, stype, yr, mo)
        if group_key not in monthly_groups:
            monthly_groups[group_key] = {
                'paper_code': subj.code,
                'paper_name': subj.name,
                'paper_type': stype,
                'month': month_label,
                'year': yr,
                'month_num': mo,
                'lect_held': 0,
                'lect_attd': 0,
                'bft_med': 0,
                'bft_eca': 0,
                'bft_sports': 0,
                'bft_ncc': 0,
                'bft_nss': 0,
                'faculty_codes': set(),
                'faculty_names': set(),
            }

        grp = monthly_groups[group_key]
        grp['lect_held'] += 1
        if rec.status in ['PRESENT', 'LATE']:
            grp['lect_attd'] += 1

        # Benefits
        if rec.benefit_type == 'MED':
            grp['bft_med'] += 1
        elif rec.benefit_type == 'ECA':
            grp['bft_eca'] += 1
        elif rec.benefit_type == 'SPORTS':
            grp['bft_sports'] += 1
        elif rec.benefit_type == 'NCC':
            grp['bft_ncc'] += 1
        elif rec.benefit_type == 'NSS':
            grp['bft_nss'] += 1

        if sess.faculty:
            grp['faculty_codes'].add(sess.faculty.employee_id)
            grp['faculty_names'].add(sess.faculty.full_name)

    monthly_rows = []
    sr_no = 1
    total_held = 0
    total_attd = 0
    total_bft_all = 0
    total_bft_med = 0

    stats_map = {
        'ALL': {'label': 'Total Combined (All Types)', 'held': 0, 'attd': 0, 'bft': 0, 'bft_med': 0},
        'TE': {'label': 'Theory (TE) Attendance', 'held': 0, 'attd': 0, 'bft': 0, 'bft_med': 0},
        'PR': {'label': 'Practical / Lab (PR) Attendance', 'held': 0, 'attd': 0, 'bft': 0, 'bft_med': 0},
        'TU': {'label': 'Tutorial (TU) Attendance', 'held': 0, 'attd': 0, 'bft': 0, 'bft_med': 0},
    }

    for key, data in monthly_groups.items():
        bft_sum = data['bft_eca'] + data['bft_sports'] + data['bft_ncc'] + data['bft_nss']
        final_held = data['lect_held']
        final_attd = min(final_held, data['lect_attd'] + bft_sum)
        pct = round((final_attd / final_held * 100), 1) if final_held > 0 else 0.0

        stype = data['paper_type']
        if stype in stats_map:
            stats_map[stype]['held'] += data['lect_held']
            stats_map[stype]['attd'] += data['lect_attd']
            stats_map[stype]['bft'] += bft_sum
            stats_map[stype]['bft_med'] += data['bft_med']

        monthly_rows.append({
            'sr_no': sr_no,
            'paper_code': data['paper_code'],
            'paper_name': data['paper_name'],
            'paper_type': data['paper_type'],
            'month': data['month'],
            'year': data['year'],
            'lect_held': data['lect_held'],
            'lect_attd': data['lect_attd'],
            'bft_med': data['bft_med'] if data['bft_med'] > 0 else '',
            'bft_eca': data['bft_eca'] if data['bft_eca'] > 0 else '',
            'bft_sports': data['bft_sports'] if data['bft_sports'] > 0 else '',
            'bft_ncc': data['bft_ncc'] if data['bft_ncc'] > 0 else '',
            'bft_nss': data['bft_nss'] if data['bft_nss'] > 0 else '',
            'total_attd_bft': bft_sum,
            'final_lect_held': final_held,
            'final_lect_attd': final_attd,
            'pct': pct,
            'faculty_code': ", ".join(sorted(data['faculty_codes'])) if data['faculty_codes'] else "F-GEN",
            'faculty_name': ", ".join(sorted(data['faculty_names'])) if data['faculty_names'] else "Faculty Member",
        })
        sr_no += 1
        total_held += data['lect_held']
        total_attd += data['lect_attd']
        total_bft_all += bft_sum
        total_bft_med += data['bft_med']

    grand_final_attd = min(total_held, total_attd + total_bft_all)
    overall_percentage = round((grand_final_attd / total_held * 100), 1) if total_held > 0 else 0.0

    stats_map['ALL']['held'] = total_held
    stats_map['ALL']['attd'] = total_attd
    stats_map['ALL']['bft'] = total_bft_all
    stats_map['ALL']['bft_med'] = total_bft_med

    component_stats = {}
    for c_key, c_data in stats_map.items():
        f_attd = min(c_data['held'], c_data['attd'] + c_data['bft'])
        c_pct = round((f_attd / c_data['held'] * 100), 1) if c_data['held'] > 0 else 0.0
        component_stats[c_key] = {
            'label': c_data['label'],
            'held': c_data['held'],
            'attd': c_data['attd'],
            'bft': c_data['bft'],
            'bft_med': c_data['bft_med'],
            'final_attd': f_attd,
            'pct': c_pct,
            'shortage': c_pct < 75.0 if c_data['held'] > 0 else False,
        }

    selected_component = request.GET.get('component', 'ALL')
    if selected_component not in component_stats:
        selected_component = 'ALL'

    # 2. Detailed Date-Wise Log with Filters
    subject_filter = request.GET.get('subject')
    month_filter = request.GET.get('month')
    status_filter = request.GET.get('status')
    type_filter = request.GET.get('type')

    filtered_records = records_qs
    if subject_filter:
        filtered_records = filtered_records.filter(session__subject_id=subject_filter)
    if month_filter:
        filtered_records = filtered_records.filter(session__date__month=month_filter)
    if status_filter:
        filtered_records = filtered_records.filter(status=status_filter)
    if type_filter:
        filtered_records = filtered_records.filter(session__session_type=type_filter)

    enrolled_subjects = Subject.objects.filter(
        semester=student.current_semester
    ).order_by('code')

    months_list = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]

    context = {
        'student': student,
        'monthly_rows': monthly_rows,
        'total_lect_held': total_held,
        'total_lect_attd': total_attd,
        'total_bft_all': total_bft_all,
        'total_bft_med': total_bft_med,
        'grand_final_attd': grand_final_attd,
        'overall_percentage': overall_percentage,
        'detailed_records': filtered_records,
        'enrolled_subjects': enrolled_subjects,
        'months_list': months_list,
        'selected_subject': int(subject_filter) if subject_filter else '',
        'selected_month': int(month_filter) if month_filter else '',
        'selected_status': status_filter or '',
        'selected_type': type_filter or '',
        'is_student_viewer': request.user.is_student_role,
        'component_stats': component_stats,
        'component_stats_json': json.dumps(component_stats),
        'selected_component': selected_component,
    }
    return render(request, 'attendance/student_attendance_view.html', context)


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
