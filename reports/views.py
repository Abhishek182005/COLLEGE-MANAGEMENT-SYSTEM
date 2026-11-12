import json
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.generic import TemplateView, ListView
from django.db.models import Count, Avg
from accounts.permissions import AdminRequiredMixin, FacultyRequiredMixin, role_required
from reports.models import AuditLog
from reports.utils import log_audit
from reports.ia_utils import (
    build_final_ia_report_data,
    generate_final_ia_report_pdf,
    export_final_ia_report_excel,
)
from students.models import Student, Batch
from academics.models import Department, Course, Semester, Subject, SubjectAllocation
from attendance.models import AttendanceRecord, AttendanceSession
from examinations.models import Marks, InternalAssessmentRecord


class ReportsDashboardView(FacultyRequiredMixin, TemplateView):
    template_name = 'reports/reports_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # 1. Department Enrollment Stats
        dept_data = Department.objects.annotate(count=Count('students')).values('code', 'count')
        ctx['dept_labels'] = json.dumps([d['code'] for d in dept_data])
        ctx['dept_counts'] = json.dumps([d['count'] for d in dept_data])

        # 2. Overall Attendance Distribution
        records = AttendanceRecord.objects.all()
        present_cnt = records.filter(status='PRESENT').count()
        absent_cnt = records.filter(status='ABSENT').count()
        late_cnt = records.filter(status='LATE').count()
        excused_cnt = records.filter(status='EXCUSED').count()

        ctx['att_labels'] = json.dumps(['Present', 'Absent', 'Late', 'Excused'])
        ctx['att_counts'] = json.dumps([present_cnt, absent_cnt, late_cnt, excused_cnt])

        # 3. Grade Distribution
        grades_data = Marks.objects.values('grade').annotate(count=Count('id')).order_by('grade')
        all_grades = ['A+', 'A', 'B+', 'B', 'C', 'D', 'F']
        grade_dict = {g['grade']: g['count'] for g in grades_data if g['grade']}
        ctx['grade_labels'] = json.dumps(all_grades)
        ctx['grade_counts'] = json.dumps([grade_dict.get(g, 0) for g in all_grades])

        # Key counters
        ctx['total_records'] = records.count()
        ctx['total_marks'] = Marks.objects.count()
        ctx['total_audits'] = AuditLog.objects.count()

        return ctx


class AuditLogListView(AdminRequiredMixin, ListView):
    model = AuditLog
    template_name = 'reports/audit_logs.html'
    context_object_name = 'logs'
    paginate_by = 30

    def get_queryset(self):
        qs = AuditLog.objects.select_related('user')
        action = self.request.GET.get('action')
        entity = self.request.GET.get('entity')
        if action:
            qs = qs.filter(action__icontains=action)
        if entity:
            qs = qs.filter(entity_type__icontains=entity)
        return qs.order_by('-timestamp')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['selected_action'] = self.request.GET.get('action', '')
        ctx['selected_entity'] = self.request.GET.get('entity', '')
        return ctx


def _parse_decimal_or_none(val_str):
    if val_str is None:
        return None
    s = val_str.strip()
    if s == '':
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _get_faculty_ia_scope(user):
    """
    Return scoping metadata for IA views.
    Admins see all courses/subjects; restricted faculty only see their own allocated subjects/courses.
    """
    is_restricted = user.is_faculty_role and not user.is_admin_role
    if not is_restricted:
        return {
            'is_restricted': False,
            'subject_ids': None,
            'semester_ids': None,
            'course_ids': None,
        }

    faculty_profile = getattr(user, 'faculty_profile', None)
    if not faculty_profile:
        return {
            'is_restricted': True,
            'subject_ids': set(),
            'semester_ids': set(),
            'course_ids': set(),
        }

    allocated = Subject.objects.filter(
        allocations__faculty=faculty_profile,
        allocations__is_active=True,
    ).select_related('semester').distinct()

    subject_ids = set(allocated.values_list('id', flat=True))
    semester_ids = set(allocated.values_list('semester_id', flat=True))
    course_ids = set(allocated.values_list('semester__course_id', flat=True))
    return {
        'is_restricted': True,
        'subject_ids': subject_ids,
        'semester_ids': semester_ids,
        'course_ids': course_ids,
    }


