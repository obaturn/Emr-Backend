from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CreateAccountView, LoginView, AddPatientsView, PatientDetailView, DeletePatientView, \
    ListPatientsView, UpdatePatientView, ListReportsView, GenerateReportView, ViewReportView, RetrieveReportDataView, \
    ExportAllReportsView, ListAppointmentsView, DeleteAppointmentView, AvailableSlotsView, CreateAppointView, \
    UpdateAppointView, ListInvitationsView, CreateInvitationView, AppointmentDetailView, InvitationDetailView, \
    DiagnosticListCreateView, UserProfileView, LabReportListCreateView, LabReportDetailView, workspace_dashboard, \
    analytics_dashboard, MedicalHistoryListCreateView, MedicalHistoryDetailView, VitalSignsDetailView, \
    VitalSignsListCreateView, AllergyListCreateView, AllergyDetailView, ImmunizationListCreateView, \
    ImmunizationDetailView, FamilyHistoryListCreateView, FamilyHistoryDetailView, SocialHistoryListCreateView, \
    SocialHistoryDetailView, FeedbackListCreateView, FeedbackDetailView, FeedbackResponseListCreateView, \
    SupportRequestListCreateView, SupportRequestDetailView, SupportResponseListCreateView, health_promotion_stats, \
    EducationalResourceDetailView, EducationalResourceListCreateView, HealthCampaignDetailView, \
    HealthCampaignListCreateView, ForgotPasswordView, VerifyOTPView, ResetPasswordView

urlpatterns = [
    path('register/', CreateAccountView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('add-patient/', AddPatientsView.as_view(), name='add-patient'),
    path('patients/<int:pk>/', PatientDetailView.as_view(), name='patient-detail'),
    path('patients/<int:pk>/delete/', DeletePatientView.as_view(), name='delete-patient'),
    path('patients/', ListPatientsView.as_view(), name='list-patients'),
    path('patients/<int:pk>/update/', UpdatePatientView.as_view(), name='update-patient'),
    path('reports/', ListReportsView.as_view(), name='list-reports'),
    path('reports/generate/', GenerateReportView.as_view(), name='generate-report'),
    path('reports/<int:pk>/view/', ViewReportView.as_view(), name='view-report'),
    path('reports/<int:pk>/data/', RetrieveReportDataView.as_view(), name='retrieve-report-data'),
    path('reports/export-all/', ExportAllReportsView.as_view(), name='export-all-reports'),
    path('appointments/', ListAppointmentsView.as_view(), name='list-appointments'),
    path('appointments/create/', CreateAppointView.as_view(), name='create-appointment'),
    path('appointments/<int:pk>/update/', UpdateAppointView.as_view(), name='update-appointment'),
    path('appointments/<int:pk>/delete/', DeleteAppointmentView.as_view(), name='delete-appointment'),
    path('available-slots/', AvailableSlotsView.as_view(), name='available-slots'),
    path('invitations/', ListInvitationsView.as_view(), name='list-invitations'),
    path('invitations/create/', CreateInvitationView.as_view(), name='create-invitation'),
    path('appointments/<int:pk>/', AppointmentDetailView.as_view(), name='appointment-detail'),
    path('invitations/<int:pk>/', InvitationDetailView.as_view(), name='invitation-detail'),
    path('diagnostics/', DiagnosticListCreateView.as_view(), name='diagnostic-list-create'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('lab-reports/', LabReportListCreateView.as_view(), name='lab-report-list-create'),
    path('lab-reports/<int:pk>/', LabReportDetailView.as_view(), name='lab-report-detail'),
    path('workspace/dashboard/', workspace_dashboard, name='workspace_dashboard'),
    path('analytics/dashboard/', analytics_dashboard, name='analytics_dashboard'),
    path('ehr/medical-history/', MedicalHistoryListCreateView.as_view(), name='medical_history_list'),
    path('ehr/medical-history/<int:pk>/', MedicalHistoryDetailView.as_view(), name='medical_history_detail'),
    path('ehr/vital-signs/', VitalSignsListCreateView.as_view(), name='vital_signs_list'),
    path('ehr/vital-signs/<int:pk>/', VitalSignsDetailView.as_view(), name='vital_signs_detail'),
    path('ehr/allergies/', AllergyListCreateView.as_view(), name='allergies_list'),
    path('ehr/allergies/<int:pk>/', AllergyDetailView.as_view(), name='allergies_detail'),
    path('ehr/immunizations/', ImmunizationListCreateView.as_view(), name='immunizations_list'),
    path('ehr/immunizations/<int:pk>/', ImmunizationDetailView.as_view(), name='immunizations_detail'),
    path('ehr/family-history/', FamilyHistoryListCreateView.as_view(), name='family_history_list'),
    path('ehr/family-history/<int:pk>/', FamilyHistoryDetailView.as_view(), name='family_history_detail'),
    path('ehr/social-history/', SocialHistoryListCreateView.as_view(), name='social_history_list'),
    path('ehr/social-history/<int:pk>/', SocialHistoryDetailView.as_view(), name='social_history_detail'),
    path('health-promotion/campaigns/', HealthCampaignListCreateView.as_view(), name='health_campaigns_list'),
    path('health-promotion/campaigns/<int:pk>/', HealthCampaignDetailView.as_view(), name='health_campaign_detail'),
    path('health-promotion/resources/', EducationalResourceListCreateView.as_view(), name='educational_resources_list'),
    path('health-promotion/resources/<int:pk>/', EducationalResourceDetailView.as_view(), name='educational_resource_detail'),
    path('feedback/', FeedbackListCreateView.as_view(), name='feedback_list'),
    path('feedback/<int:pk>/', FeedbackDetailView.as_view(), name='feedback_detail'),
    path('feedback/<int:feedback_id>/responses/', FeedbackResponseListCreateView.as_view(), name='feedback_responses'),
    path('support/requests/', SupportRequestListCreateView.as_view(), name='support_requests_list'),
    path('support/requests/<int:pk>/', SupportRequestDetailView.as_view(), name='support_request_detail'),
    path('support/requests/<int:support_request_id>/responses/', SupportResponseListCreateView.as_view(),name='support_responses'),
    path('health-promotion/stats/', health_promotion_stats, name='health_promotion_stats'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
]


# Allow credentials (cookies, authorization headers)
