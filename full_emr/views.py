import os
import csv
import zipfile
from io import BytesIO
from datetime import datetime, date, timedelta

from django.core.mail import send_mail
from django.http import FileResponse, Http404
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, status, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from openpyxl import Workbook
import logging

from .models import AddPatients, Report, User, Appointment, Invitation, Diagnostic
from .serializer import (
    CreateAccountSerializer, LoginSerializer, AddPatientSerializer, ReportSerializer,
    GenerateReportSerializer, AppointmentSerializer, InvitationSerializer, DiagnosticSerializer, UserProfileSerializer
)

logger = logging.getLogger(__name__)

class CreateAccountView(generics.CreateAPIView):
    serializer_class = CreateAccountSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        logger.info(f"Account created for user: {user.email} (ID: {user.id})")
        return Response({
            'user': {
                'id': user.id,
                'email': user.email,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_201_CREATED)

class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        logger.info(f"Login successful for user: {serializer.validated_data['user']['email']}")
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

class IsDoctorOrNurse(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ["doctor", "nurse"]

class IsDoctor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "doctor"

class AddPatientsView(generics.CreateAPIView):
    serializer_class = AddPatientSerializer
    queryset = AddPatients.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = serializer.save()
        logger.info(f"Patient added: {patient.first_name} {patient.last_name} (ID: {patient.id}) by user {request.user.id}")
        return Response({
            'message': 'Patient added successfully',
            'patient': serializer.data
        }, status=status.HTTP_201_CREATED)

class ListPatientsView(generics.ListAPIView):
    serializer_class = AddPatientSerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def get_queryset(self):
        queryset = AddPatients.objects.all()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )
        logger.debug(f"Fetching patients for user {self.request.user.id}, search: {search or 'none'}")
        return queryset

class PatientDetailView(generics.RetrieveAPIView):
    serializer_class = AddPatientSerializer
    queryset = AddPatients.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

class DeletePatientView(generics.DestroyAPIView):
    serializer_class = AddPatientSerializer
    queryset = AddPatients.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

class UpdatePatientView(generics.UpdateAPIView):
    serializer_class = AddPatientSerializer
    queryset = AddPatients.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

class IsAuthorizedForReports(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        role = request.user.role
        category = request.data.get('category') or request.query_params.get('category')
        if role == 'doctor':
            return True
        if role == 'nurse' and category in ['clinical', 'quality']:
            return True
        if role == 'pharmacy' and category in ['administrative', 'financial']:
            return True
        logger.warning(f"User {request.user.id} with role {role} denied access to reports with category {category}")
        return False

class ListReportsView(generics.ListAPIView):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated, IsAuthorizedForReports]

    def get_queryset(self):
        queryset = Report.objects.filter(generated_by=self.request.user)
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(name__icontains=category)
        logger.debug(f"Fetching reports for user {self.request.user.id}, category: {category or 'none'}")
        return queryset

class GenerateReportView(generics.CreateAPIView):
    serializer_class = GenerateReportSerializer
    permission_classes = [IsAuthenticated, IsAuthorizedForReports]

    def generate_file(self, name, file_format, patients, params):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_path = os.path.join(settings.MEDIA_ROOT, 'reports')
        os.makedirs(base_path, exist_ok=True)
        file_name = f"{name.replace(' ', '_')}_{timestamp}.{file_format}"
        file_path = os.path.join(base_path, file_name)

        if file_format == 'pdf':
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            p.drawString(100, 750, f"Report: {name}")
            y = 700
            if params.get('include_demographics'):
                p.drawString(100, y, "Patient Demographics:")
                y -= 20
                for patient in patients:
                    p.drawString(120, y, f"{patient.first_name} {patient.last_name} - Age: {patient.age}, Gender: {patient.gender}")
                    y -= 20
            p.showPage()
            p.save()
            with open(file_path, 'wb') as f:
                f.write(buffer.getvalue())
        elif file_format == 'excel':
            wb = Workbook()
            ws = wb.active
            ws.title = name
            ws.append(['Patient ID', 'First Name', 'Last Name', 'Age', 'Gender'])
            for patient in patients:
                ws.append([patient.id, patient.first_name, patient.last_name, patient.age, patient.gender])
            wb.save(file_path)
        elif file_format == 'csv':
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Patient ID', 'First Name', 'Last Name', 'Age', 'Gender'])
                for patient in patients:
                    writer.writerow([patient.id, patient.first_name, patient.last_name, patient.age, patient.gender])

        logger.debug(f"Generated report file: {file_path}")
        return f"reports/{file_name}"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data.copy()

        if 'date_range_start' in params and params['date_range_start']:
            params['date_range_start'] = params['date_range_start'].isoformat()
        if 'date_range_end' in params and params['date_range_end']:
            params['date_range_end'] = params['date_range_end'].isoformat()

        patients = AddPatients.objects.all()
        if params.get('date_range_start'):
            start_date = datetime.strptime(params['date_range_start'], '%Y-%m-%d')
            start_date = timezone.make_aware(start_date)
            patients = patients.filter(created_at__gte=start_date)
        if params.get('date_range_end'):
            end_date = datetime.strptime(params['date_range_end'], '%Y-%m-%d')
            end_date = timezone.make_aware(end_date)
            patients = patients.filter(created_at__lte=end_date)
        if params.get('department') and params['department'] != 'all':
            patients = patients.filter(category=params['department'])

        file_path = self.generate_file(
            params['name'],
            params['format'],
            patients,
            params
        )

        report = Report.objects.create(
            name=params['name'],
            generated_by=request.user,
            file_path=file_path,
            parameters=params,
            format=params['format']
        )
        logger.info(f"Report {report.id} created by user {request.user.id}: {params['name']}")
        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)

class ViewReportView(generics.RetrieveAPIView):
    queryset = Report.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def retrieve(self, request, *args, **kwargs):
        report = self.get_object()
        if report.generated_by != request.user:
            logger.error(f"User {request.user.id} attempted to access report {report.id} not owned")
            raise Http404("Report not found")
        file_path = os.path.join(settings.MEDIA_ROOT, report.file_path.name)
        if not os.path.exists(file_path):
            logger.error(f"Report file missing: {file_path}")
            raise Http404("File not found")
        logger.debug(f"Serving report file: {file_path} to user {request.user.id}")
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=report.file_path.name)