def _parse_ia_filter_params(request, scope):
    params = request.GET if request.method == 'GET' else request.POST
    course_id = params.get('course') or None
    semester_id = params.get('semester') or None
    subject_id = params.get('subject') or None
    batch_id = params.get('batch') or None
    exam_type = params.get('exam_type', 'CBCS_NEP').strip() or 'CBCS_NEP'
    section_sorting = params.get('section_sorting', 'NO')
    # Restricted faculty are ALWAYS locked to their own assigned subjects
    my_subjects_only = True if scope['is_restricted'] else (params.get('my_subjects') == '1')

    # Auto-select first allowed course on clean initial GET load
    if not course_id and not semester_id and not subject_id and request.method == 'GET' and 'course' not in request.GET:
        courses_qs = Course.objects.order_by('code')
        if scope['is_restricted']:
            courses_qs = courses_qs.filter(id__in=scope['course_ids'])
        first_course = courses_qs.first()
        if first_course:
            course_id = str(first_course.id)

    return {
        'course_id': course_id,
        'semester_id': semester_id,
        'subject_id': subject_id,
        'batch_id': batch_id,
        'exam_type': exam_type,
        'section_sorting': section_sorting,
        'my_subjects_only': my_subjects_only,
    }


def _validate_faculty_filter_scope(scope, filters):
    """Ensure a restricted faculty user cannot inspect or export courses/semesters/subjects they don't teach."""
    if not scope['is_restricted']:
        return True
    try:
        if filters['subject_id'] and int(filters['subject_id']) not in scope['subject_ids']:
            return False
        if filters['semester_id'] and int(filters['semester_id']) not in scope['semester_ids']:
            return False
        if filters['course_id'] and int(filters['course_id']) not in scope['course_ids']:
            return False
    except (ValueError, TypeError):
        return False
    return True


