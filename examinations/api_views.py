from decimal import Decimal
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import AssessmentComponent, Marks
from faculty.models import Faculty
from reports.utils import log_audit


class BulkMarksEntryAPIView(APIView):
    """
    Allows faculty to record or update marks for all enrolled students in a single request.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not (request.user.is_faculty_role or request.user.is_admin_role):
            return Response({'error': 'Faculty permissions required.'}, status=status.HTTP_403_FORBIDDEN)

        component_id = request.data.get('component_id')
        marks_records = request.data.get('records', [])  # [{'student_id': 1, 'marks_obtained': 45.5, 'remarks': ''}]

        if not component_id:
            return Response({'error': 'component_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            component = AssessmentComponent.objects.get(id=component_id)
        except AssessmentComponent.DoesNotExist:
            return Response({'error': 'Assessment component not found.'}, status=status.HTTP_404_NOT_FOUND)

        faculty = getattr(request.user, 'faculty_profile', None)

        saved_count = 0
        with transaction.atomic():
            for rec in marks_records:
                student_id = rec.get('student_id')
                marks_val = Decimal(str(rec.get('marks_obtained', 0)))
                remarks = rec.get('remarks', '')

                if marks_val > component.max_marks:
                    return Response({
                        'error': f"Marks ({marks_val}) cannot exceed maximum allowed marks ({component.max_marks})."
                    }, status=status.HTTP_400_BAD_REQUEST)

                marks_obj, created = Marks.objects.update_or_create(
                    assessment_component=component,
                    student_id=student_id,
                    defaults={
                        'marks_obtained': marks_val,
                        'remarks': remarks,
                        'graded_by': faculty
                    }
                )
                saved_count += 1

            log_audit(
                request=request,
                action="MARKS_RECORDED",
                entity_type="AssessmentComponent",
                entity_id=component.id,
                details=f"Marks entered/updated for {saved_count} students in {component.examination.name} - {component.subject.code} ({component.title})."
            )

        return Response({
            'message': f"Successfully recorded marks for {saved_count} students.",
            'saved_count': saved_count
        }, status=status.HTTP_200_OK)