class RetrieveReportDataView(generics.RetrieveAPIView):
    queryset = Report.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def retrieve(self, request, *args, **kwargs):
        try:
            report = self.get_object()
            logger.debug(f"Retrieving report {report.id} for user {request.user.id}")
            if report.generated_by != request.user:
                logger.error(f"Report {report.id} not owned by user {request.user.id}")
                raise Http404("Report not found")
            params = report.parameters or {}
            patients = AddPatients.objects.all()
            if params.get('date_range_start'):
                try:
                    start_date = datetime.strptime(params['date_range_start'], '%Y-%m-%d')
                    start_date = timezone.make_aware(start_date)
                    patients = patients.filter(created_at__gte=start_date)
                except ValueError as e:
                    logger.error(f"Invalid date format: {params['date_range_start']}")
                    raise Http404("Invalid date format")
            if params.get('date_range_end'):
                try:
                    end_date = datetime.strptime(params['date_range_end'], '%Y-%m-%d')
                    end_date = timezone.make_aware(end_date)
                    patients = patients.filter(created_at__lte=end_date)
                except ValueError as e:
                    logger.error(f"Invalid date format: {params['date_range_end']}")
                    raise Http404("Invalid date format")
            if params.get('department') and params['department'] != 'all':
                patients = patients.filter(category=params['department'])
            patient_data = [
                {
                    'id': patient.id,
                    'first_name': patient.first_name or "Unknown",
                    'last_name': patient.last_name or "Unknown",
                    'name': f"{patient.first_name or 'Unknown'} {patient.last_name or 'Unknown'}".strip(),
                    'age': patient.age,
                    'gender': patient.gender,
                    'category': patient.category,
                    'created_at': patient.created_at.isoformat(),
                }
                for patient in patients
            ]
            logger.debug(f"Found {len(patient_data)} patients for report {report.id}")
            return Response({
                'report_name': report.name,
                'generated_date': report.generated_date.isoformat(),
                'generated_by': str(report.generated_by),
                'format': report.format,
                'patients': patient_data,
            }, status=status.HTTP_200_OK)
        except Report.DoesNotExist:
            logger.error(f"Report {self.kwargs['pk']} does not exist")
            raise Http404("Report not found")

