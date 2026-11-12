import io
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.conf import settings
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from academics.models import Course, Semester, Subject, SubjectAllocation
from students.models import Student, Batch
from attendance.models import AttendanceRecord
from examinations.models import Marks, InternalAssessmentRecord
from assignments.models import Submission


ROMAN_MAP = {
    1: 'I', 2: 'II', 3: 'III', 4: 'IV',
    5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII'
}


def _fmt_num(val):
    """Format decimal/int cleanly without trailing .00 (e.g., 10.00 -> '10', 11.50 -> '11.5')."""
    if val is None or val == '':
        return ''
    d = Decimal(str(val))
    if d == d.to_integral_value():
        return str(int(d))
    s = f"{d.quantize(Decimal('0.01')).normalize():f}"
    return s


def _calculate_auto_attd_marks(pct_attd, attd_max, max_ia, lect_held, threshold):
    """
    Calculate Final Attendance Marks based on attendance % and effective attendance weightage.
    In NEP/CBCS:
      - If Max IA = 30 -> Attendance cap = 6 (20% of 30)
      - If Max IA = 10 -> Attendance cap = 2 (20% of 10)
      - If Max IA = 0 or Lect Delivered = 0 -> 0
    """
    if lect_held <= 0 or max_ia <= 0 or attd_max <= 0:
        return Decimal('0')

    prop_cap = (Decimal(str(max_ia)) * Decimal('0.20')).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    cap = min(Decimal(str(attd_max)), prop_cap)

    if pct_attd >= 85:
        ratio = Decimal('1.0')
    elif pct_attd >= 80:
        ratio = Decimal('0.80')
    elif pct_attd >= 75:
        ratio = Decimal('0.67')
    elif pct_attd >= 70:
        ratio = Decimal('0.50')
    elif pct_attd >= float(threshold):
        ratio = Decimal('0.33')
    else:
        ratio = Decimal('0')

    raw = cap * ratio
    # Round cleanly to nearest integer or 0.5
    return raw.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def build_final_ia_report_data(
    course_id=None,
    semester_id=None,
    subject_id=None,
    batch_id=None,
    exam_type='CBCS_NEP',
    section_sorting='NO',
    my_subjects_only=False,
    user=None,
):
    """
    Construct the complete Final IA Report (Course Wise) dataset combining:
    - Student enrollment & roll details
    - Live lecture delivery & attendance + benefit counts
    - Class Test (C.T.) marks from examinations.Marks
    - Assignment (Assi.) marks from assignments.Submission / Marks
    - Manual/Confirmed overrides from examinations.InternalAssessmentRecord
    """
    try:
        from accounts.models import CollegeSetting
        college_obj = CollegeSetting.get_settings()
        college_name = college_obj.name
        college_code = college_obj.college_code
        threshold = float(college_obj.attendance_threshold)
    except Exception:
        college_name = getattr(settings, 'COLLEGE_NAME', 'CampusConnect Institute of Technology')
        college_code = getattr(settings, 'COLLEGE_CODE', 'CCIT-092')
        threshold = float(getattr(settings, 'ATTENDANCE_SHORTAGE_THRESHOLD', 75.0))

    selected_course = Course.objects.filter(id=course_id).first() if course_id else None
    selected_semester = Semester.objects.select_related('course', 'academic_session').filter(id=semester_id).first() if semester_id else None
    selected_subject = Subject.objects.select_related('semester__course').filter(id=subject_id).first() if subject_id else None
    selected_batch = Batch.objects.filter(id=batch_id).first() if batch_id else None

    if selected_subject and not selected_semester:
        selected_semester = selected_subject.semester
    if selected_semester and not selected_course:
        selected_course = selected_semester.course

    students_qs = Student.objects.filter(is_archived=False).select_related(
        'user', 'course', 'department', 'current_semester', 'batch'
    )
    if selected_course:
        students_qs = students_qs.filter(course=selected_course)
    if selected_semester:
        students_qs = students_qs.filter(current_semester=selected_semester)
    if selected_batch:
        students_qs = students_qs.filter(batch=selected_batch)

    if section_sorting == 'YES':
        students_qs = students_qs.order_by('batch__name', 'roll_number')
    else:
        students_qs = students_qs.order_by('roll_number')

    # Determine allocated subjects if filtering to faculty's subjects
    faculty_subject_ids = None
    if my_subjects_only:
        if user and hasattr(user, 'faculty_profile'):
            faculty_subject_ids = set(
                SubjectAllocation.objects.filter(
                    faculty=user.faculty_profile, is_active=True
                ).values_list('subject_id', flat=True)
            )
        else:
            faculty_subject_ids = set()

    if faculty_subject_ids is not None:
        students_qs = students_qs.filter(
            current_semester__subjects__id__in=faculty_subject_ids
        ).distinct()
        if section_sorting == 'YES':
            students_qs = students_qs.order_by('batch__name', 'roll_number')
        else:
            students_qs = students_qs.order_by('roll_number')

    students = list(students_qs)
    student_ids = [s.id for s in students]

    # Preload subjects grouped by semester
    sem_ids = {s.current_semester_id for s in students if s.current_semester_id}
    subjects_qs = Subject.objects.filter(semester_id__in=sem_ids).order_by('code')
    if selected_subject:
        subjects_qs = subjects_qs.filter(id=selected_subject.id)
    if faculty_subject_ids is not None:
        subjects_qs = subjects_qs.filter(id__in=faculty_subject_ids)

    subjects_by_sem = {}
    all_subject_ids = []
    for subj in subjects_qs:
        subjects_by_sem.setdefault(subj.semester_id, []).append(subj)
        all_subject_ids.append(subj.id)

    # Bulk preload AttendanceRecords
    att_map = {}  # (student_id, subject_id) -> {'held': int, 'attd': int, 'bft': int}
    if student_ids and all_subject_ids:
        att_records = AttendanceRecord.objects.filter(
            student_id__in=student_ids,
            session__subject_id__in=all_subject_ids
        ).values('student_id', 'session__subject_id', 'status', 'benefit_type')

        for r in att_records:
            key = (r['student_id'], r['session__subject_id'])
            entry = att_map.setdefault(key, {'held': 0, 'attd': 0, 'bft': 0})
            entry['held'] += 1
            if r['status'] in ('PRESENT', 'LATE'):
                entry['attd'] += 1
            if r['benefit_type'] in ('ECA', 'SPORTS', 'NCC', 'NSS'):
                entry['bft'] += 1

    # Bulk preload Examination Marks
    ct_marks_map = {}     # (student_id, subject_id) -> {'obt': Decimal, 'max': Decimal}
    assi_exam_map = {}    # (student_id, subject_id) -> {'obt': Decimal, 'max': Decimal}
    if student_ids and all_subject_ids:
        exam_marks = Marks.objects.filter(
            student_id__in=student_ids,
            assessment_component__subject_id__in=all_subject_ids
        ).select_related('assessment_component')
        for m in exam_marks:
            key = (m.student_id, m.assessment_component.subject_id)
            title_lower = (m.assessment_component.title or '').lower()
            target_map = assi_exam_map if 'assign' in title_lower else ct_marks_map
            entry = target_map.setdefault(key, {'obt': Decimal('0'), 'max': Decimal('0')})
            entry['obt'] += m.marks_obtained
            entry['max'] += m.assessment_component.max_marks

    # Bulk preload Graded Assignment Submissions
    assi_sub_map = {}  # (student_id, subject_id) -> {'obt': Decimal, 'max': Decimal}
    if student_ids and all_subject_ids:
        subs = Submission.objects.filter(
            student_id__in=student_ids,
            assignment__subject_id__in=all_subject_ids,
            status='GRADED',
            marks_obtained__isnull=False
        ).select_related('assignment')
        for sub in subs:
            key = (sub.student_id, sub.assignment.subject_id)
            entry = assi_sub_map.setdefault(key, {'obt': Decimal('0'), 'max': Decimal('0')})
            entry['obt'] += sub.marks_obtained
            entry['max'] += sub.assignment.max_score

    # Bulk preload saved InternalAssessmentRecord overrides
    ia_saved_map = {}
    if student_ids and all_subject_ids:
        saved_qs = InternalAssessmentRecord.objects.filter(
            student_id__in=student_ids,
            subject_id__in=all_subject_ids
        )
        for rec in saved_qs:
            ia_saved_map[(rec.student_id, rec.subject_id)] = rec

    rows = []
    sr_no = 1
    for st in students:
        sem_subjects = subjects_by_sem.get(st.current_semester_id, [])
        for subj in sem_subjects:
            key = (st.id, subj.id)
            saved = ia_saved_map.get(key)

            # Determine Max IA and Attd MKS
            if saved:
                max_ia = saved.max_ia_marks
                attd_max = saved.attd_max_marks
            else:
                if subj.subject_type == Subject.TYPE_PRACTICAL:
                    max_ia = Decimal('0')
                    attd_max = Decimal('0.0')
                elif subj.credits <= 2:
                    max_ia = Decimal('10')
                    attd_max = Decimal('6.0')
                else:
                    max_ia = Decimal('30')
                    attd_max = Decimal('6.0')

            # Attendance computation
            att_data = att_map.get(key, {'held': 0, 'attd': 0, 'bft': 0})
            lect_held = att_data['held']
            lect_attd_val = min(lect_held, att_data['attd'] + att_data['bft'])
            pct_attd = round((lect_attd_val / lect_held) * 100, 2) if lect_held > 0 else 0.0

            # Final Marks Attd.
            if saved and saved.final_attd_marks is not None:
                final_attd_marks = saved.final_attd_marks
            else:
                final_attd_marks = _calculate_auto_attd_marks(pct_attd, attd_max, max_ia, lect_held, threshold)

            # Marks C.T. (scaled to 40% of Max IA if auto-fetched from Exams, or saved override)
            ct_cap = (max_ia * Decimal('0.40')).quantize(Decimal('0.01'))
            if saved and saved.marks_ct is not None:
                marks_ct_val = saved.marks_ct
            elif key in ct_marks_map and ct_marks_map[key]['max'] > 0 and max_ia > 0:
                ct_entry = ct_marks_map[key]
                marks_ct_val = ((ct_entry['obt'] / ct_entry['max']) * ct_cap).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            else:
                marks_ct_val = None

            # Marks Assi. (scaled to 40% of Max IA from Assignments / Assignment Marks, or saved override)
            assi_cap = (max_ia * Decimal('0.40')).quantize(Decimal('0.01'))
            if saved and saved.marks_assi is not None:
                marks_assi_val = saved.marks_assi
            elif key in assi_sub_map and assi_sub_map[key]['max'] > 0 and max_ia > 0:
                a_entry = assi_sub_map[key]
                marks_assi_val = ((a_entry['obt'] / a_entry['max']) * assi_cap).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            elif key in assi_exam_map and assi_exam_map[key]['max'] > 0 and max_ia > 0:
                a_entry = assi_exam_map[key]
                marks_assi_val = ((a_entry['obt'] / a_entry['max']) * assi_cap).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            else:
                marks_assi_val = None

            # Moderation
            mod_val = saved.moderation_marks if (saved and saved.moderation_marks is not None) else None

            # Total Theory IA (TE_IA)
            te_ia_val = (
                (final_attd_marks or Decimal('0'))
                + (marks_ct_val or Decimal('0'))
                + (marks_assi_val or Decimal('0'))
                + (mod_val or Decimal('0'))
            )
            if max_ia > 0:
                te_ia_val = min(max_ia, te_ia_val)

            confirm_status_raw = saved.confirm_status if saved else ''
            confirm_status_disp = 'Confirmed' if confirm_status_raw == 'CONFIRMED' else 'Pending'
            confirm_date_disp = saved.confirm_date.strftime('%d %b %Y') if (saved and saved.confirm_date) else '—'

            rows.append({
                'sr_no': sr_no,
                'student_id': st.id,
                'subject_id': subj.id,
                'univ_rollno': st.registration_number,
                'college_rollno': st.roll_number,
                'name': st.full_name.title(),
                'paper_id': subj.code,
                'paper_name': subj.name,
                'max_ia_marks': _fmt_num(max_ia),
                'max_ia_raw': str(max_ia),
                'lect_deliver': lect_held,
                'lect_attd': '—' if (lect_held == 0 and lect_attd_val == 0) else lect_attd_val,
                'pct_attd': f"{pct_attd:.2f}",
                'pct_attd_num': pct_attd,
                'attd_mks': f"{float(attd_max):.1f}",
                'attd_mks_raw': str(attd_max),
                'benefit_dash': str(att_data['bft']) if att_data['bft'] > 0 else '—',
                'final_marks_attd': _fmt_num(final_attd_marks),
                'final_attd_raw': str(saved.final_attd_marks) if (saved and saved.final_attd_marks is not None) else '',
                'marks_ct': _fmt_num(marks_ct_val),
                'marks_ct_raw': str(marks_ct_val) if marks_ct_val is not None else '',
                'marks_assi': _fmt_num(marks_assi_val),
                'marks_assi_raw': str(marks_assi_val) if marks_assi_val is not None else '',
                'mod_marks': _fmt_num(mod_val),
                'mod_raw': str(mod_val) if mod_val is not None else '',
                'te_ia': _fmt_num(te_ia_val),
                'te_ia_num': float(te_ia_val),
                'class_section': st.batch.name if st.batch else '—',
                'ia_confirm_status': confirm_status_disp,
                'ia_confirm_date': confirm_date_disp,
                'is_confirmed': confirm_status_raw == 'CONFIRMED',
            })
            sr_no += 1

    # Modern structured institutional metadata
    college_name_line = f"{college_name} ({college_code})"
    if selected_course:
        course_display = f"{selected_course.code} — {selected_course.name}"
    else:
        course_display = "Assigned Courses Overview" if my_subjects_only else "All Enrolled Courses"

    if selected_semester:
        sem_num = selected_semester.semester_number
        part_num = (sem_num + 1) // 2
        part_sem_display = f"Semester {sem_num} ({ROMAN_MAP.get(sem_num, sem_num)}) • Year {ROMAN_MAP.get(part_num, part_num)}"
    else:
        part_sem_display = "All Semesters"

    confirmed_cnt = sum(1 for r in rows if r['is_confirmed'])
    shortage_cnt = sum(1 for r in rows if r['lect_deliver'] > 0 and r['pct_attd_num'] < threshold)
    avg_ia = round(sum(r['te_ia_num'] for r in rows) / len(rows), 2) if rows else 0.0

    return {
        'college_name_line': college_name_line,
        'exam_type': exam_type or 'CBCS_NEP',
        'course_display': course_display,
        'part_sem_display': part_sem_display,
        'section_sorting': 'Section-Wise' if section_sorting == 'YES' else 'Roll Number',
        'printing_date': timezone.localtime().strftime('%d %b %Y, %H:%M'),
        'rows': rows,
        'selected_course': selected_course,
        'selected_semester': selected_semester,
        'selected_subject': selected_subject,
        'selected_batch': selected_batch,
        'threshold': threshold,
        'my_subjects_only': my_subjects_only,
        'summary': {
            'total_rows': len(rows),
            'confirmed_count': confirmed_cnt,
            'pending_count': len(rows) - confirmed_cnt,
            'shortage_count': shortage_cnt,
            'avg_te_ia': avg_ia,
        },
    }


