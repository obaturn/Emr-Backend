import re
from datetime import timedelta
import logging
from django.utils import timezone
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, AddPatients, Report, Appointment, Invitation, Diagnostic, LabReport, SocialHistory, \
    FamilyHistory, Immunization, Allergy, VitalSigns, MedicalHistory, SupportRequest, SupportResponse, FeedbackResponse, \
    Feedback, HealthCampaign, EducationalResource, OTP

logger = logging.getLogger(__name__)

User = get_user_model()

class CreateAccountSerializer(serializers.ModelSerializer):
    profile_image = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2',
            'first_name', 'last_name', 'role', 'speciality',
            'phone_number', 'country_code', 'license_number',
            'profile_image'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True},
            'username': {'required': True},
            'phone_number': {'required': True},
            'role': {'required': True},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email is already registered.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value

    def validate_phone_number(self, value):
        if not re.match(r'^\d{7,15}$', value):
            raise serializers.ValidationError("Enter a valid phone number (7–15 digits).")
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Phone number already registered.")
        return value

    def validate_license_number(self, value):
        role = self.initial_data.get("role")
        if role in ["doctor", "nurse"] and not value:
            raise serializers.ValidationError(f"{role.capitalize()} must provide a license number.")
        return value

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Passwords don't match."})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        logger.info(f"User created: {user.email} (ID: {user.id})")
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'}, trim_whitespace=False)
    remember_me = serializers.BooleanField(default=False, required=False)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        remember_me = attrs.get('remember_me', False)

        user = authenticate(
            request=self.context.get('request'),
            username=email,
            password=password
        )
        if not user:
            logger.error(f"Login failed for email: {email}")
            raise serializers.ValidationError("Invalid credentials.")

        refresh = RefreshToken.for_user(user)

        # If remember_me is true, make refresh token last longer
        if remember_me:
            refresh.set_exp(lifetime=timedelta(days=30))  # 30 days
        else:
            refresh.set_exp(lifetime=timedelta(days=1))   # default 1 day

        access = refresh.access_token
        # Optional: you can also make access token longer if you want
        access.set_exp(lifetime=timedelta(hours=1))

        return {
            'user': {
                'id': user.id,
                'email': user.email,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name
            },
            'tokens': {
                'access': str(access),
                'refresh': str(refresh)
            }
        }


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email address.")
        return value


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp_code = serializers.CharField(max_length=6, required=True)

    def validate(self, data):
        email = data.get('email')
        otp_code = data.get('otp_code')

        try:
            user = User.objects.get(email=email)
            otp = OTP.objects.filter(
                user=user,
                otp_code=otp_code,
                purpose='password_reset',
                is_used=False
            ).first()

            if not otp or not otp.is_valid():
                raise serializers.ValidationError("Invalid or expired OTP.")

            data['user'] = user
            data['otp'] = otp

        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        return data


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp_code = serializers.CharField(max_length=6, required=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords don't match.")

        # Verify OTP first
        otp_serializer = VerifyOTPSerializer(data={
            'email': data['email'],
            'otp_code': data['otp_code']
        })

        if not otp_serializer.is_valid():
            raise serializers.ValidationError(otp_serializer.errors)

        data['user'] = otp_serializer.validated_data['user']
        data['otp'] = otp_serializer.validated_data['otp']

        return data


class AddPatientSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField(read_only=True)
    dateOfBirth = serializers.DateField(source='dob', read_only=True)
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = AddPatients
        fields = [
            'id', 'first_name', 'last_name', 'name', 'email', 'phone', 'dob', 'dateOfBirth', 'age', 'gender',
            'address', 'city', 'pincode', 'aadhaar', 'remarks', 'category', 'created_at', 'updated_at', 'emergency_contact'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'name', 'dateOfBirth']
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'dob': {'required': False, 'allow_null': True},
            'email': {'required': False, 'allow_null': True},
            'phone': {'required': False, 'allow_null': True},
            'age': {'required': False, 'allow_null': True},
            'address': {'required': False, 'allow_null': True},
            'city': {'required': False, 'allow_null': True},
            'pincode': {'required': False, 'allow_null': True},
            'aadhaar': {'required': False, 'allow_null': True},
            'remarks': {'required': False, 'allow_null': True},
            'emergency_contact': {'required': False, 'allow_null': True},
        }

    def get_name(self, obj):
        first_name = obj.first_name or ""
        last_name = obj.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        if not full_name:
            logger.warning(f"Patient ID {obj.id} has no first_name or last_name")
            return "Unnamed Patient"
        return full_name

    def validate_phone(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError('Phone number must contain only digits')
        if value and len(value) < 7:
            raise serializers.ValidationError('Phone number must be at least 7 digits')
        return value

    def validate(self, data):
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        if not first_name or not last_name:
            logger.error(f"Patient creation failed: first_name='{first_name}', last_name='{last_name}'")
            raise serializers.ValidationError("Both first_name and last_name are required.")
        return data

    def create(self, validated_data):
        patient = super().create(validated_data)
        logger.info(f"Patient created: {patient.first_name} {patient.last_name} (ID: {patient.id})")
        return patient

class ReportSerializer(serializers.ModelSerializer):
    generated_by = serializers.StringRelatedField()

    class Meta:
        model = Report
        fields = ['id', 'name', 'generated_by', 'generated_date', 'file_path', 'format']
        read_only_fields = ['id', 'generated_by', 'generated_date']

class GenerateReportSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=True)
    date_range_start = serializers.DateField(required=False, allow_null=True)
    date_range_end = serializers.DateField(required=False, allow_null=True)
    department = serializers.CharField(max_length=50, required=False, default='all')
    format = serializers.ChoiceField(choices=['pdf', 'excel', 'csv'], default='pdf')
    include_demographics = serializers.BooleanField(default=True)
    include_statistics = serializers.BooleanField(default=True)
    include_detailed_records = serializers.BooleanField(default=False)