@login_required
@role_required('ADMIN', 'FACULTY')
def final_ia_report_view(request):
    """
    Internal Assessment Evaluation & Grade Ledger for Faculty & Admin.
    Strictly scopes faculty access to their own assigned subjects & courses.
    """
    scope = _get_faculty_ia_scope(request.user)

    if request.method == 'POST':
        row_keys = request.POST.getlist('row_keys')
        action_type = request.POST.get('action_type', 'save')
        faculty_obj = getattr(request.user, 'faculty_profile', None)
        today = timezone.localdate()

        parsed_rows = []
        for rk in row_keys:
            try:
                st_id_str, subj_id_str = rk.split('_', 1)
                st_id = int(st_id_str)
                subj_id = int(subj_id_str)
            except (ValueError, TypeError):
                continue

            if scope['is_restricted'] and subj_id not in scope['subject_ids']:
                log_audit(
                    request=request,
                    action="UNAUTHORIZED_IA_EDIT_ATTEMPT",
                    entity_type="Subject",
                    entity_id=subj_id,
                    details=f"Blocked faculty {request.user.username} from modifying IA marks for unassigned subject ID {subj_id}."
                )
                return HttpResponseForbidden(
                    "Access denied: You can only enter or confirm marks for your own assigned courses and subjects."
                )
            parsed_rows.append((rk, st_id, subj_id))

        # Preload valid (student_id, semester_id) & subject_semester for integrity
        subj_sem_map = dict(
            Subject.objects.filter(id__in=[p[2] for p in parsed_rows]).values_list('id', 'semester_id')
        )
        valid_students_sem = dict(
            Student.objects.filter(id__in=[p[1] for p in parsed_rows], is_archived=False).values_list('id', 'current_semester_id')
        )

        updated_count = 0
        for rk, st_id, subj_id in parsed_rows:
            if subj_id not in subj_sem_map or valid_students_sem.get(st_id) != subj_sem_map[subj_id]:
                continue

            max_ia = _parse_decimal_or_none(request.POST.get(f'max_ia_{rk}'))
            attd_max = _parse_decimal_or_none(request.POST.get(f'attd_max_{rk}'))
            final_attd = _parse_decimal_or_none(request.POST.get(f'final_attd_{rk}'))
            marks_ct = _parse_decimal_or_none(request.POST.get(f'marks_ct_{rk}'))
            marks_assi = _parse_decimal_or_none(request.POST.get(f'marks_assi_{rk}'))
            mod_marks = _parse_decimal_or_none(request.POST.get(f'mod_{rk}'))
            is_confirmed_checked = request.POST.get(f'confirm_{rk}') == '1' or action_type == 'confirm_all'

            defaults = {
                'max_ia_marks': max_ia if max_ia is not None else Decimal('30.00'),
                'attd_max_marks': attd_max if attd_max is not None else Decimal('6.0'),
                'final_attd_marks': final_attd,
                'marks_ct': marks_ct,
                'marks_assi': marks_assi,
                'moderation_marks': mod_marks,
                'updated_by': faculty_obj,
            }
            if is_confirmed_checked:
                defaults['confirm_status'] = 'CONFIRMED'
                defaults['confirm_date'] = today
            elif action_type == 'unconfirm_all':
                defaults['confirm_status'] = ''
                defaults['confirm_date'] = None
            else:
                defaults['confirm_status'] = 'CONFIRMED' if request.POST.get(f'confirm_{rk}') == '1' else ''
                defaults['confirm_date'] = today if defaults['confirm_status'] == 'CONFIRMED' else None

            rec, created = InternalAssessmentRecord.objects.get_or_create(
                student_id=st_id, subject_id=subj_id, defaults=defaults
            )
            if not created:
                rec.max_ia_marks = defaults['max_ia_marks']
                rec.attd_max_marks = defaults['attd_max_marks']
                rec.final_attd_marks = defaults['final_attd_marks']
                rec.marks_ct = defaults['marks_ct']
                rec.marks_assi = defaults['marks_assi']
                rec.moderation_marks = defaults['moderation_marks']
                rec.updated_by = faculty_obj
                if action_type == 'confirm_all' or request.POST.get(f'confirm_{rk}') == '1':
                    rec.confirm_status = 'CONFIRMED'
                    if not rec.confirm_date:
                        rec.confirm_date = today
                elif action_type == 'unconfirm_all' or f'confirm_{rk}' in request.POST or action_type == 'save':
                    if request.POST.get(f'confirm_{rk}') == '1':
                        rec.confirm_status = 'CONFIRMED'
                        if not rec.confirm_date:
                            rec.confirm_date = today
                    else:
                        rec.confirm_status = ''
                        rec.confirm_date = None
                rec.save()
            updated_count += 1

        log_audit(
            request=request,
            action="FINAL_IA_UPDATED",
            entity_type="InternalAssessmentRecord",
            entity_id=0,
            details=f"Updated/confirmed Final IA marks for {updated_count} student-subject rows (action={action_type})."
        )
        messages.success(request, f"Successfully saved IA evaluations for {updated_count} records.")
        qs_params = []
        for k in ('course', 'semester', 'subject', 'batch', 'exam_type', 'section_sorting', 'my_subjects'):
            v = request.POST.get(k)
            if v:
                qs_params.append(f"{k}={v}")
        redirect_url = request.path + ("?" + "&".join(qs_params) if qs_params else "")
        return redirect(redirect_url)

    filters = _parse_ia_filter_params(request, scope)
    if not _validate_faculty_filter_scope(scope, filters):
        return HttpResponseForbidden(
            "Access denied: You can only view IA records for your own assigned courses and subjects."
        )

    report_data = build_final_ia_report_data(
        course_id=filters['course_id'],
        semester_id=filters['semester_id'],
        subject_id=filters['subject_id'],
        batch_id=filters['batch_id'],
        exam_type=filters['exam_type'],
        section_sorting=filters['section_sorting'],
        my_subjects_only=filters['my_subjects_only'],
        user=request.user,
    )

    courses = Course.objects.all().order_by('code')
    semesters = Semester.objects.select_related('course', 'academic_session').order_by('course__code', 'semester_number')
    subjects = Subject.objects.select_related('semester__course').order_by('code')
    batches = Batch.objects.select_related('course').order_by('name')

    if scope['is_restricted']:
        courses = courses.filter(id__in=scope['course_ids'])
        semesters = semesters.filter(id__in=scope['semester_ids'])
        subjects = subjects.filter(id__in=scope['subject_ids'])
        batches = batches.filter(course_id__in=scope['course_ids'])

    if filters['course_id']:
        semesters = semesters.filter(course_id=filters['course_id'])
        batches = batches.filter(course_id=filters['course_id'])

    if filters['semester_id']:
        subjects = subjects.filter(semester_id=filters['semester_id'])
    elif filters['course_id']:
        subjects = subjects.filter(semester__course_id=filters['course_id'])

    context = {
        'report': report_data,
        'courses': courses,
        'semesters': semesters,
        'subjects': subjects,
        'batches': batches,
        'selected_course_id': str(filters['course_id'] or ''),
        'selected_semester_id': str(filters['semester_id'] or ''),
        'selected_subject_id': str(filters['subject_id'] or ''),
        'selected_batch_id': str(filters['batch_id'] or ''),
        'exam_type': filters['exam_type'],
        'section_sorting': filters['section_sorting'],
        'my_subjects_only': filters['my_subjects_only'],
        'is_restricted_faculty': scope['is_restricted'],
        'has_allocated_subjects': bool(scope['subject_ids']) if scope['is_restricted'] else True,
        'edit_mode': request.GET.get('edit') == '1',
    }
    return render(request, 'reports/final_ia_report.html', context)


