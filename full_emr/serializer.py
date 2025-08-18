import re
from datetime import timedelta
from django.utils import timezone  # Fixed import
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User

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
        if not re.match(r'^\d{7,15}$', value):  # 7 to 15 digits
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

            # Set longer expiration if "remember me" is checked
            if attrs.get('remember_me'):
                access_token.set_exp(lifetime=timedelta(days=7))
                refresh.set_exp(lifetime=timedelta(days=30))

            # Add custom claims
            access_token['role'] = user.role
            access_token['email'] = user.email

            # Update last login info
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