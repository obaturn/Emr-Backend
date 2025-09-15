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
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from openpyxl import Workbook
import logging

from .models import AddPatients, Report, User, Appointment, Invitation, Diagnostic, LabReport, SocialHistory, \
    FamilyHistory, Immunization, Allergy, VitalSigns, MedicalHistory, HealthCampaign, EducationalResource, Feedback, \
    SupportRequest, FeedbackResponse, SupportResponse
from .serializer import (
    CreateAccountSerializer, LoginSerializer, AddPatientSerializer, ReportSerializer,
    GenerateReportSerializer, AppointmentSerializer, InvitationSerializer, DiagnosticSerializer, UserProfileSerializer,
    LabReportSerializer, SocialHistorySerializer, FamilyHistorySerializer, ImmunizationSerializer, AllergySerializer,
    MedicalHistorySerializer, VitalSignsSerializer, HealthCampaignSerializer, EducationalResourceSerializer,
    FeedbackSerializer, FeedbackResponseSerializer, SupportRequestSerializer, SupportResponseSerializer
)

logger = logging.getLogger(__name__)
logger = logging.getLogger(__name__)


# ⭐ ADD THE WORKSPACE FUNCTION RIGHT HERE (AFTER logger AND BEFORE FIRST CLASS) ⭐
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def workspace_dashboard(request):
    """Combined dashboard data for workspace"""
    user = request.user
    today = timezone.now().date()

    # Today's appointments - filter by user role
    if user.role == 'doctor':
        today_appointments = Appointment.objects.filter(
            doctor=user,
            date=today
        ).select_related('patient')
    elif user.role == 'nurse':
        # Nurses can see appointments they're involved with
        today_appointments = Appointment.objects.filter(
            Q(doctor=user) | Q(doctor__role='doctor'),
            date=today
        ).select_related('patient')
    else:
        # Admin can see all appointments
        today_appointments = Appointment.objects.filter(
            date=today
        ).select_related('patient')

    # Format appointments using your existing serializer
    appointment_serializer = AppointmentSerializer(today_appointments, many=True)
    formatted_appointments = []

    for apt_data in appointment_serializer.data:
        formatted_appointments.append({
            'id': apt_data['id'],
            'patient_name': apt_data.get('patient_name', 'Unknown Patient'),
            'time': apt_data['time'],
            'status': apt_data['status'],
            'type': apt_data['type']
        })

    # Pending tasks
    pending_tasks = []

    # Pending diagnostics - filter by user
    if user.role in ['doctor', 'nurse']:
        pending_diags = Diagnostic.objects.filter(
            created_by=user,
            status='pending'
        ).select_related('patient')

        for diag in pending_diags:
            pending_tasks.append({
                'id': f"diag_{diag.id}",
                'type': 'diagnostic',
                'title': f"{diag.test_type} for {diag.patient.first_name} {diag.patient.last_name}",
                'patient_name': f"{diag.patient.first_name} {diag.patient.last_name}",
                'priority': 'high',
                'due_date': diag.date.strftime('%Y-%m-%d')
            })

    # Recent activity (last 10 items)
    recent_activity = []

    # Recent appointments
    if user.role == 'doctor':
        recent_appts = Appointment.objects.filter(
            doctor=user
        ).select_related('patient').order_by('-created_at')[:5]
    elif user.role == 'nurse':
        recent_appts = Appointment.objects.filter(
            Q(doctor=user) | Q(doctor__role='doctor')
        ).select_related('patient').order_by('-created_at')[:5]
    else:
        recent_appts = Appointment.objects.all().select_related('patient').order_by('-created_at')[:5]

    for apt in recent_appts:
        recent_activity.append({
            'id': f"apt_{apt.id}",
            'type': 'appointment',
            'description': f"Appointment scheduled for {apt.patient.first_name} {apt.patient.last_name}",
            'timestamp': apt.created_at.strftime('%Y-%m-%d %H:%M'),
            'patient_name': f"{apt.patient.first_name} {apt.patient.last_name}"
        })

    # Recent diagnostics
    if user.role in ['doctor', 'nurse']:
        recent_diags = Diagnostic.objects.filter(
            created_by=user
        ).select_related('patient').order_by('-created_at')[:3]

        for diag in recent_diags:
            recent_activity.append({
                'id': f"diag_{diag.id}",
                'type': 'diagnostic',
                'description': f"{diag.test_type} completed for {diag.patient.first_name}",
                'timestamp': diag.created_at.strftime('%Y-%m-%d %H:%M'),
                'patient_name': f"{diag.patient.first_name} {diag.patient.last_name}"
            })

    # Patient stats
    patient_stats = {
        'total_patients': AddPatients.objects.count(),
        'with_appointments': AddPatients.objects.filter(
            appointments__date__gte=today
        ).distinct().count(),
        'pending_diagnostics': Diagnostic.objects.filter(
            status='pending'
        ).count(),
        'completed_today': Appointment.objects.filter(
            date=today,
            status='Completed'
        ).count()
    }

    # Alerts
    alerts = []

    # Check for cancelled appointments
    cancelled_today = Appointment.objects.filter(
        date=today,
        status='Cancelled'
    )

    if user.role == 'doctor':
        cancelled_today = cancelled_today.filter(doctor=user)

    cancelled_count = cancelled_today.count()

    if cancelled_count > 0:
        alerts.append({
            'id': 'cancelled_appts',
            'type': 'warning',
            'message': f"{cancelled_count} appointment(s) cancelled today",
            'action_url': f"/{user.role}/calendar"
        })

    # Check for pending diagnostics
    if user.role in ['doctor', 'nurse']:
        pending_count = Diagnostic.objects.filter(
            created_by=user,
            status='pending',
            date__lt=today  # Overdue
        ).count()

        if pending_count > 0:
            alerts.append({
                'id': 'overdue_diagnostics',
                'type': 'warning',
                'message': f"{pending_count} diagnostic(s) are overdue",
                'action_url': f"/{user.role}/diagnostics"
            })

    logger.info(f"Workspace dashboard data generated for user {user.id} ({user.role})")
    return Response({
        'today_appointments': formatted_appointments,
        'pending_tasks': pending_tasks,
        'recent_activity': recent_activity,
        'patient_stats': patient_stats,
        'alerts': alerts
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics_dashboard(request):
    """Analytics dashboard data with comprehensive metrics"""
    user = request.user
    time_range = request.GET.get('period', 'month')

    # Calculate date range
    today = timezone.now().date()
    if time_range == 'week':
        start_date = today - timedelta(days=7)
    elif time_range == 'quarter':
        start_date = today - timedelta(days=90)
    elif time_range == 'year':
        start_date = today - timedelta(days=365)
    else:  # month
        start_date = today - timedelta(days=30)

    # Overview Statistics
    total_patients = AddPatients.objects.count()
    total_appointments = Appointment.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=today
    ).count()

    completed_appointments = Appointment.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=today,
        status='Completed'
    ).count()

    pending_diagnostics = Diagnostic.objects.filter(
        status='pending',
        created_at__date__gte=start_date
    ).count()

    total_reports = Report.objects.filter(
        generated_date__date__gte=start_date,
        generated_by=user
    ).count()

    # Average wait time (mock data - you can calculate from actual appointment data)
    avg_wait_time = 15  # minutes

    # Performance Metrics
    if total_appointments > 0:
        completion_rate = (completed_appointments / total_appointments) * 100
    else:
        completion_rate = 0

    # Mock TAT data (you can calculate from diagnostic completion times)
    diagnostic_tat = 120  # minutes

    # Mock satisfaction score
    satisfaction_score = 87.5

    # Mock resource utilization
    resource_utilization = 78.3

    # Demographics
    age_distribution = [
        {"range": "18-30", "percentage": 35},
        {"range": "31-50", "percentage": 45},
        {"range": "51+", "percentage": 20}
    ]

    gender_distribution = [
        {"gender": "Female", "percentage": 58},
        {"gender": "Male", "percentage": 42}
    ]

    appointment_types = [
        {"type": "Consultation", "count": 45},
        {"type": "Follow-up", "count": 32},
        {"type": "Emergency", "count": 12},
        {"type": "Check-up", "count": 28}
    ]

    # Alerts based on real data
    alerts = []

    # Check for high no-show rate
    if total_appointments > 10:
        cancelled_count = Appointment.objects.filter(
            created_at__date__gte=start_date,
            status='Cancelled'
        ).count()

        if cancelled_count > total_appointments * 0.15:  # 15% cancellation rate
            alerts.append({
                'id': 'high_cancellation_rate',
                'type': 'warning',
                'message': f'High cancellation rate: {cancelled_count} appointments cancelled',
                'action_url': f'/{user.role}/calendar'
            })

    # Check for pending diagnostics
    if pending_diagnostics > 5:
        alerts.append({
            'id': 'pending_diagnostics',
            'type': 'info',
            'message': f'{pending_diagnostics} diagnostics are pending review',
            'action_url': f'/{user.role}/diagnostics'
        })

    # Trends data (mock - you can implement real trend calculations)
    patient_growth = [
        {"date": (today - timedelta(days=6)).strftime('%Y-%m-%d'), "count": 12},
        {"date": (today - timedelta(days=5)).strftime('%Y-%m-%d'), "count": 15},
        {"date": (today - timedelta(days=4)).strftime('%Y-%m-%d'), "count": 18},
        {"date": (today - timedelta(days=3)).strftime('%Y-%m-%d'), "count": 22},
        {"date": (today - timedelta(days=2)).strftime('%Y-%m-%d'), "count": 25},
        {"date": (today - timedelta(days=1)).strftime('%Y-%m-%d'), "count": 28},
        {"date": today.strftime('%Y-%m-%d'), "count": total_patients}
    ]

    appointment_trends = [
        {"date": (today - timedelta(days=6)).strftime('%Y-%m-%d'), "count": 8},
        {"date": (today - timedelta(days=5)).strftime('%Y-%m-%d'), "count": 12},
        {"date": (today - timedelta(days=4)).strftime('%Y-%m-%d'), "count": 15},
        {"date": (today - timedelta(days=3)).strftime('%Y-%m-%d'), "count": 18},
        {"date": (today - timedelta(days=2)).strftime('%Y-%m-%d'), "count": 22},
        {"date": (today - timedelta(days=1)).strftime('%Y-%m-%d'), "count": 25},
        {"date": today.strftime('%Y-%m-%d'), "count": total_appointments}
    ]

    diagnostic_completion = [
        {"date": (today - timedelta(days=6)).strftime('%Y-%m-%d'), "count": 5},
        {"date": (today - timedelta(days=5)).strftime('%Y-%m-%d'), "count": 7},
        {"date": (today - timedelta(days=4)).strftime('%Y-%m-%d'), "count": 9},
        {"date": (today - timedelta(days=3)).strftime('%Y-%m-%d'), "count": 11},
        {"date": (today - timedelta(days=2)).strftime('%Y-%m-%d'), "count": 13},
        {"date": (today - timedelta(days=1)).strftime('%Y-%m-%d'), "count": 15},
        {"date": today.strftime('%Y-%m-%d'), "count": pending_diagnostics}
    ]

    logger.info(f"Analytics dashboard data generated for user {user.id} ({user.role}) - period: {time_range}")

    return Response({
        'overview': {
            'total_patients': total_patients,
            'total_appointments': total_appointments,
            'completed_appointments': completed_appointments,
            'pending_diagnostics': pending_diagnostics,
            'total_reports': total_reports,
            'average_wait_time': avg_wait_time
        },
        'trends': {
            'patient_growth': patient_growth,
            'appointment_trends': appointment_trends,
            'diagnostic_completion': diagnostic_completion
        },
        'performance': {
            'appointment_completion_rate': completion_rate,
            'diagnostic_turnaround_time': diagnostic_tat,
            'patient_satisfaction': satisfaction_score,
            'resource_utilization': resource_utilization
        },
        'demographics': {
            'age_distribution': age_distribution,
            'gender_distribution': gender_distribution,
            'appointment_types': appointment_types
        },
        'alerts': alerts
    })
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


