from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView
from django.http import HttpResponse, HttpResponseForbidden
from .models import Examination, AssessmentComponent, Marks
from academics.models import AcademicSession, Subject, Semester, SubjectAllocation
from students.models import Student
from faculty.models import Faculty
from accounts.permissions import role_required, FacultyRequiredMixin, StudentRequiredMixin
from reports.utils import generate_marksheet_pdf, log_audit


def _faculty_allocated_subject_ids(user):
    """Return set of active Subject IDs allocated to the given faculty user."""
    faculty = getattr(user, 'faculty_profile', None)
    if not faculty:
        return set()
    return set(
        SubjectAllocation.objects.filter(faculty=faculty, is_active=True)
        .values_list('subject_id', flat=True)
    )


class ExaminationListView(LoginRequiredMixin, ListView):
    model = Examination
    template_name = 'examinations/exam_list.html'
    context_object_name = 'examinations'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        is_restricted_faculty = user.is_faculty_role and not user.is_admin_role
        allowed_subj_ids = _faculty_allocated_subject_ids(user) if is_restricted_faculty else None

        filtered_exams = []
        for ex in ctx['examinations']:
            comps_qs = ex.components.select_related('subject', 'subject__semester__course')
            if is_restricted_faculty:
                comps_qs = comps_qs.filter(subject_id__in=allowed_subj_ids)
                ex.visible_components = list(comps_qs)
                if ex.visible_components:
                    filtered_exams.append(ex)
            else:
                ex.visible_components = list(comps_qs)
                filtered_exams.append(ex)

        ctx['examinations'] = filtered_exams
        ctx['is_restricted_faculty'] = is_restricted_faculty
        return ctx


@login_required
@role_required('ADMIN')
def exam_create_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        session_id = request.POST.get('academic_session')
        exam_type = request.POST.get('exam_type')
        start = request.POST.get('start_date')
        end = request.POST.get('end_date')
        is_published = request.POST.get('is_published') == 'on'

        exam = Examination.objects.create(
            name=name,
            academic_session_id=session_id,
            exam_type=exam_type,
            start_date=start,
            end_date=end,
            is_published=is_published
        )
        log_audit(request, "EXAM_CREATED", "Examination", exam.id, f"Created {name}")
        messages.success(request, f"Examination '{name}' created successfully.")
        return redirect('examination_list')

    context = {
        'sessions': AcademicSession.objects.all(),
        'exam_types': Examination.EXAM_TYPES,
    }
    return render(request, 'examinations/exam_form.html', context)


@login_required
@role_required('ADMIN')
def toggle_exam_publish(request, pk):
    exam = get_object_or_404(Examination, pk=pk)
    exam.is_published = not exam.is_published
    exam.save()
    status_str = "published" if exam.is_published else "unpublished"
    log_audit(request, "EXAM_PUBLISH_TOGGLE", "Examination", exam.id, f"Examination {exam.name} was {status_str}.")
    messages.success(request, f"Examination '{exam.name}' has been {status_str}.")
    return redirect('examination_list')


@login_required
@role_required('FACULTY', 'ADMIN')
def marks_entry_view(request, component_id):
    """Faculty entry screen for student assessment marks with instant grade generation."""
    component = get_object_or_404(AssessmentComponent.objects.select_related('subject', 'subject__semester__course'), id=component_id)
    subject = component.subject

    if request.user.is_faculty_role and not request.user.is_admin_role:
        if component.subject_id not in _faculty_allocated_subject_ids(request.user):
            return HttpResponseForbidden(
                "Access denied: You can only view or enter marks for courses and subjects assigned to you."
            )

    students = list(Student.objects.filter(current_semester=subject.semester, is_archived=False).select_related('user', 'batch'))
    valid_student_ids = {s.id for s in students}

    # Existing marks mapping
    existing_marks = {m.student_id: m for m in Marks.objects.filter(assessment_component=component)}

    student_rows = []
    for s in students:
        rec = existing_marks.get(s.id)
        student_rows.append({
            'student': s,
            'marks_obtained': rec.marks_obtained if rec else '',
            'grade': rec.grade if rec else '',
            'remarks': rec.remarks or '' if rec else ''
        })

    if request.method == 'POST':
        faculty = getattr(request.user, 'faculty_profile', None)
        saved_count = 0

        for key, val in request.POST.items():
            if key.startswith('marks_') and val.strip():
                try:
                    st_id = int(key.replace('marks_', ''))
                except ValueError:
                    continue
                if st_id not in valid_student_ids:
                    continue
                remarks = request.POST.get(f'remarks_{st_id}', '')
                marks_val = Decimal(val.strip())

                if marks_val < 0 or marks_val > component.max_marks:
                    messages.error(request, f"Error: Marks ({marks_val}) must be between 0 and {component.max_marks}.")
                    continue

                Marks.objects.update_or_create(
                    assessment_component=component,
                    student_id=st_id,
                    defaults={
                        'marks_obtained': marks_val,
                        'remarks': remarks,
                        'graded_by': faculty
                    }
                )
                saved_count += 1

        log_audit(
            request=request,
            action="MARKS_ENTRY_SUBMITTED",
            entity_type="AssessmentComponent",
            entity_id=component.id,
            details=f"Marks entered/updated for {saved_count} students in {component.examination.name} - {component.subject.code}."
        )
        messages.success(request, f"Recorded marks for {saved_count} students successfully!")
        return redirect('marks_entry', component_id=component.id)

    context = {
        'component': component,
        'subject': subject,
        'student_rows': student_rows,
    }
    return render(request, 'examinations/marks_entry.html', context)


