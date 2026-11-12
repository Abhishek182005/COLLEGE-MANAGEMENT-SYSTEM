import json
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect
from django.http import HttpResponse
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
from academics.models import Department, Course, Semester, Subject
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


def _parse_ia_filter_params(request):
    params = request.GET if request.method == 'GET' else request.POST
    course_id = params.get('course') or None
    semester_id = params.get('semester') or None
    subject_id = params.get('subject') or None
    batch_id = params.get('batch') or None
    exam_type = params.get('exam_type', 'CBCS_NEP').strip() or 'CBCS_NEP'
    section_sorting = params.get('section_sorting', 'NO')
    my_subjects_only = params.get('my_subjects') == '1'

    # Auto-select first course if none selected and courses exist (for cleaner initial Course Wise view)
    if not course_id and not semester_id and not subject_id and request.method == 'GET' and 'course' not in request.GET:
        first_course = Course.objects.first()
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


@login_required
@role_required('ADMIN', 'FACULTY')
def final_ia_report_view(request):
    """
    Final IA Report (Course Wise) module for Faculty & Admin.
    Combines attendance metrics, C.T. marks, Assignment marks, Moderation & Total TE_IA.
    Supports inline editing/confirmation, browser printing, PDF download, and Excel download.
    """
    if request.method == 'POST':
        row_keys = request.POST.getlist('row_keys')
        action_type = request.POST.get('action_type', 'save')
        faculty_obj = getattr(request.user, 'faculty_profile', None)
        today = timezone.localdate()
        updated_count = 0

        for rk in row_keys:
            try:
                st_id_str, subj_id_str = rk.split('_', 1)
                st_id = int(st_id_str)
                subj_id = int(subj_id_str)
            except (ValueError, TypeError):
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
        messages.success(request, f"Successfully saved Final IA evaluations for {updated_count} records.")
        # Redirect back preserving query string filters
        qs_params = []
        for k in ('course', 'semester', 'subject', 'batch', 'exam_type', 'section_sorting', 'my_subjects'):
            v = request.POST.get(k)
            if v:
                qs_params.append(f"{k}={v}")
        redirect_url = request.path + ("?" + "&".join(qs_params) if qs_params else "")
        return redirect(redirect_url)

    filters = _parse_ia_filter_params(request)
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
    if filters['course_id']:
        semesters = semesters.filter(course_id=filters['course_id'])

    subjects = Subject.objects.select_related('semester__course').order_by('code')
    if filters['semester_id']:
        subjects = subjects.filter(semester_id=filters['semester_id'])
    elif filters['course_id']:
        subjects = subjects.filter(semester__course_id=filters['course_id'])

    batches = Batch.objects.select_related('course').order_by('name')
    if filters['course_id']:
        batches = batches.filter(course_id=filters['course_id'])

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
        'edit_mode': request.GET.get('edit') == '1',
    }
    return render(request, 'reports/final_ia_report.html', context)


@login_required
@role_required('ADMIN', 'FACULTY')
def final_ia_report_pdf_view(request):
    """Download or print-preview the Final IA Report (Course Wise) as a landscape A4 PDF."""
    filters = _parse_ia_filter_params(request)
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
    course_slug = report_data['selected_course'].code if report_data['selected_course'] else 'All_Courses'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'{disposition}; filename="Final_IA_Report_{course_slug}.pdf"'
    return response


@login_required
@role_required('ADMIN', 'FACULTY')
def final_ia_report_excel_view(request):
    """Download the Final IA Report (Course Wise) as an Excel (.xlsx) spreadsheet."""
    filters = _parse_ia_filter_params(request)
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
    course_slug = report_data['selected_course'].code if report_data['selected_course'] else 'All_Courses'
    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="Final_IA_Report_{course_slug}.xlsx"'
    return response
