from django.conf import settings
from django.db.models import Q
from .models import CollegeSetting


def user_role_context(request):
    try:
        college_obj = CollegeSetting.get_settings()
        college_name = college_obj.name
        college_code = college_obj.college_code
        attendance_threshold = college_obj.attendance_threshold
    except Exception:
        college_obj = None
        college_name = getattr(settings, 'COLLEGE_NAME', 'CampusConnect Institute of Technology')
        college_code = getattr(settings, 'COLLEGE_CODE', 'CCIT-092')
        attendance_threshold = getattr(settings, 'ATTENDANCE_SHORTAGE_THRESHOLD', 75)

    context = {
        'college_settings': college_obj,
        'COLLEGE_NAME': college_name,
        'COLLEGE_CODE': college_code,
        'attendance_threshold': attendance_threshold,
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
                        Q(audience_type='ALL') |
                        Q(audience_type='STUDENTS_ONLY') |
                        Q(audience_type='DEPARTMENT', department=student.department) |
                        Q(audience_type='SEMESTER', semester=student.current_semester) |
                        Q(audience_type='BATCH', batch=student.batch)
                    )
            elif context['is_faculty']:
                faculty = getattr(request.user, 'faculty_profile', None)
                if faculty:
                    notices_qs = notices_qs.filter(
                        Q(audience_type='ALL') |
                        Q(audience_type='FACULTY_ONLY') |
                        Q(audience_type='DEPARTMENT', department=faculty.department)
                    )
            context['unread_notices_count'] = notices_qs.count()
        except Exception:
            context['unread_notices_count'] = 0

    return context
