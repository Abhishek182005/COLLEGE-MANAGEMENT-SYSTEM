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

    students = list(students_qs)
    student_ids = [s.id for s in students]

    # Determine allocated subjects if filtering to faculty's subjects
    faculty_subject_ids = None
    if my_subjects_only and user and hasattr(user, 'faculty_profile'):
        faculty_subject_ids = set(
            SubjectAllocation.objects.filter(
                faculty=user.faculty_profile, is_active=True
            ).values_list('subject_id', flat=True)
        )

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
            confirm_status_disp = 'Confirmed' if confirm_status_raw == 'CONFIRMED' else ''
            confirm_date_disp = saved.confirm_date.strftime('%d %b %Y') if (saved and saved.confirm_date) else ''

            rows.append({
                'sr_no': sr_no,
                'student_id': st.id,
                'subject_id': subj.id,
                'univ_rollno': st.registration_number,
                'college_rollno': st.roll_number,
                'name': st.full_name.upper(),
                'paper_id': subj.code,
                'paper_name': subj.name.upper(),
                'max_ia_marks': _fmt_num(max_ia),
                'max_ia_raw': str(max_ia),
                'lect_deliver': lect_held,
                'lect_attd': '' if (lect_held == 0 and lect_attd_val == 0) else lect_attd_val,
                'pct_attd': f"{pct_attd:.2f}",
                'attd_mks': f"{float(attd_max):.1f}",
                'attd_mks_raw': str(attd_max),
                'benefit_dash': str(att_data['bft']) if att_data['bft'] > 0 else '',
                'final_marks_attd': _fmt_num(final_attd_marks),
                'final_attd_raw': str(saved.final_attd_marks) if (saved and saved.final_attd_marks is not None) else '',
                'marks_ct': _fmt_num(marks_ct_val),
                'marks_ct_raw': str(marks_ct_val) if marks_ct_val is not None else '',
                'marks_assi': _fmt_num(marks_assi_val),
                'marks_assi_raw': str(marks_assi_val) if marks_assi_val is not None else '',
                'mod_marks': _fmt_num(mod_val),
                'mod_raw': str(mod_val) if mod_val is not None else '',
                'te_ia': _fmt_num(te_ia_val),
                'class_section': st.batch.name if st.batch else 'NILL',
                'ia_confirm_status': confirm_status_disp,
                'ia_confirm_date': confirm_date_disp,
                'is_confirmed': confirm_status_raw == 'CONFIRMED',
            })
            sr_no += 1

    # Header Metadata strings matching screenshot
    college_name_line = f"({college_code}) {college_name}"
    if selected_course:
        course_display = f"{selected_course.code} -||- {selected_course.name.upper()}"
    else:
        course_display = "ALL ENROLLED COURSES"

    if selected_semester:
        sem_num = selected_semester.semester_number
        part_num = (sem_num + 1) // 2
        part_sem_display = f"Part: {ROMAN_MAP.get(part_num, part_num)}   Sem: {ROMAN_MAP.get(sem_num, sem_num)}"
    else:
        part_sem_display = "All Semesters"

    return {
        'college_name_line': college_name_line,
        'exam_type': exam_type or 'CBCS_NEP',
        'course_display': course_display,
        'part_sem_display': part_sem_display,
        'section_sorting': 'YES' if section_sorting == 'YES' else 'NO',
        'printing_date': timezone.localtime().strftime('%d %b %Y %H:%M:%S'),
        'rows': rows,
        'selected_course': selected_course,
        'selected_semester': selected_semester,
        'selected_subject': selected_subject,
        'selected_batch': selected_batch,
        'threshold': threshold,
    }


