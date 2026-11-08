import json
from django.shortcuts import render
from django.views.generic import TemplateView, ListView
from django.db.models import Count, Avg
from accounts.permissions import AdminRequiredMixin, FacultyRequiredMixin
from reports.models import AuditLog
from students.models import Student
from academics.models import Department, Subject
from attendance.models import AttendanceRecord, AttendanceSession
from examinations.models import Marks


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
