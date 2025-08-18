from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    DOCTOR = 'doctor'
    NURSE = 'nurse'
    PHARMACY = 'pharmacy'
    ROLE_CHOICES =[
        (DOCTOR,'Doctor'),
        (NURSE, 'Nurse'),
        (PHARMACY, 'Pharmacist'),
    ]
    role = models.CharField(max_length=10,choices=ROLE_CHOICES)
    speciality = models.CharField(max_length=20)
    phone_number = models.CharField(max_length=30)
    country_code = models.CharField(max_length=5)
    license_number = models.CharField(max_length=50, blank=True, null=True)

    last_login_ip = models.GenericIPAddressField(blank=True,null=True)
    last_login_at = models.DateTimeField(blank=True,null=True)

def __str__(self):
    return f"{self.get_full_name()} ({self.get_role_display()})"
# Create your models here.
