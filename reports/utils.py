import io
from decimal import Decimal
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reports.models import AuditLog


def get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_audit(request, action, entity_type, entity_id, details):
    """Utility to log system mutations for compliance and accountability."""
    user = request.user if request and request.user.is_authenticated else None
    ip = get_client_ip(request)
    AuditLog.objects.create(
        user=user,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details=details,
        ip_address=ip
    )


# ==========================================
# REPORTLAB PDF GENERATORS
# ==========================================

def generate_student_id_card_pdf(student):
    """Generates an official Student Identity Card PDF using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(300, 480),  # Standard ID card aspect ratio
        leftMargin=15,
        rightMargin=15,
        topMargin=15,
        bottomMargin=15
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CardTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        alignment=1,  # Center
        textColor=colors.HexColor('#1e3a8a')
    )
    subtitle_style = ParagraphStyle(
        'CardSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        alignment=1,
        textColor=colors.HexColor('#475569')
    )
    badge_style = ParagraphStyle(
        'CardBadge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        alignment=1,
        textColor=colors.white
    )
    label_style = ParagraphStyle(
        'CardLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#334155')
    )
    val_style = ParagraphStyle(
        'CardVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0f172a')
    )

    elements = []

    # Header Card
    college_name = getattr(settings, 'COLLEGE_NAME', 'CAMPUSCONNECT INSTITUTE')
    elements.append(Paragraph(college_name.upper(), title_style))
    elements.append(Paragraph("STUDENT IDENTITY CARD", subtitle_style))
    elements.append(Spacer(1, 8))

    # Badge Ribbon
    ribbon_data = [[Paragraph("STUDENT PASS", badge_style)]]
    ribbon_table = Table(ribbon_data, colWidths=[270], rowHeights=[18])
    ribbon_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2563eb')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(ribbon_table)
    elements.append(Spacer(1, 10))

    # Student Details
    info_data = [
        [Paragraph("Student Name:", label_style), Paragraph(student.full_name, val_style)],
        [Paragraph("Roll Number:", label_style), Paragraph(student.roll_number, val_style)],
        [Paragraph("Registration No:", label_style), Paragraph(student.registration_number, val_style)],
        [Paragraph("Department:", label_style), Paragraph(student.department.name, val_style)],
        [Paragraph("Course:", label_style), Paragraph(student.course.name, val_style)],
        [Paragraph("Semester / Batch:", label_style), Paragraph(f"Sem {student.current_semester.semester_number} ({student.batch.name})", val_style)],
        [Paragraph("Blood Group:", label_style), Paragraph(student.blood_group or "N/A", val_style)],
        [Paragraph("Emergency Contact:", label_style), Paragraph(student.guardian_phone or "N/A", val_style)],
    ]

    info_table = Table(info_data, colWidths=[90, 180])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 25))

    # Signature line
    sig_data = [
        [Paragraph("Student's Signature", subtitle_style), Paragraph("Principal / Authorized Signatory", subtitle_style)]
    ]
    sig_table = Table(sig_data, colWidths=[135, 135])
    sig_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 1, colors.HexColor('#94a3b8')),
        ('LINEABOVE', (1, 0), (1, 0), 1, colors.HexColor('#94a3b8')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generate_marksheet_pdf(student, examination):
    """Generates an official downloadable Grade Card / Marksheet PDF using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=1,
        textColor=colors.HexColor('#1e293b')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=14,
        alignment=1,
        textColor=colors.HexColor('#475569')
    )
    h3_style = ParagraphStyle(
        'DocH3',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0f172a')
    )
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1e293b')
    )
    body_normal = ParagraphStyle(
        'BodyNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )

    elements = []

    # Header
    college_name = getattr(settings, 'COLLEGE_NAME', 'CAMPUSCONNECT INSTITUTE OF TECHNOLOGY')
    elements.append(Paragraph(college_name.upper(), title_style))
    elements.append(Paragraph("OFFICIAL ACADEMIC TRANSCRIPT & MARKSHEET", subtitle_style))
    elements.append(Paragraph(f"{examination.name} • Academic Session: {examination.academic_session.name}", subtitle_style))
    elements.append(Spacer(1, 14))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=14))

    # Student metadata table
    meta_data = [
        [
            Paragraph("<b>Student Name:</b>", body_normal), Paragraph(student.full_name, body_bold),
            Paragraph("<b>Roll Number:</b>", body_normal), Paragraph(student.roll_number, body_bold),
        ],
        [
            Paragraph("<b>Registration No:</b>", body_normal), Paragraph(student.registration_number, body_normal),
            Paragraph("<b>Department:</b>", body_normal), Paragraph(student.department.name, body_normal),
        ],
        [
            Paragraph("<b>Course:</b>", body_normal), Paragraph(student.course.name, body_normal),
            Paragraph("<b>Semester:</b>", body_normal), Paragraph(f"Semester {student.current_semester.semester_number}", body_normal),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[100, 160, 100, 160])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 16))

    # Marks table
    from examinations.models import Marks, AssessmentComponent
    components = AssessmentComponent.objects.filter(examination=examination, subject__semester=student.current_semester)
    marks_records = {m.assessment_component_id: m for m in Marks.objects.filter(student=student, assessment_component__in=components)}

    marks_data = [
        [
            Paragraph("<b>Subject Code</b>", body_bold),
            Paragraph("<b>Subject Name</b>", body_bold),
            Paragraph("<b>Component</b>", body_bold),
            Paragraph("<b>Max Marks</b>", body_bold),
            Paragraph("<b>Pass Marks</b>", body_bold),
            Paragraph("<b>Obtained</b>", body_bold),
            Paragraph("<b>Grade</b>", body_bold),
            Paragraph("<b>Result</b>", body_bold),
        ]
    ]

    total_max = Decimal('0.0')
    total_obtained = Decimal('0.0')
    passed_all = True

    for comp in components:
        record = marks_records.get(comp.id)
        obt = record.marks_obtained if record else Decimal('0.0')
        grade = record.grade if record else 'F'
        is_pass = obt >= comp.pass_marks
        if not is_pass:
            passed_all = False

        total_max += comp.max_marks
        total_obtained += obt

        res_text = "PASS" if is_pass else "FAIL"
        res_color = "#16a34a" if is_pass else "#dc2626"
        res_p = Paragraph(f"<font color='{res_color}'><b>{res_text}</b></font>", body_normal)

        marks_data.append([
            Paragraph(comp.subject.code, body_normal),
            Paragraph(comp.subject.name, body_normal),
            Paragraph(comp.title, body_normal),
            Paragraph(str(comp.max_marks), body_normal),
            Paragraph(str(comp.pass_marks), body_normal),
            Paragraph(str(obt), body_bold),
            Paragraph(f"<b>{grade}</b>", body_bold),
            res_p,
        ])

    table = Table(marks_data, colWidths=[65, 145, 90, 55, 55, 55, 40, 50])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 14))

    # Summary box
    pct = round((total_obtained / total_max * 100), 2) if total_max > 0 else 0.0
    overall_status = "PASSED" if (passed_all and components.exists()) else "NEEDS RE-APPEAR"
    status_color = "#16a34a" if overall_status == "PASSED" else "#dc2626"

    summary_data = [
        [
            Paragraph(f"<b>Total Maximum Marks:</b> {total_max}", body_normal),
            Paragraph(f"<b>Total Marks Obtained:</b> {total_obtained}", body_bold),
            Paragraph(f"<b>Percentage:</b> {pct}%", body_bold),
            Paragraph(f"<b>Status:</b> <font color='{status_color}'><b>{overall_status}</b></font>", body_bold)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[130, 130, 130, 130])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e0e7ff')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#6366f1')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 40))

    # Signatures
    sig_data = [
        [
            Paragraph("Controller of Examinations", subtitle_style),
            Paragraph("Dean of Academic Affairs", subtitle_style),
            Paragraph("College Principal", subtitle_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[170, 170, 170])
    sig_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 1, colors.HexColor('#94a3b8')),
        ('LINEABOVE', (1, 0), (1, 0), 1, colors.HexColor('#94a3b8')),
        ('LINEABOVE', (2, 0), (2, 0), 1, colors.HexColor('#94a3b8')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ==========================================
# OPENPYXL EXCEL EXPORT / IMPORT
# ==========================================

def export_students_to_excel(students_queryset):
    """Exports list of students to formatted Excel spreadsheet."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Student Directory"

    # Header styling
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    headers = [
        "Roll No", "Registration No", "Full Name", "Email", "Phone",
        "Department", "Course", "Semester", "Batch", "Section", "Blood Group", "Status"
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    for s in students_queryset:
        status_text = "Archived" if s.is_archived else ("Active" if s.user.is_active else "Inactive")
        ws.append([
            s.roll_number,
            s.registration_number,
            s.full_name,
            s.email,
            s.phone or "-",
            s.department.code,
            s.course.code,
            s.current_semester.semester_number,
            s.batch.name,
            s.batch.section,
            s.blood_group or "-",
            status_text
        ])

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.border = thin_border

    # Adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def export_attendance_to_excel(session):
    """Exports attendance records for a specific session to Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance Session"

    # Title block
    ws["A1"] = f"CampusConnect - Attendance Report: {session.subject.name} ({session.subject.code})"
    ws["A1"].font = Font(size=14, bold=True, color="1E3A8A")
    ws["A2"] = f"Date: {session.date} | Slot: {session.lecture_slot} | Faculty: {session.faculty.full_name} | Batch: {session.batch.name if session.batch else 'All'}"
    ws["A2"].font = Font(size=10, italic=True)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")

    headers = ["Roll No", "Student Name", "Status", "Marking Method", "Remarks", "Timestamp"]
    ws.append([])  # empty line 3
    ws.append(headers)  # line 4

    for cell in ws[4]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for rec in session.records.select_related('student__user').all():
        ws.append([
            rec.student.roll_number,
            rec.student.full_name,
            rec.get_status_display(),
            rec.get_marked_via_display(),
            rec.remarks or "-",
            rec.marked_at.strftime("%Y-%m-%d %H:%M")
        ])

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def parse_and_import_students_excel(file_obj, department_default, course_default, semester_default, batch_default):
    """Parses an uploaded Excel file and imports student accounts."""
    from accounts.models import CustomUser
    from students.models import Student

    wb = load_workbook(file_obj)
    ws = wb.active
    created_count = 0
    errors = []

    # Expected columns: RollNo, RegNo, Username, Email, FirstName, LastName, Phone, BloodGroup
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or not row[0]:
            continue
        try:
            roll_no = str(row[0]).strip()
            reg_no = str(row[1]).strip() if len(row) > 1 and row[1] else f"REG-{roll_no}"
            username = str(row[2]).strip() if len(row) > 2 and row[2] else roll_no.lower()
            email = str(row[3]).strip() if len(row) > 3 and row[3] else f"{username}@campusconnect.edu"
            first_name = str(row[4]).strip() if len(row) > 4 and row[4] else "Student"
            last_name = str(row[5]).strip() if len(row) > 5 and row[5] else roll_no
            phone = str(row[6]).strip() if len(row) > 6 and row[6] else ""
            blood_group = str(row[7]).strip() if len(row) > 7 and row[7] else ""

            if CustomUser.objects.filter(username=username).exists():
                errors.append(f"Row {idx}: Username '{username}' already exists.")
                continue

            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password="Student@123",
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role=CustomUser.ROLE_STUDENT
            )

            Student.objects.create(
                user=user,
                roll_number=roll_no,
                registration_number=reg_no,
                department=department_default,
                course=course_default,
                current_semester=semester_default,
                batch=batch_default,
                blood_group=blood_group if blood_group in ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'] else None,
            )
            created_count += 1
        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")

    return created_count, errors