class ExportAllReportsView(APIView):
    permission_classes = [IsAuthenticated, IsAuthorizedForReports]

    def get(self, request):
        reports = Report.objects.filter(generated_by=request.user)
        logger.debug(f"Found {reports.count()} reports for user {request.user.id}")
        if not reports:
            logger.warning(f"No reports found for user {request.user.id}")
            return Response({"detail": "No reports found for this user."}, status=status.HTTP_404_NOT_FOUND)

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for report in reports:
                file_path = os.path.join(settings.MEDIA_ROOT, report.file_path.name)
                if os.path.exists(file_path):
                    zip_file.write(file_path, os.path.basename(report.file_path.name))
                    logger.debug(f"Added report {report.id}: {file_path} to zip")
                else:
                    logger.warning(f"Report file missing for report {report.id}: {file_path}")
            if not zip_file.namelist():
                logger.warning(f"No valid report files found for user {request.user.id}")
                return Response({"detail": "No valid report files available to export."}, status=status.HTTP_404_NOT_FOUND)
        zip_buffer.seek(0)
        logger.info(f"Exporting zip file for user {request.user.id}")
        return FileResponse(
            zip_buffer,
            as_attachment=True,
            filename=f"reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        )

class ListAppointmentsView(generics.ListAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def get_queryset(self):
        queryset = Appointment.objects.all()
        status = self.request.query_params.get('status')
        patient_id = self.request.query_params.get('patient_id')
        if status:
            queryset = queryset.filter(status=status)
        if patient_id:
            try:
                patient_id = int(patient_id)
                if not AddPatients.objects.filter(id=patient_id).exists():
                    logger.warning(f"Patient ID {patient_id} does not exist for appointment query")
                queryset = queryset.filter(patient_id=patient_id)
            except ValueError:
                logger.error(f"Invalid patient_id format: {patient_id}")
        logger.debug(f"Fetching appointments for user {self.request.user.id}, status: {status or 'none'}, patient_id: {patient_id or 'none'}")
        return queryset

class CreateAppointView(generics.CreateAPIView):
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def create(self, request, *args, **kwargs):
        logger.debug(f"Create appointment request by user: {request.user.id if request.user.is_authenticated else 'anonymous'}")
        if not request.user.is_authenticated:
            logger.error("Unauthenticated request to create appointment")
            return Response(
                {"detail": "Authentication credentials were not provided"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        date = data['date']
        time = data['time']
        duration = data['duration']
        patient = data['patient']
        if not AddPatients.objects.filter(id=patient.id).exists():
            logger.error(f"Patient ID {patient.id} does not exist")
            return Response({"error": "Patient does not exist"}, status=status.HTTP_400_BAD_REQUEST)
        end_time = (datetime.combine(date, time) + timedelta(minutes=duration)).time()
        overlapping = Appointment.objects.filter(
            doctor=request.user,
            date=date,
            time__lt=end_time,
            time__gte=time
        ).exists()
        if overlapping:
            logger.warning(f"Time slot conflict for user {request.user.id} on {date} at {time}")
            return Response({"error": "Time slot is already booked"}, status=status.HTTP_400_BAD_REQUEST)
        instance = serializer.save()
        logger.info(f"Appointment {instance.id} created for patient {patient.id} ({patient.first_name} {patient.last_name}) by user {request.user.id}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class UpdateAppointView(generics.UpdateAPIView):
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

class DeleteAppointmentView(generics.DestroyAPIView):
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.all()
    permission_classes = [IsAuthenticated, IsDoctor]

class AvailableSlotsView(APIView):
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def get(self, request):
        date_str = request.query_params.get('date')
        if not date_str:
            logger.error("Date not provided for available slots query")
            return Response({"error": "Date is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Invalid date format: {date_str}")
            return Response({"error": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)

        clinic_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()) + timedelta(hours=9))
        clinic_end = timezone.make_aware(datetime.combine(target_date, datetime.min.time()) + timedelta(hours=17))
        slot_duration = timedelta(minutes=30)

        appointments = Appointment.objects.filter(doctor=request.user, date=target_date)
        booked_slots = []
        for apt in appointments:
            start_datetime = timezone.make_aware(datetime.combine(apt.date, apt.time))
            end_datetime = start_datetime + timedelta(minutes=apt.duration)
            booked_slots.append((start_datetime, end_datetime))

        available_slots = []
        current_time = clinic_start
        while current_time + slot_duration <= clinic_end:
            slot_start = current_time.time().strftime('%H:%M')
            slot_end = (current_time + slot_duration).time()
            is_booked = any(
                (apt_start <= current_time + slot_duration and apt_end > current_time)
                for apt_start, apt_end in booked_slots
            )
            if not is_booked:
                available_slots.append(slot_start)
            current_time += slot_duration

        logger.debug(f"Available slots for {date_str}: {len(available_slots)} slots")
        return Response({"available_slots": available_slots})

class ListInvitationsView(generics.ListAPIView):
    serializer_class = InvitationSerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def get_queryset(self):
        queryset = Invitation.objects.filter(doctor=self.request.user)
        logger.debug(f"Fetching invitations for user {self.request.user.id}")
        return queryset

class CreateInvitationView(generics.CreateAPIView):
    serializer_class = InvitationSerializer
    queryset = Invitation.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()

        # Get patient email
        patient_email = invitation.patient.email

        if patient_email:
            # Create a more detailed email message
            subject = f"Appointment Invitation from {request.user.get_full_name()}"

            # Format preferred dates for display
            formatted_dates = []
            for date_str in invitation.preferred_dates:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    formatted_dates.append(date_obj.strftime('%B %d, %Y'))
                except (ValueError, TypeError):
                    continue

            dates_list = "\n".join(
                [f"• {date}" for date in formatted_dates]) if formatted_dates else "No specific dates suggested"

            message = f"""
Dear {invitation.patient.first_name or 'Patient'},

You have been invited to schedule an appointment at our clinic.

The following dates have been suggested for your appointment:
{dates_list}

Please log in to our patient portal to confirm your availability or suggest alternative dates.

If you have any questions, please contact our office.

Best regards,
{request.user.get_full_name()}
{request.user.role.title()}
            """

            try:
                send_mail(
                    subject,
                    message.strip(),
                    settings.DEFAULT_FROM_EMAIL,
                    [patient_email],
                    fail_silently=False,
                )
                logger.info(f"Invitation email sent to {patient_email} for invitation {invitation.id}")
            except Exception as e:
                logger.error(f"Failed to send invitation email to {patient_email}: {str(e)}")
                # Don't fail the request if email fails, just log it
        else:
            logger.warning(f"Patient {invitation.patient.id} has no email address, cannot send invitation email")

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class AppointmentDetailView(generics.RetrieveAPIView):
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

class InvitationDetailView(generics.RetrieveAPIView):
    serializer_class = InvitationSerializer
    queryset = Invitation.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

class DiagnosticListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        diagnostics = Diagnostic.objects.all()
        serializer = DiagnosticSerializer(diagnostics, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = DiagnosticSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)