class AppointmentSerializer(serializers.ModelSerializer):
    patient = AddPatientSerializer(read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=AddPatients.objects.all(),
        source='patient',
        write_only=True
    )
    doctor_name = serializers.CharField(source='doctor.get_full_name', read_only=True)
    patient_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_id', 'patient_name', 'doctor', 'doctor_name', 'date', 'time', 'duration',
            'type', 'status', 'symptoms', 'notes', 'createdAt', 'updatedAt'
        ]
        read_only_fields = ['id', 'createdAt', 'updatedAt', 'doctor', 'patient_name']

    def get_patient_name(self, obj):
        if obj.patient:
            patient_name = f"{obj.patient.first_name or ''} {obj.patient.last_name or ''}".strip()
            if not patient_name:
                logger.warning(f"Appointment ID {obj.id} has patient ID {obj.patient.id} with no name")
                return "Unnamed Patient"
            return patient_name
        logger.error(f"Appointment ID {obj.id} has no associated patient")
        return "Unknown Patient"

    def validate(self, data):
        if 'request' not in self.context or not self.context['request'].user.is_authenticated:
            logger.error("No authenticated user in AppointmentSerializer context")
            raise serializers.ValidationError("Authenticated user required to create appointment")
        patient = data.get('patient')
        if not patient:
            logger.error("No patient provided for appointment creation")
            raise serializers.ValidationError("Patient is required")
        if not patient.first_name or not patient.last_name:
            logger.warning(f"Patient ID {patient.id} has incomplete name: {patient.first_name} {patient.last_name}")
        return data

    def create(self, validated_data):
        doctor = self.context['request'].user
        if not doctor.is_authenticated:
            logger.error("Attempted to create appointment with unauthenticated user")
            raise serializers.ValidationError("Cannot create appointment without an authenticated user")
        if doctor.role not in ['doctor', 'nurse']:
            logger.error(f"User {doctor.id} with role {doctor.role} attempted to create appointment")
            raise serializers.ValidationError("Only doctors or nurses can create appointments")
        validated_data['doctor'] = doctor
        patient = validated_data['patient']
        logger.debug(f"Creating appointment for patient {patient.id} ({patient.first_name} {patient.last_name}) by user {doctor.id}")
        appointment = super().create(validated_data)
        logger.info(f"Appointment {appointment.id} created for patient {patient.id} ({patient.first_name} {patient.last_name})")
        return appointment