class HealthCampaignListCreateView(generics.ListCreateAPIView):
    serializer_class = HealthCampaignSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = HealthCampaign.objects.all()
        status = self.request.query_params.get('status')
        category = self.request.query_params.get('category')

        if status:
            queryset = queryset.filter(status=status)
        if category:
            queryset = queryset.filter(category__icontains=category)

        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class HealthCampaignDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = HealthCampaignSerializer
    permission_classes = [IsAuthenticated]
    queryset = HealthCampaign.objects.all()


class EducationalResourceListCreateView(generics.ListCreateAPIView):
    serializer_class = EducationalResourceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = EducationalResource.objects.filter(is_active=True)
        category = self.request.query_params.get('category')
        type_filter = self.request.query_params.get('type')

        if category:
            queryset = queryset.filter(category__icontains=category)
        if type_filter:
            queryset = queryset.filter(type=type_filter)

        return queryset.order_by('-publish_date')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class EducationalResourceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EducationalResourceSerializer
    permission_classes = [IsAuthenticated]
    queryset = EducationalResource.objects.all()


# Feedback Views
class FeedbackListCreateView(generics.ListCreateAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Feedback.objects.all()
        status = self.request.query_params.get('status')
        category = self.request.query_params.get('category')

        if status:
            queryset = queryset.filter(status=status)
        if category:
            queryset = queryset.filter(category__icontains=category)

        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FeedbackDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [IsAuthenticated]
    queryset = Feedback.objects.all()


class FeedbackResponseListCreateView(generics.ListCreateAPIView):
    serializer_class = FeedbackResponseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        feedback_id = self.kwargs.get('feedback_id')
        return FeedbackResponse.objects.filter(feedback_id=feedback_id).order_by('created_at')

    def perform_create(self, serializer):
        feedback_id = self.kwargs.get('feedback_id')
        feedback = Feedback.objects.get(id=feedback_id)
        serializer.save(feedback=feedback, responder=self.request.user)


# Support Views
class SupportRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = SupportRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = SupportRequest.objects.all()
        status = self.request.query_params.get('status')
        priority = self.request.query_params.get('priority')
        category = self.request.query_params.get('category')

        if status:
            queryset = queryset.filter(status=status)
        if priority:
            queryset = queryset.filter(priority=priority)
        if category:
            queryset = queryset.filter(category__icontains=category)

        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SupportRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SupportRequestSerializer
    permission_classes = [IsAuthenticated]
    queryset = SupportRequest.objects.all()


class SupportResponseListCreateView(generics.ListCreateAPIView):
    serializer_class = SupportResponseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        support_request_id = self.kwargs.get('support_request_id')
        return SupportResponse.objects.filter(support_request_id=support_request_id).order_by('created_at')

    def perform_create(self, serializer):
        support_request_id = self.kwargs.get('support_request_id')
        support_request = SupportRequest.objects.get(id=support_request_id)
        serializer.save(support_request=support_request, responder=self.request.user)


# Analytics Views for Health Promotion
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health_promotion_stats(request):
    """Statistics for health promotion dashboard"""
    total_campaigns = HealthCampaign.objects.count()
    active_campaigns = HealthCampaign.objects.filter(status='active').count()
    total_resources = EducationalResource.objects.filter(is_active=True).count()
    total_feedback = Feedback.objects.count()
    resolved_feedback = Feedback.objects.filter(status='resolved').count()
    total_support = SupportRequest.objects.count()
    resolved_support = SupportRequest.objects.filter(status='resolved').count()

    # Average rating
    feedback_ratings = Feedback.objects.values_list('rating', flat=True)
    avg_rating = sum(feedback_ratings) / len(feedback_ratings) if feedback_ratings else 0

    return Response({
        'campaigns': {
            'total': total_campaigns,
            'active': active_campaigns,
        },
        'resources': {
            'total': total_resources,
        },
        'feedback': {
            'total': total_feedback,
            'resolved': resolved_feedback,
            'average_rating': round(avg_rating, 1),
        },
        'support': {
            'total': total_support,
            'resolved': resolved_support,
        }
    })

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

class LabReportListCreateView(generics.ListCreateAPIView):
    serializer_class = LabReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = LabReport.objects.all()
        if self.request.user.role != 'doctor':
            queryset = queryset.filter(created_by=self.request.user)
        logger.debug(f"Fetching lab reports for user {self.request.user.id}")
        return queryset

    def perform_create(self, serializer):
        if self.request.user.role != 'doctor':
            logger.error(f"User {self.request.user.id} with role {self.request.user.role} attempted to create lab report")
            raise serializer.ValidationError("Only doctors can create lab reports.")
        serializer.save(created_by=self.request.user)
        logger.info(f"Lab report created by user {self.request.user.id} for patient {serializer.validated_data['patient'].id}")

class LabReportDetailView(generics.RetrieveAPIView):
    serializer_class = LabReportSerializer
    queryset = LabReport.objects.all()
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        lab_report = self.get_object()
        if request.user.role != 'doctor' and lab_report.created_by != request.user:
            logger.error(f"User {request.user.id} attempted to access lab report {lab_report.id} not owned")
            raise Http404("Lab report not found")
        logger.debug(f"Retrieving lab report {lab_report.id} for user {request.user.id}")
        return Response(self.get_serializer(lab_report).data)


class MedicalHistoryListCreateView(generics.ListCreateAPIView):
    serializer_class = MedicalHistorySerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def get_queryset(self):
        patient_id = self.request.query_params.get('patient_id')
        if patient_id:
            return MedicalHistory.objects.filter(patient_id=patient_id)
        return MedicalHistory.objects.all()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class MedicalHistoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MedicalHistorySerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]
    queryset = MedicalHistory.objects.all()