def generate_final_ia_report_pdf(report_data):
    """
    Generate landscape A4 PDF matching the official university Final IA Report (Course Wise) format.
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
        fontName='Helvetica-Bold', fontSize=14, leading=16,
        textColor=colors.HexColor('#8b0000'), alignment=1, spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        'IASubtitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9.5, leading=12,
        textColor=colors.HexColor('#006400'), alignment=1, spaceAfter=6
    )
    right_label_style = ParagraphStyle(
        'IARight', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9, alignment=2
    )
    meta_label_style = ParagraphStyle(
        'IAMetaLabel', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.5, leading=11
    )
    meta_val_style = ParagraphStyle(
        'IAMetaVal', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8.5, leading=11
    )
    th_style = ParagraphStyle(
        'IATH', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=6.8, leading=8,
        alignment=1, textColor=colors.black
    )
    td_style = ParagraphStyle(
        'IATD', parent=styles['Normal'],
        fontName='Helvetica', fontSize=6.8, leading=8.2,
        alignment=1, textColor=colors.black
    )
    td_left_style = ParagraphStyle(
        'IATDLeft', parent=styles['Normal'],
        fontName='Helvetica', fontSize=6.5, leading=8,
        alignment=0, textColor=colors.black
    )

    elements = []
    elements.append(Paragraph("Final IA Report (Course Wise)", title_style))
    elements.append(Paragraph("(Report is Valid After Final Attendance & IA Calculation)", subtitle_style))
    elements.append(Paragraph("COLLEGE", right_label_style))
    elements.append(Spacer(1, 2))

    meta_rows = [
        [Paragraph("College Name", meta_label_style), Paragraph(report_data['college_name_line'], meta_val_style)],
        [Paragraph("Exam Type", meta_label_style), Paragraph(report_data['exam_type'], meta_val_style)],
        [Paragraph("Course Code and Name", meta_label_style), Paragraph(report_data['course_display'], meta_val_style)],
        [Paragraph("", meta_label_style), Paragraph(report_data['part_sem_display'], meta_val_style)],
        [Paragraph("Class Section Wise Sorting", meta_label_style), Paragraph(report_data['section_sorting'], meta_val_style)],
        [Paragraph("Printing Date", meta_label_style), Paragraph(report_data['printing_date'], meta_val_style)],
    ]
    meta_table = Table(meta_rows, colWidths=[165, 635])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 8))

    headers = [
        Paragraph("Sr.<br/>No.", th_style),
        Paragraph("Univ. Rollno", th_style),
        Paragraph("College<br/>Rollno", th_style),
        Paragraph("Name", th_style),
        Paragraph("Paper_Id", th_style),
        Paragraph("Paper Name", th_style),
        Paragraph("Max<br/>IA<br/>Marks", th_style),
        Paragraph("Lect.<br/>Deliver", th_style),
        Paragraph("Lect.<br/>Attd.", th_style),
        Paragraph("%<br/>Attd.", th_style),
        Paragraph("Attd.<br/>MKS", th_style),
        Paragraph("-", th_style),
        Paragraph("Final<br/>Marks<br/>Attd.", th_style),
        Paragraph("Marks<br/>C.T.", th_style),
        Paragraph("Marks<br/>Assi.", th_style),
        Paragraph("Mod.", th_style),
        Paragraph("TE_IA", th_style),
        Paragraph("Class<br/>Section", th_style),
        Paragraph("IA<br/>Confirm<br/>Status", th_style),
        Paragraph("IA Confirm<br/>Date", th_style),
    ]

    # Landscape A4 width ~ 842pt - 36pt margins = 806pt total
    col_widths = [20, 56, 44, 72, 48, 108, 28, 30, 28, 34, 28, 12, 30, 30, 30, 24, 28, 42, 42, 48]

    table_data = [headers]
    for r in report_data['rows']:
        table_data.append([
            Paragraph(str(r['sr_no']), td_style),
            Paragraph(str(r['univ_rollno']), td_style),
            Paragraph(str(r['college_rollno']), td_style),
            Paragraph(r['name'], td_left_style),
            Paragraph(str(r['paper_id']), td_style),
            Paragraph(r['paper_name'], td_left_style),
            Paragraph(str(r['max_ia_marks']), td_style),
            Paragraph(str(r['lect_deliver']), td_style),
            Paragraph(str(r['lect_attd']), td_style),
            Paragraph(str(r['pct_attd']), td_style),
            Paragraph(str(r['attd_mks']), td_style),
            Paragraph(str(r['benefit_dash']), td_style),
            Paragraph(str(r['final_marks_attd']), td_style),
            Paragraph(str(r['marks_ct']), td_style),
            Paragraph(str(r['marks_assi']), td_style),
            Paragraph(str(r['mod_marks']), td_style),
            Paragraph(str(r['te_ia']), td_style),
            Paragraph(str(r['class_section']), td_style),
            Paragraph(str(r['ia_confirm_status']), td_style),
            Paragraph(str(r['ia_confirm_date']), td_style),
        ])

    if not report_data['rows']:
        table_data.append([Paragraph("No enrolled student records match the selected filters.", td_style)] + [""] * 19)

    data_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]
    if not report_data['rows']:
        style_cmds.append(('SPAN', (0, 1), (19, 1)))
    data_table.setStyle(TableStyle(style_cmds))
    elements.append(data_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def export_final_ia_report_excel(report_data):
    """
    Export the Final IA Report (Course Wise) table as a formatted Excel (.xlsx) workbook.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Final IA Report"

    # Title block
    ws.merge_cells("A1:T1")
    ws["A1"] = "Final IA Report (Course Wise)"
    ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="8B0000")
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:T2")
    ws["A2"] = "(Report is Valid After Final Attendance & IA Calculation)"
    ws["A2"].font = Font(name="Calibri", size=10, bold=True, color="006400")
    ws["A2"].alignment = Alignment(horizontal="center")

    meta_rows = [
        ("College Name", report_data['college_name_line']),
        ("Exam Type", report_data['exam_type']),
        ("Course Code and Name", f"{report_data['course_display']} ({report_data['part_sem_display']})"),
        ("Class Section Wise Sorting", report_data['section_sorting']),
        ("Printing Date", report_data['printing_date']),
    ]
    row_idx = 4
    for label, val in meta_rows:
        ws.cell(row=row_idx, column=1, value=label).font = Font(bold=True, size=10)
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=3)
        ws.cell(row=row_idx, column=4, value=val).font = Font(bold=True, size=10)
        ws.merge_cells(start_row=row_idx, start_column=4, end_row=row_idx, end_column=10)
        row_idx += 1

    header_row = row_idx + 1
    headers = [
        "Sr. No.", "Univ. Rollno", "College Rollno", "Name", "Paper_Id", "Paper Name",
        "Max IA Marks", "Lect. Deliver", "Lect. Attd.", "% Attd.", "Attd. MKS", "-",
        "Final Marks Attd.", "Marks C.T.", "Marks Assi.", "Mod.", "TE_IA",
        "Class Section", "IA Confirm Status", "IA Confirm Date"
    ]

    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    header_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    for col_num, h in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col_num, value=h)
        cell.font = Font(name="Calibri", size=10, bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws.row_dimensions[header_row].height = 28

    for idx, r in enumerate(report_data['rows'], start=header_row + 1):
        row_vals = [
            r['sr_no'], r['univ_rollno'], r['college_rollno'], r['name'],
            r['paper_id'], r['paper_name'], r['max_ia_marks'], r['lect_deliver'],
            r['lect_attd'], r['pct_attd'], r['attd_mks'], r['benefit_dash'],
            r['final_marks_attd'], r['marks_ct'], r['marks_assi'], r['mod_marks'],
            r['te_ia'], r['class_section'], r['ia_confirm_status'], r['ia_confirm_date']
        ]
        for col_num, val in enumerate(row_vals, 1):
            cell = ws.cell(row=idx, column=col_num, value=val)
            cell.font = Font(name="Calibri", size=10)
            cell.border = thin_border
            if col_num in (4, 6):
                cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="center", vertical="center")

    col_widths = [7, 15, 13, 22, 13, 34, 10, 10, 10, 10, 10, 5, 12, 10, 10, 8, 9, 13, 14, 14]
    for i, w in enumerate(col_widths, 1):
        col_letter = ws.cell(row=header_row, column=i).column_letter
        ws.column_dimensions[col_letter].width = w

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out.getvalue()