@login_required
def student_results_view(request):
    """Results screen for students with download button for ReportLab PDF marksheet."""
    student = None
    if request.user.is_student_role and hasattr(request.user, 'student_profile'):
        student = request.user.student_profile
    elif request.GET.get('student_id'):
        student = get_object_or_404(Student, id=request.GET.get('student_id'))

    if not student:
        messages.error(request, "Student profile not found.")
        return redirect('dashboard_redirect')

    # Published examinations
    exams = Examination.objects.filter(is_published=True).order_by('-start_date')
    selected_exam_id = request.GET.get('exam_id')
    selected_exam = None

    results = []
    if selected_exam_id:
        selected_exam = get_object_or_404(Examination, id=selected_exam_id, is_published=True)
    elif exams.exists():
        selected_exam = exams.first()

    if selected_exam:
        components = AssessmentComponent.objects.filter(
            examination=selected_exam,
            subject__semester=student.current_semester
        ).select_related('subject')
        if request.user.is_faculty_role and not request.user.is_admin_role:
            components = components.filter(subject_id__in=_faculty_allocated_subject_ids(request.user))

        marks_map = {m.assessment_component_id: m for m in Marks.objects.filter(student=student, assessment_component__in=components)}

        for c in components:
            m = marks_map.get(c.id)
            results.append({
                'component': c,
                'marks': m.marks_obtained if m else None,
                'grade': m.grade if m else 'N/A',
                'is_pass': m.marks_obtained >= c.pass_marks if m else False,
            })

    context = {
        'student': student,
        'exams': exams,
        'selected_exam': selected_exam,
        'results': results,
    }
    return render(request, 'examinations/student_results.html', context)


@login_required
def download_marksheet_pdf_view(request, exam_id):
    if request.user.is_student_role:
        messages.info(request, "Marksheet PDF download is disabled for student accounts.")
        return redirect('student_results')
    examination = get_object_or_404(Examination, id=exam_id)
    student = None
    if request.user.is_student_role and hasattr(request.user, 'student_profile'):
        student = request.user.student_profile
    elif request.GET.get('student_id') and (request.user.is_admin_role or request.user.is_faculty_role):
        student = get_object_or_404(Student, id=request.GET.get('student_id'))

    if not student:
        messages.error(request, "Unauthorized access to transcript.")
        return redirect('dashboard_redirect')

    if request.user.is_faculty_role and not request.user.is_admin_role:
        allowed_subj_ids = _faculty_allocated_subject_ids(request.user)
        if not student.current_semester or not Subject.objects.filter(
            semester=student.current_semester, id__in=allowed_subj_ids
        ).exists():
            return HttpResponseForbidden(
                "Access denied: You can only view transcripts for students enrolled in your assigned subjects."
            )

    pdf_bytes = generate_marksheet_pdf(student, examination)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Marksheet_{student.roll_number}_{examination.id}.pdf"'
    return response

@login_required
@role_required('ADMIN')
def exam_delete_view(request, pk):
    exam = get_object_or_404(Examination, pk=pk)
    if request.method == 'POST':
        name = exam.name
        exam_id = exam.id
        exam.delete()
        log_audit(request, "EXAM_DELETED", "Examination", exam_id, f"Deleted examination '{name}'.")
        messages.success(request, f"Examination '{name}' deleted successfully.")
        return redirect('examination_list')
    return render(request, 'academics/confirm_delete.html', {'object': exam, 'type': 'Examination', 'cancel_url': 'examination_list'})
