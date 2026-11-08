import io
import base64
import uuid
import qrcode
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import AttendanceSession, AttendanceRecord
from .serializers import AttendanceSessionSerializer, AttendanceRecordSerializer
from students.models import Student
from academics.models import Subject, Semester
from reports.utils import log_audit


class QuickMarkAttendanceAPIView(APIView):
    """
    Enables faculty to mark or update attendance for all students in a batch/subject in one request.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        session_id = data.get('session_id')
        subject_id = data.get('subject_id')
        semester_id = data.get('semester_id')
        batch_id = data.get('batch_id')
        date_val = data.get('date', timezone.now().date())
        slot = data.get('lecture_slot', '09:00 - 10:00')
        topic = data.get('topic_covered', '')
        records_data = data.get('records', [])  # [{'student_id': 1, 'status': 'PRESENT', 'remarks': ''}]
        is_backdated_edit = data.get('is_backdated_edit', False)
        amendment_reason = data.get('amendment_reason', '')

        if not request.user.is_faculty_role and not request.user.is_admin_role:
            return Response({'error': 'Faculty access required.'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            if session_id:
                session = AttendanceSession.objects.get(id=session_id)
                if topic:
                    session.topic_covered = topic
                    session.save()
            else:
                if not (subject_id and semester_id):
                    return Response({'error': 'subject_id and semester_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
                faculty = getattr(request.user, 'faculty_profile', None)
                if not faculty and request.user.is_admin_role:
                    # fallback to subject's first allocated faculty or admin
                    alloc = Subject.objects.get(id=subject_id).allocations.first()
                    faculty = alloc.faculty if alloc else None

                if not faculty:
                    return Response({'error': 'No faculty profile associated with user.'}, status=status.HTTP_400_BAD_REQUEST)

                session = AttendanceSession.objects.create(
                    subject_id=subject_id,
                    faculty=faculty,
                    semester_id=semester_id,
                    batch_id=batch_id if batch_id else None,
                    date=date_val,
                    lecture_slot=slot,
                    topic_covered=topic
                )

            changes_summary = []
            for item in records_data:
                st_id = item.get('student_id')
                new_status = item.get('status', 'PRESENT')
                remarks = item.get('remarks', '')

                record, created = AttendanceRecord.objects.get_or_create(
                    session=session,
                    student_id=st_id,
                    defaults={'status': new_status, 'remarks': remarks, 'marked_via': 'MANUAL'}
                )
                if not created:
                    old_status = record.status
                    if old_status != new_status or record.remarks != remarks:
                        changes_summary.append(f"Student #{st_id}: {old_status} -> {new_status}")
                        record.status = new_status
                        record.remarks = remarks
                        record.marked_via = 'MANUAL'
                        record.save()

            # If this was an amendment of historical session, record in AuditLog
            if changes_summary or is_backdated_edit:
                log_audit(
                    request=request,
                    action="ATTENDANCE_CORRECTION",
                    entity_type="AttendanceSession",
                    entity_id=session.id,
                    details=f"Attendance modified for {session.subject.code} on {session.date}. Reason: {amendment_reason or 'Faculty revision'}. Changes: {', '.join(changes_summary) or 'No changes'}"
                )

        return Response({
            'message': 'Attendance marked successfully.',
            'session_id': session.id,
            'total_marked': len(records_data),
            'attendance_percentage': session.attendance_percentage
        }, status=status.HTTP_200_OK)


class QRGenerateAPIView(APIView):
    """
    Generates a dynamic QR code with a 15-minute countdown token for a classroom session.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = AttendanceSession.objects.get(id=session_id)
        except AttendanceSession.DoesNotExist:
            return Response({'error': 'Attendance session not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not (request.user.is_admin_role or (hasattr(request.user, 'faculty_profile') and session.faculty == request.user.faculty_profile)):
            return Response({'error': 'Only the assigned faculty can generate the QR code.'}, status=status.HTTP_403_FORBIDDEN)

        # Generate new token valid for 15 minutes
        session.qr_token = str(uuid.uuid4())
        session.qr_expires_at = timezone.now() + timedelta(minutes=15)
        session.save()

        # Build QR code image in memory
        qr = qrcode.QRCode(version=1, box_size=10, border=3)
        qr_payload = f"CAMPUSCONNECT_ATTENDANCE:{session.qr_token}"
        qr.add_data(qr_payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1e3a8a", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        log_audit(
            request=request,
            action="QR_CODE_GENERATED",
            entity_type="AttendanceSession",
            entity_id=session.id,
            details=f"Dynamic QR code generated for {session.subject.code} session #{session.id}. Valid until {session.qr_expires_at.strftime('%H:%M:%S')}."
        )

        return Response({
            'session_id': session.id,
            'qr_token': session.qr_token,
            'qr_payload': qr_payload,
            'qr_base64': f"data:image/png;base64,{qr_base64}",
            'expires_at': session.qr_expires_at.isoformat(),
            'expires_in_seconds': 900
        })


class QRMarkAttendanceAPIView(APIView):
    """
    Allows a student to scan a QR code or submit the dynamic token to mark their own attendance.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_student_role:
            return Response({'error': 'Only registered students can mark QR attendance.'}, status=status.HTTP_403_FORBIDDEN)

        student = getattr(request.user, 'student_profile', None)
        if not student:
            return Response({'error': 'Student profile not found.'}, status=status.HTTP_400_BAD_REQUEST)

        token = request.data.get('token', '').strip()
        if token.startswith("CAMPUSCONNECT_ATTENDANCE:"):
            token = token.replace("CAMPUSCONNECT_ATTENDANCE:", "")

        if not token:
            return Response({'error': 'Token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = AttendanceSession.objects.get(qr_token=token)
        except AttendanceSession.DoesNotExist:
            return Response({'error': 'Invalid or expired QR code.'}, status=status.HTTP_400_BAD_REQUEST)

        if not session.is_qr_valid():
            return Response({'error': 'This QR code has expired. Please ask your faculty for a refreshed QR code.'}, status=status.HTTP_400_BAD_REQUEST)

        if session.is_locked:
            return Response({'error': 'This attendance session has been finalized and locked by faculty.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check eligibility: is student in same semester and batch?
        if student.current_semester != session.semester:
            return Response({'error': 'You are not enrolled in the semester for this session.'}, status=status.HTTP_400_BAD_REQUEST)

        if session.batch and student.batch != session.batch:
            return Response({'error': 'This lecture is restricted to a different batch section.'}, status=status.HTTP_400_BAD_REQUEST)

        # Mark attendance
        record, created = AttendanceRecord.objects.get_or_create(
            session=session,
            student=student,
            defaults={'status': 'PRESENT', 'marked_via': 'QR_CODE'}
        )
        if not created and record.status != 'PRESENT':
            record.status = 'PRESENT'
            record.marked_via = 'QR_CODE'
            record.save()

        return Response({
            'success': True,
            'message': f"Attendance successfully marked for {session.subject.name} ({session.subject.code})!",
            'subject': session.subject.name,
            'date': session.date,
            'slot': session.lecture_slot,
            'status': record.status,
            'marked_at': record.marked_at
        }, status=status.HTTP_200_OK)


class OfflineSyncAttendanceAPIView(APIView):
    """
    SmartProf-inspired feature: Synchronizes attendance captured offline in local storage.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_faculty_role and not request.user.is_admin_role:
            return Response({'error': 'Faculty access required.'}, status=status.HTTP_403_FORBIDDEN)

        synced_sessions = request.data.get('sessions', [])
        synced_count = 0
        errors = []

        with transaction.atomic():
            for item in synced_sessions:
                try:
                    subject_id = item.get('subject_id')
                    semester_id = item.get('semester_id')
                    batch_id = item.get('batch_id')
                    date_val = item.get('date')
                    slot = item.get('lecture_slot')
                    records = item.get('records', [])

                    faculty = getattr(request.user, 'faculty_profile', None)
                    if not faculty:
                        continue

                    session, _ = AttendanceSession.objects.get_or_create(
                        subject_id=subject_id,
                        faculty=faculty,
                        semester_id=semester_id,
                        batch_id=batch_id if batch_id else None,
                        date=date_val,
                        lecture_slot=slot
                    )

                    for rec in records:
                        AttendanceRecord.objects.update_or_create(
                            session=session,
                            student_id=rec.get('student_id'),
                            defaults={
                                'status': rec.get('status', 'PRESENT'),
                                'marked_via': 'OFFLINE_SYNC',
                                'remarks': rec.get('remarks', 'Synced from offline storage')
                            }
                        )
                    synced_count += 1
                except Exception as e:
                    errors.append(str(e))

            log_audit(
                request=request,
                action="OFFLINE_ATTENDANCE_SYNC",
                entity_type="AttendanceSession",
                entity_id="Batch",
                details=f"Faculty {request.user.username} synced {synced_count} offline sessions. Errors: {len(errors)}"
            )

        return Response({
            'message': f"Successfully synchronized {synced_count} offline attendance sessions.",
            'synced_count': synced_count,
            'errors': errors
        }, status=status.HTTP_200_OK)