@login_required
@role_required('ADMIN', 'FACULTY')
def final_ia_report_pdf_view(request):
    """Download or print-preview the IA Evaluation Ledger as a landscape A4 PDF."""
    scope = _get_faculty_ia_scope(request.user)
    filters = _parse_ia_filter_params(request, scope)
    if not _validate_faculty_filter_scope(scope, filters):
        return HttpResponseForbidden(
            "Access denied: You can only export IA records for your own assigned courses and subjects."
        )
    report_data = build_final_ia_report_data(
        course_id=filters['course_id'],
        semester_id=filters['semester_id'],
        subject_id=filters['subject_id'],
        batch_id=filters['batch_id'],
        exam_type=filters['exam_type'],
        section_sorting=filters['section_sorting'],
        my_subjects_only=filters['my_subjects_only'],
        user=request.user,
    )
    pdf_bytes = generate_final_ia_report_pdf(report_data)
    disposition = 'inline' if request.GET.get('view') == '1' else 'attachment'
    course_slug = report_data['selected_course'].code if report_data['selected_course'] else 'Assigned_Courses'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'{disposition}; filename="IA_Evaluation_Ledger_{course_slug}.pdf"'
    return response


@login_required
@role_required('ADMIN', 'FACULTY')
def final_ia_report_excel_view(request):
    """Download the IA Evaluation Ledger as an Excel (.xlsx) spreadsheet."""
    scope = _get_faculty_ia_scope(request.user)
    filters = _parse_ia_filter_params(request, scope)
    if not _validate_faculty_filter_scope(scope, filters):
        return HttpResponseForbidden(
            "Access denied: You can only export IA records for your own assigned courses and subjects."
        )
    report_data = build_final_ia_report_data(
        course_id=filters['course_id'],
        semester_id=filters['semester_id'],
        subject_id=filters['subject_id'],
        batch_id=filters['batch_id'],
        exam_type=filters['exam_type'],
        section_sorting=filters['section_sorting'],
        my_subjects_only=filters['my_subjects_only'],
        user=request.user,
    )
    excel_bytes = export_final_ia_report_excel(report_data)
    course_slug = report_data['selected_course'].code if report_data['selected_course'] else 'Assigned_Courses'
    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="IA_Evaluation_Ledger_{course_slug}.xlsx"'
    return response