# Vital Signs Views
class VitalSignsListCreateView(generics.ListCreateAPIView):
    serializer_class = VitalSignsSerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def get_queryset(self):
        patient_id = self.request.query_params.get('patient_id')
        if patient_id:
            return VitalSigns.objects.filter(patient_id=patient_id).order_by('-recorded_at')
        return VitalSigns.objects.all().order_by('-recorded_at')

    def perform_create(self, serializer):
        print("Serializer data:", self.request.data)
        print("Serializer errors before save:", serializer.errors)
        serializer.save(recorded_by=self.request.user)

class VitalSignsDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VitalSignsSerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]
    queryset = VitalSigns.objects.all()
class VitalSignsDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VitalSignsSerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]
    queryset = VitalSigns.objects.all()


# Allergy Views
class AllergyListCreateView(generics.ListCreateAPIView):
    serializer_class = AllergySerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def get_queryset(self):
        patient_id = self.request.query_params.get('patient_id')
        if patient_id:
            return Allergy.objects.filter(patient_id=patient_id)
        return Allergy.objects.all()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AllergyDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AllergySerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]
    queryset = Allergy.objects.all()


# Immunization Views
class ImmunizationListCreateView(generics.ListCreateAPIView):
    serializer_class = ImmunizationSerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def get_queryset(self):
        patient_id = self.request.query_params.get('patient_id')
        if patient_id:
            return Immunization.objects.filter(patient_id=patient_id).order_by('-administered_date')
        return Immunization.objects.all().order_by('-administered_date')

    def perform_create(self, serializer):
        serializer.save(administered_by=self.request.user)


class ImmunizationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ImmunizationSerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]
    queryset = Immunization.objects.all()


# Family History Views
class FamilyHistoryListCreateView(generics.ListCreateAPIView):
    serializer_class = FamilyHistorySerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def get_queryset(self):
        patient_id = self.request.query_params.get('patient_id')
        if patient_id:
            return FamilyHistory.objects.filter(patient_id=patient_id)
        return FamilyHistory.objects.all()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class FamilyHistoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FamilyHistorySerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]
    queryset = FamilyHistory.objects.all()


# Social History Views
class SocialHistoryListCreateView(generics.ListCreateAPIView):
    serializer_class = SocialHistorySerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]

    def get_queryset(self):
        patient_id = self.request.query_params.get('patient_id')
        if patient_id:
            return SocialHistory.objects.filter(patient_id=patient_id)
        return SocialHistory.objects.all()

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)


class SocialHistoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SocialHistorySerializer
    permission_classes = [IsAuthenticated, IsDoctorOrNurse]
    queryset = SocialHistory.objects.all()