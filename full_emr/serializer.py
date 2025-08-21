import re
from datetime import timedelta
from venv import logger

from django.utils import timezone
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password
from pip._internal.utils import logging
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, AddPatients, Report, Appointment, Invitation


user = get_user_model()

class CreateAccountSerializer(serializers.ModelSerializer):
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
            'phone_number', 'country_code', 'license_number'
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
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        style={'input_type': 'password'},
        trim_whitespace=False
    )
    remember_me = serializers.BooleanField(default=False, required=False)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(
                request=self.context.get('request'),
                username=email,
                password=password
            )

            if not user:
                raise serializers.ValidationError(
                    "Unable to login with provided credentials.",
                    code='authorization'
                )

            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            if attrs.get('remember_me'):
                access_token.set_exp(lifetime=timedelta(days=7))
                refresh.set_exp(lifetime=timedelta(days=30))

            access_token['role'] = user.role
            access_token['email'] = user.email

            user.last_login_ip = self.context['request'].META.get('REMOTE_ADDR')
            user.last_login_at = timezone.now()
            user.save()

            return {
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                    'speciality': user.speciality,
                },
                'tokens': {
                    'access': str(access_token),
                    'refresh': str(refresh),
                }
            }
        else:
            raise serializers.ValidationError(
                'Must include "email" and "password".',
                code='authorization'
            )

class AddPatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddPatients
        name = serializers.SerializerMethodField(read_only=True)
        dateOfBirth = serializers.DateField(source='dob', read_only=True)
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone', 'dob', 'age', 'gender',
            'address', 'city', 'pincode', 'aadhaar', 'remarks', 'category', 'created_at', 'updated_at','emergency_contact'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'dob': {'required': False, 'allow_null': True},
            'email': {'required': False, 'allow_null': True},
            'phone': {'required': False, 'allow_null': True},
            'age': {'required': False, 'allow_null': True},
            'address': {'required': False, 'allow_null': True},
            'city': {'required': False, 'allow_null': True},
            'pincode': {'required': False, 'allow_null': True},
            'aadhaar': {'required': False, 'allow_null': True},
            'remarks': {'required': False, 'allow_null': True},
        }

    def get_name(self, obj):
            return f"{obj.first_name} {obj.last_name}"
    def validate_phone(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError('Phone Number must contain only digits')
        if value and len(value) < 7:
            raise serializers.ValidationError('Phone number must be at least 7 digits')
        return value

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

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_id', 'doctor', 'doctor_name', 'date', 'time', 'duration',
            'type', 'status', 'symptoms', 'notes', 'createdAt', 'updatedAt'
        ]
        read_only_fields = ['id', 'createdAt', 'updatedAt', 'doctor']  # Doctor auto-set to current user on create

    def create(self, validated_data):
        # Auto-assign the current doctor (assuming the API caller is the doctor)
        validated_data['doctor'] = self.context['request'].user
        return super().create(validated_data)

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
        fields = ['id', 'patient', 'patient_id', 'doctor', 'invitedDate', 'preferredDates', 'status', 'createdAt','invitedBy']
        read_only_fields = ['id', 'doctor', 'invitedDate', 'createdAt']

        def create(self, validated_data):
            validated_data['doctor'] = self.context['request'].user
            return super().create(validated_data)


