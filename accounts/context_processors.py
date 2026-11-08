from django.conf import settings
from django.db.models import Q


def user_role_context(request):
    context = {
        'COLLEGE_NAME': getattr(settings, 'COLLEGE_NAME', 'CampusConnect Institute of Technology'),
        'COLLEGE_CODE': getattr(settings, 'COLLEGE_CODE', 'CCIT-092'),
        'user_role': 'GUEST',
        'is_admin': False,
        'is_faculty': False,
        'is_student': False,
        'unread_notices_count': 0,
    }

    if request.user.is_authenticated:
        role = getattr(request.user, 'role', None)
        context['user_role'] = role
        context['is_admin'] = request.user.is_admin_role
        context['is_faculty'] = request.user.is_faculty_role
        context['is_student'] = request.user.is_student_role

        try:
            from communication.models import Notice, NoticeRead
            read_ids = NoticeRead.objects.filter(user=request.user).values_list('notice_id', flat=True)
            notices_qs = Notice.objects.exclude(id__in=read_ids)
            if context['is_student']:
                student = getattr(request.user, 'student_profile', None)
                if student:
                    notices_qs = notices_qs.filter(
                        models.Q(audience_type='ALL') |
                        models.Q(audience_type='STUDENTS_ONLY') |
                        models.Q(audience_type='DEPARTMENT', department=student.department) |
                        models.Q(audience_type='SEMESTER', semester=student.current_semester) |
                        models.Q(audience_type='BATCH', batch=student.batch)
                    )
            elif context['is_faculty']:
                faculty = getattr(request.user, 'faculty_profile', None)
                if faculty:
                    notices_qs = notices_qs.filter(
                        models.Q(audience_type='ALL') |
                        models.Q(audience_type='FACULTY_ONLY') |
                        models.Q(audience_type='DEPARTMENT', department=faculty.department)
                    )
            context['unread_notices_count'] = notices_qs.count()
        except Exception:
            context['unread_notices_count'] = 0

    return context
