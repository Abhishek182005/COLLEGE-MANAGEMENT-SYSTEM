from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.utils import timezone
from .models import Assignment, Submission
from academics.models import Subject, Semester
from students.models import Student, Batch
from faculty.models import Faculty
from accounts.permissions import role_required, FacultyRequiredMixin
from reports.utils import log_audit


class AssignmentListView(ListView):
    model = Assignment
    template_name = 'assignments/assignment_list.html'
    context_object_name = 'assignments'
    paginate_by = 20

    def get_queryset(self):
        qs = Assignment.objects.select_related('subject', 'faculty__user', 'semester', 'batch')
        user = self.request.user
        if user.is_faculty_role and hasattr(user, 'faculty_profile'):
            qs = qs.filter(faculty=user.faculty_profile)
        elif user.is_student_role and hasattr(user, 'student_profile'):
            qs = qs.filter(semester=user.student_profile.current_semester)
        return qs.order_by('-due_date')


class AssignmentDetailView(DetailView):
    model = Assignment
    template_name = 'assignments/assignment_detail.html'
    context_object_name = 'assignment'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        assignment = self.object
        user = self.request.user

        if user.is_faculty_role or user.is_admin_role:
            ctx['submissions'] = assignment.submissions.select_related('student__user', 'student__batch').order_by('-submitted_at')
        elif user.is_student_role and hasattr(user, 'student_profile'):
            ctx['my_submission'] = assignment.submissions.filter(student=user.student_profile).first()

        return ctx


@login_required
@role_required('FACULTY', 'ADMIN')
def assignment_create_view(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        desc = request.POST.get('description')
        subj_id = request.POST.get('subject')
        batch_id = request.POST.get('batch')
        due = request.POST.get('due_date')
        max_score = request.POST.get('max_score', 100)
        attachment = request.FILES.get('attachment')

        subj = get_object_or_404(Subject, id=subj_id)
        faculty = getattr(request.user, 'faculty_profile', None)
        if not faculty and request.user.is_admin_role:
            alloc = subj.allocations.first()
            faculty = alloc.faculty if alloc else Faculty.objects.first()

        assign = Assignment.objects.create(
            title=title,
            description=desc,
            subject=subj,
            faculty=faculty,
            semester=subj.semester,
            batch_id=batch_id if batch_id else None,
            due_date=due,
            max_score=Decimal(str(max_score)),
            attachment=attachment
        )
        log_audit(request, "ASSIGNMENT_CREATED", "Assignment", assign.id, f"Created {title} for {subj.code}")
        messages.success(request, f"Assignment '{title}' published successfully.")
        return redirect('assignment_detail', pk=assign.pk)

    faculty = getattr(request.user, 'faculty_profile', None)
    if faculty:
        my_subjects = Subject.objects.filter(allocations__faculty=faculty)
    else:
        my_subjects = Subject.objects.all()

    context = {
        'subjects': my_subjects,
        'batches': Batch.objects.all(),
    }
    return render(request, 'assignments/assignment_form.html', context)


@login_required
@role_required('STUDENT')
def submit_assignment_view(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    student = getattr(request.user, 'student_profile', None)
    if not student:
        messages.error(request, "Student profile required.")
        return redirect('assignment_list')

    if request.method == 'POST' and request.FILES.get('submission_file'):
        file_obj = request.FILES['submission_file']
        notes = request.POST.get('student_notes', '')

        sub, created = Submission.objects.update_or_create(
            assignment=assignment,
            student=student,
            defaults={
                'submission_file': file_obj,
                'student_notes': notes,
                'submitted_at': timezone.now(),
                'status': 'PENDING'
            }
        )
        status_msg = "Late submission recorded" if sub.is_late else "Submitted on time"
        log_audit(request, "ASSIGNMENT_SUBMITTED", "Submission", sub.id, f"Student {student.roll_number} submitted '{assignment.title}'. {status_msg}")
        messages.success(request, f"Assignment submitted successfully! ({status_msg})")
        return redirect('assignment_detail', pk=assignment.pk)

    return redirect('assignment_detail', pk=assignment.pk)


@login_required
@role_required('FACULTY', 'ADMIN')
def grade_submission_view(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id)
    if request.method == 'POST':
        score = request.POST.get('marks_obtained')
        feedback = request.POST.get('faculty_feedback', '')

        if score is not None and score.strip():
            score_dec = Decimal(score.strip())
            if score_dec > submission.assignment.max_score:
                messages.error(request, f"Score cannot exceed max score of {submission.assignment.max_score}.")
                return redirect('assignment_detail', pk=submission.assignment.pk)

            submission.marks_obtained = score_dec
            submission.faculty_feedback = feedback
            submission.status = 'GRADED'
            submission.save()

            log_audit(
                request=request,
                action="SUBMISSION_GRADED",
                entity_type="Submission",
                entity_id=submission.id,
                details=f"Graded submission #{submission.id} for {submission.student.roll_number}. Score: {score_dec}/{submission.assignment.max_score}."
            )
            messages.success(request, f"Submission graded successfully ({score_dec}/{submission.assignment.max_score}).")

    return redirect('assignment_detail', pk=submission.assignment.pk)

@login_required
@role_required('FACULTY', 'ADMIN')
def assignment_delete_view(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    if request.method == 'POST':
        title = assignment.title
        assign_id = assignment.id
        assignment.delete()
        log_audit(request, "ASSIGNMENT_DELETED", "Assignment", assign_id, f"Deleted assignment '{title}'.")
        messages.success(request, f"Assignment '{title}' deleted successfully.")
        return redirect('assignment_list')
    return render(request, 'academics/confirm_delete.html', {'object': assignment, 'type': 'Assignment', 'cancel_url': 'assignment_list'})
