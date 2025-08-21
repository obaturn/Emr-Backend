import os
import csv
import zipfile
from io import BytesIO
from datetime import datetime, date, timedelta
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

from .models import AddPatients, Report, User, Appointment, Invitation
from .serializer import CreateAccountSerializer, LoginSerializer, AddPatientSerializer, ReportSerializer, \
    GenerateReportSerializer, AppointmentSerializer, InvitationSerializer

logger = logging.getLogger(__name__)

class CreateAccountView(generics.CreateAPIView):
    serializer_class = CreateAccountSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

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
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class IsDoctorOrNurse(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ["doctor", "nurse"]


class IsDoctor(permissions.BasePermission):
    """Permission to only allow doctors to perform an action."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "doctor"


class AddPatientsView(generics.CreateAPIView):
    serializer_class = AddPatientSerializer
    queryset = AddPatients.objects.all()
    permission_classes = [IsDoctorOrNurse]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
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
        return queryset


class PatientDetailView(generics.RetrieveAPIView):
    serializer_class = AddPatientSerializer
    queryset = AddPatients.objects.all()


class DeletePatientView(generics.DestroyAPIView):
    serializer_class = AddPatientSerializer
    queryset = AddPatients.objects.all()


class UpdatePatientView(generics.UpdateAPIView):
    serializer_class = AddPatientSerializer
    queryset = AddPatients.objects.all()


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
        return False


class ListReportsView(generics.ListAPIView):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated, IsAuthorizedForReports]

    def get_queryset(self):
        queryset = Report.objects.filter(generated_by=self.request.user)
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(name__icontains=category)
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

        return f"reports/{file_name}"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data.copy()

        # Convert date objects to strings for JSON serialization
        if 'date_range_start' in params and params['date_range_start']:
            params['date_range_start'] = params['date_range_start'].isoformat()
        if 'date_range_end' in params and params['date_range_end']:
            params['date_range_end'] = params['date_range_end'].isoformat()

        # Fetch patient data with timezone-aware filtering
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

        # Generate file
        file_path = self.generate_file(
            params['name'],
            params['format'],
            patients,
            params
        )

        # Save to model
        report = Report.objects.create(
            name=params['name'],
            generated_by=request.user,
            file_path=file_path,
            parameters=params,
            format=params['format']
        )

        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)


class ViewReportView(generics.RetrieveAPIView):
    queryset = Report.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def retrieve(self, request, *args, **kwargs):
        report = self.get_object()
        if report.generated_by != request.user:
            raise Http404("Report not found")
        file_path = os.path.join(settings.MEDIA_ROOT, report.file_path.name)
        if not os.path.exists(file_path):
            raise Http404("File not found")
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
                    'first_name': patient.first_name,
                    'last_name': patient.last_name,
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
            queryset = queryset.filter(patient_id=patient_id)
        return queryset


class CreateAppointView(generics.CreateAPIView):
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        date = data['date']
        time = data['time']
        duration = data['duration']
        end_time = (datetime.combine(date, time) + timedelta(minutes=duration)).time()
        overlapping = Appointment.objects.filter(
            doctor=request.user,
            date=date,
            time__lt=end_time,
            time__gte=time
        ).exists()
        if overlapping:
            return Response({"error": "Time slot is already booked"}, status=status.HTTP_400_BAD_REQUEST)
        instance = serializer.save()
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
            return Response({"error": "Date is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)

        # Assume clinic hours: 9:00 AM to 5:00 PM, 30-min slots
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

        return Response({"available_slots": available_slots})


class ListInvitationsView(generics.ListAPIView):
    serializer_class = InvitationSerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def get_queryset(self):
        return Invitation.objects.filter(doctor=self.request.user)


class CreateInvitationView(generics.CreateAPIView):
    serializer_class = InvitationSerializer
    queryset = Invitation.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]


class AppointmentDetailView(generics.RetrieveAPIView):
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]


class InvitationDetailView(generics.RetrieveAPIView):
    serializer_class = InvitationSerializer
    queryset = Invitation.objects.all()
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]