class InvitationSerializer(serializers.ModelSerializer):
    patient = AddPatientSerializer(read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    invitedDate = serializers.DateField(source='invited_date', read_only=True)
    invitedBy = serializers.CharField(source='doctor.get_full_name', read_only=True)
    preferredDates = serializers.JSONField(source='preferred_dates')
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=AddPatients.objects.all(),
        source='patient',
        write_only=True
    )

    class Meta:
        model = Invitation
        fields = ['id', 'patient', 'patient_id', 'doctor', 'invitedDate', 'preferredDates', 'status', 'createdAt', 'invitedBy']
        read_only_fields = ['id', 'doctor', 'invitedDate', 'createdAt']

    def validate(self, data):
        patient = data.get('patient')
        if not patient:
            logger.error("No patient provided for invitation creation")
            raise serializers.ValidationError("Patient is required")
        if not patient.first_name or not patient.last_name:
            logger.warning(f"Patient ID {patient.id} has incomplete name: {patient.first_name} {patient.last_name}")
        return data

    def create(self, validated_data):
        validated_data['doctor'] = self.context['request'].user
        invitation = super().create(validated_data)
        logger.info(f"Invitation {invitation.id} created for patient {invitation.patient.id} ({invitation.patient.first_name} {invitation.patient.last_name})")
        return invitation

class DiagnosticSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    patient = serializers.PrimaryKeyRelatedField(
        queryset=AddPatients.objects.all(),
        write_only=True
    )

    class Meta:
        model = Diagnostic
        fields = ['id', 'patient', 'patient_name', 'test_type', 'result', 'date', 'notes', 'status', 'created_by',
                  'created_by_name', 'created_at', 'updated_at']

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else 'Unknown'

class UserProfileSerializer(serializers.ModelSerializer):
    profile_image = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'role',
            'speciality', 'phone_number', 'license_number', 'profile_image'
        ]
        read_only_fields = ['id', 'username', 'role']

        def validate_profile_image(self, value):
            if value and len(value) > 2 * 1024 * 1024:  # ~2MB limit for base64
                raise serializers.ValidationError("Image is too large. Maximum size is 2MB.")
            return value

class LabReportSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=AddPatients.objects.all(),
        source='patient',
        write_only=True
    )
    file_url = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = LabReport
        fields = [
            'id', 'patient_id', 'patient_name', 'test_type', 'date',
            'notes', 'file', 'file_url', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'patient_name', 'created_by', 'created_at',
            'updated_at', 'file_url', 'created_by_name'
        ]

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else 'Unknown'

    def get_file_url(self, obj):
        if obj.file and hasattr(obj.file, 'url'):
            return obj.file.url
        return None


class MedicalHistorySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = MedicalHistory
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class VitalSignsSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)

    class Meta:
        model = VitalSigns
        fields = [
            'id', 'patient', 'recorded_at', 'blood_pressure_systolic',
            'blood_pressure_diastolic', 'heart_rate', 'temperature',
            'temperature_unit', 'respiratory_rate', 'oxygen_saturation',
            'weight', 'height', 'bmi', 'notes', 'recorded_by_name'
        ]
        read_only_fields = ['id', 'recorded_by_name', 'bmi']



class AllergySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = Allergy
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class ImmunizationSerializer(serializers.ModelSerializer):
    administered_by_name = serializers.CharField(source='administered_by.get_full_name', read_only=True)

    class Meta:
        model = Immunization
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class FamilyHistorySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = FamilyHistory
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class SocialHistorySerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)

    class Meta:
        model = SocialHistory
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class HealthCampaignSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = HealthCampaign
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_name']


class EducationalResourceSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = EducationalResource
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'author_name', 'file_url']

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None


class FeedbackSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)

    class Meta:
        model = Feedback
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_name', 'user_role','user']


class FeedbackResponseSerializer(serializers.ModelSerializer):
    responder_name = serializers.CharField(source='responder.get_full_name', read_only=True)
    responder_role = serializers.CharField(source='responder.role', read_only=True)

    class Meta:
        model = FeedbackResponse
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'responder_name', 'responder_role']


class SupportRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True, allow_null=True)

    class Meta:
        model = SupportRequest
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_name', 'user_role', 'assigned_to_name','user']


class SupportResponseSerializer(serializers.ModelSerializer):
    responder_name = serializers.CharField(source='responder.get_full_name', read_only=True)
    responder_role = serializers.CharField(source='responder.role', read_only=True)

    class Meta:
        model = SupportResponse
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'responder_name', 'responder_role']