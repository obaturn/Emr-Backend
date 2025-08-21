from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CreateAccountView, LoginView, AddPatientsView, PatientDetailView, DeletePatientView, \
    ListPatientsView, UpdatePatientView, ListReportsView, GenerateReportView, ViewReportView, RetrieveReportDataView, \
    ExportAllReportsView, ListAppointmentsView, DeleteAppointmentView, AvailableSlotsView, CreateAppointView, \
    UpdateAppointView, ListInvitationsView, CreateInvitationView, AppointmentDetailView, InvitationDetailView

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
]
# Allow credentials (cookies, authorization headers)