def generate_final_ia_report_pdf(report_data):
    """
    Generate landscape A4 PDF using the CampusConnect modern navy & slate IA Evaluation Ledger design.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=18,
        leftMargin=18,
        topMargin=18,
        bottomMargin=18,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'IATitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=14, leading=17,
        textColor=colors.HexColor('#1e3a8a'), alignment=0, spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        'IASubtitle', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.5, leading=11,
        textColor=colors.HexColor('#475569'), alignment=0, spaceAfter=6
    )
    meta_label_style = ParagraphStyle(
        'IAMetaLabel', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=7.5, leading=10,
        textColor=colors.HexColor('#475569')
    )
    meta_val_style = ParagraphStyle(
        'IAMetaVal', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8.2, leading=11,
        textColor=colors.HexColor('#0f172a')
    )
    th_style = ParagraphStyle(
        'IATH', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=6.6, leading=8,
        alignment=1, textColor=colors.white
    )
    td_style = ParagraphStyle(
        'IATD', parent=styles['Normal'],
        fontName='Helvetica', fontSize=6.8, leading=8.2,
        alignment=1, textColor=colors.HexColor('#0f172a')
    )
    td_bold_style = ParagraphStyle(
        'IATDBold', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=7.0, leading=8.5,
        alignment=1, textColor=colors.HexColor('#1e3a8a')
    )
    td_left_style = ParagraphStyle(
        'IATDLeft', parent=styles['Normal'],
        fontName='Helvetica', fontSize=6.6, leading=8,
        alignment=0, textColor=colors.HexColor('#0f172a')
    )

    elements = []
    elements.append(Paragraph("Internal Assessment (IA) Evaluation & Grade Ledger", title_style))
    elements.append(Paragraph(
        f"{report_data['college_name_line']} &nbsp;•&nbsp; Consolidated Attendance, Class Test, Assignment &amp; Moderation Statement",
        subtitle_style
    ))

    meta_rows = [
        [
            Paragraph("COURSE / PROGRAMME", meta_label_style),
            Paragraph(report_data['course_display'], meta_val_style),
            Paragraph("SEMESTER & SCHEME", meta_label_style),
            Paragraph(f"{report_data['part_sem_display']} ({report_data['exam_type']})", meta_val_style),
        ],
        [
            Paragraph("SORTING ORDER", meta_label_style),
            Paragraph(report_data['section_sorting'], meta_val_style),
            Paragraph("GENERATED ON", meta_label_style),
            Paragraph(report_data['printing_date'], meta_val_style),
        ],
    ]
    meta_table = Table(meta_rows, colWidths=[110, 310, 110, 276])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 8))

    headers = [
        Paragraph("#", th_style),
        Paragraph("Reg. No", th_style),
        Paragraph("Roll No", th_style),
        Paragraph("Student Name", th_style),
        Paragraph("Sec.", th_style),
        Paragraph("Code", th_style),
        Paragraph("Subject Title", th_style),
        Paragraph("Max<br/>IA", th_style),
        Paragraph("Held", th_style),
        Paragraph("Attd.", th_style),
        Paragraph("Attd.<br/>%", th_style),
        Paragraph("Bft.", th_style),
        Paragraph("Attd.<br/>Cap", th_style),
        Paragraph("Attd.<br/>Score", th_style),
        Paragraph("Class<br/>Test", th_style),
        Paragraph("Assign.", th_style),
        Paragraph("Mod.", th_style),
        Paragraph("Total<br/>IA", th_style),
        Paragraph("Status", th_style),
        Paragraph("Verified", th_style),
    ]

    # Landscape A4 usable width: 806pt total
    col_widths = [20, 56, 44, 82, 34, 48, 118, 26, 26, 26, 34, 18, 26, 32, 30, 30, 26, 32, 46, 52]

    table_data = [headers]
    for r in report_data['rows']:
        table_data.append([
            Paragraph(str(r['sr_no']), td_style),
            Paragraph(str(r['univ_rollno']), td_style),
            Paragraph(str(r['college_rollno']), td_style),
            Paragraph(r['name'], td_left_style),
            Paragraph(str(r['class_section']), td_style),
            Paragraph(str(r['paper_id']), td_style),
            Paragraph(r['paper_name'], td_left_style),
            Paragraph(str(r['max_ia_marks']), td_style),
            Paragraph(str(r['lect_deliver']), td_style),
            Paragraph(str(r['lect_attd']), td_style),
            Paragraph(f"{r['pct_attd']}%", td_style),
            Paragraph(str(r['benefit_dash']), td_style),
            Paragraph(str(r['attd_mks']), td_style),
            Paragraph(str(r['final_marks_attd']), td_style),
            Paragraph(str(r['marks_ct']) if r['marks_ct'] else '—', td_style),
            Paragraph(str(r['marks_assi']) if r['marks_assi'] else '—', td_style),
            Paragraph(str(r['mod_marks']) if r['mod_marks'] else '—', td_style),
            Paragraph(str(r['te_ia']), td_bold_style),
            Paragraph(str(r['ia_confirm_status']), td_style),
            Paragraph(str(r['ia_confirm_date']), td_style),
        ])

    if not report_data['rows']:
        table_data.append([Paragraph("No enrolled student records match the selected filters.", td_style)] + [""] * 19)

    data_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 2.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2.5),
    ]
    for r_idx in range(1, len(table_data)):
        if r_idx % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#f8fafc')))
    if report_data['rows']:
        style_cmds.append(('BACKGROUND', (17, 1), (17, -1), colors.HexColor('#eef2ff')))
    else:
        style_cmds.append(('SPAN', (0, 1), (19, 1)))
    data_table.setStyle(TableStyle(style_cmds))
    elements.append(data_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def export_final_ia_report_excel(report_data):
    """
    Export the Internal Assessment Evaluation & Grade Ledger as a styled Excel (.xlsx) workbook.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "IA Evaluation Ledger"

    # Branded Navy Banner Title block
    ws.merge_cells("A1:T1")
    ws["A1"] = "Internal Assessment (IA) Evaluation & Grade Ledger"
    ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:T2")
    ws["A2"] = f"{report_data['college_name_line']}  •  Consolidated Attendance, C.T., Assignment & Moderation Statement"
    ws["A2"].font = Font(name="Calibri", size=10, italic=True, color="334155")
    ws["A2"].fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 20

    meta_rows = [
        ("Institution", report_data['college_name_line'], "Exam Scheme", report_data['exam_type']),
        ("Course / Programme", f"{report_data['course_display']} ({report_data['part_sem_display']})", "Sort Order", report_data['section_sorting']),
        ("Generated On", report_data['printing_date'], "Total Entries", str(report_data['summary']['total_rows'])),
    ]
    row_idx = 4
    for l1, v1, l2, v2 in meta_rows:
        ws.cell(row=row_idx, column=1, value=l1).font = Font(bold=True, size=9.5, color="475569")
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=3)
        ws.cell(row=row_idx, column=4, value=v1).font = Font(bold=True, size=10, color="0F172A")
        ws.merge_cells(start_row=row_idx, start_column=4, end_row=row_idx, end_column=11)
        ws.cell(row=row_idx, column=12, value=l2).font = Font(bold=True, size=9.5, color="475569")
        ws.merge_cells(start_row=row_idx, start_column=12, end_row=row_idx, end_column=14)
        ws.cell(row=row_idx, column=15, value=v2).font = Font(bold=True, size=10, color="0F172A")
        ws.merge_cells(start_row=row_idx, start_column=15, end_row=row_idx, end_column=20)
        row_idx += 1

    header_row = row_idx + 1
    headers = [
        "#", "Reg. No", "Roll No", "Student Name", "Section", "Paper Code", "Subject Title",
        "Max IA", "Held", "Attd.", "Attd. %", "Benefit", "Attd. Cap",
        "Attd. Score", "Class Test", "Assignment", "Moderation", "Total IA",
        "Status", "Verified On"
    ]

    slate_border = Border(
        left=Side(style='thin', color='CBD5E1'), right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'), bottom=Side(style='thin', color='CBD5E1')
    )
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    total_fill = PatternFill(start_color="EEF2FF", end_color="EEF2FF", fill_type="solid")

    for col_num, h in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col_num, value=h)
        cell.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = slate_border
    ws.row_dimensions[header_row].height = 28

    for idx, r in enumerate(report_data['rows'], start=header_row + 1):
        row_vals = [
            r['sr_no'], r['univ_rollno'], r['college_rollno'], r['name'], r['class_section'],
            r['paper_id'], r['paper_name'], r['max_ia_marks'], r['lect_deliver'],
            r['lect_attd'], f"{r['pct_attd']}%", r['benefit_dash'], r['attd_mks'],
            r['final_marks_attd'], r['marks_ct'] or '—', r['marks_assi'] or '—',
            r['mod_marks'] or '—', r['te_ia'], r['ia_confirm_status'], r['ia_confirm_date']
        ]
        is_even = (idx - header_row) % 2 == 0
        for col_num, val in enumerate(row_vals, 1):
            cell = ws.cell(row=idx, column=col_num, value=val)
            cell.font = Font(name="Calibri", size=10, bold=(col_num == 18), color="1E3A8A" if col_num == 18 else "0F172A")
            cell.border = slate_border
            if col_num == 18:
                cell.fill = total_fill
            elif is_even:
                cell.fill = zebra_fill
            if col_num in (4, 7):
                cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="center", vertical="center")

    col_widths = [6, 15, 13, 24, 11, 13, 34, 9, 8, 8, 10, 9, 10, 11, 11, 11, 11, 10, 12, 14]
    for i, w in enumerate(col_widths, 1):
        col_letter = ws.cell(row=header_row, column=i).column_letter
        ws.column_dimensions[col_letter].width = w

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out.getvalue()
