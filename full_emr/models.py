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
    profile_image = models.TextField(blank=True, null=True)

    last_login_ip = models.GenericIPAddressField(blank=True,null=True)
    last_login_at = models.DateTimeField(blank=True,null=True)

def __str__(self):
    return f"{self.get_full_name()} ({self.get_role_display()})"
# Create your models here.

class AddPatients(models.Model):
    CATEGORY_CHOICES = [
        ("General", "General"),
        ("Emergency", "Emergency"),
        ("OPD", "OPD"),
        ("VIP", "VIP"),
    ]
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    dob = models.DateField(null=True,blank=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=[("Male","Male"),("Female","Female"),("Other","Other")],default='Male')
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    aadhaar = models.CharField(max_length=12, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=20,choices=CATEGORY_CHOICES, default='General')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    emergency_contact = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Report(models.Model):
    name = models.CharField(max_length=100)
    generated_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True, related_name='generated_reports')
    generated_date = models.DateTimeField(auto_now_add=True)
    file_path = models.FileField(upload_to='reports/')
    parameters = models.JSONField(null=True, blank=True)
    format = models.CharField(max_length=10, choices=[('pdf', 'PDF'), ('excel', 'Excel'), ('csv', 'CSV')],
                              default='pdf')

    def __str__(self):
        return f"{self.name} - {self.generated_date}"

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('Scheduled', 'Scheduled'),
        ('Confirmed', 'Confirmed'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]
    TYPE_CHOICES = [
        ('Consultation', 'Consultation'),
        ('Follow-up', 'Follow-up'),
        ('Emergency', 'Emergency'),
        ('Routine Check', 'Routine Check'),
        ('Surgery', 'Surgery'),
        ('Lab Test', 'Lab Test'),
    ]
    patient = models.ForeignKey(AddPatients, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='appointments',
                               limit_choices_to={'role': 'doctor'})
    date = models.DateField()
    time = models.TimeField()
    duration = models.PositiveIntegerField(default=30)  # in minutes
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='Consultation')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Scheduled')
    symptoms = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Appointment for {self.patient} on {self.date} at {self.time}"

class Invitation(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Accepted', 'Accepted'),
        ('Declined', 'Declined'),
        ('Expired', 'Expired'),
    ]
    patient = models.ForeignKey(AddPatients, on_delete=models.CASCADE)
    doctor = models.ForeignKey(User, on_delete=models.CASCADE)
    invited_date = models.DateField(auto_now_add=True)
    preferred_dates = models.JSONField(default=list)  # e.g., ["2025-08-21", "2025-08-22"]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)


class Diagnostic(models.Model):
    patient = models.ForeignKey('AddPatients', on_delete=models.CASCADE, related_name='diagnostics')
    test_type = models.CharField(max_length=100)  # e.g., Blood Test, X-Ray
    result = models.TextField(blank=True)  # Test results or findings
    date = models.DateField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('abnormal', 'Abnormal'),
    ], default='pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.test_type} for {self.patient.first_name} {self.patient.last_name} on {self.date}"

class LabReport(models.Model):
    patient = models.ForeignKey(AddPatients, on_delete=models.CASCADE, related_name='lab_reports')
    test_type = models.CharField(max_length=100)
    date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='lab_reports/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='lab_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.test_type} for {self.patient.first_name} {self.patient.last_name} on {self.date}"
