from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

class User(AbstractUser):
    DOCTOR = 'doctor'
    NURSE = 'nurse'
    PHARMACY = 'pharmacy'
    PATIENT = 'patient'
    ROLE_CHOICES =[
        (DOCTOR,'Doctor'),
        (NURSE, 'Nurse'),
        (PHARMACY, 'Pharmacist'),
        (PATIENT,'patient')
    ]
    role = models.CharField(max_length=10,choices=ROLE_CHOICES)
    speciality = models.CharField(max_length=20,blank=True, null=True)
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
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('reviewed', 'Reviewed'),
    ], default='pending')

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.test_type} for {self.patient.first_name} {self.patient.last_name} on {self.date}"

class MedicalHistory(models.Model):
    patient = models.ForeignKey(AddPatients, on_delete=models.CASCADE, related_name='medical_history')
    condition = models.CharField(max_length=200)
    diagnosis_date = models.DateField()
    status = models.CharField(max_length=50, choices=[
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('chronic', 'Chronic')
    ])
    severity = models.CharField(max_length=50, choices=[
        ('mild', 'Mild'),
        ('moderate', 'Moderate'),
        ('severe', 'Severe')
    ])
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class VitalSigns(models.Model):
    patient = models.ForeignKey(AddPatients, on_delete=models.CASCADE, related_name='vital_signs')
    recorded_at = models.DateTimeField()
    blood_pressure_systolic = models.IntegerField(null=True, blank=True)
    blood_pressure_diastolic = models.IntegerField(null=True, blank=True)
    heart_rate = models.IntegerField(null=True, blank=True)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    temperature_unit = models.CharField(max_length=10, default='C')
    respiratory_rate = models.IntegerField(null=True, blank=True)
    oxygen_saturation = models.IntegerField(null=True, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    bmi = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)

class Allergy(models.Model):
    patient = models.ForeignKey(AddPatients, on_delete=models.CASCADE, related_name='allergies')
    allergen = models.CharField(max_length=200)
    allergy_type = models.CharField(max_length=50, choices=[
        ('drug', 'Drug'),
        ('food', 'Food'),
        ('environmental', 'Environmental'),
        ('other', 'Other')
    ])
    severity = models.CharField(max_length=50, choices=[
        ('mild', 'Mild'),
        ('moderate', 'Moderate'),
        ('severe', 'Severe'),
        ('life_threatening', 'Life Threatening')
    ])
    reaction = models.TextField()
    diagnosed_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=[
        ('active', 'Active'),
        ('resolved', 'Resolved')
    ], default='active')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Immunization(models.Model):
    patient = models.ForeignKey(AddPatients, on_delete=models.CASCADE, related_name='immunizations')
    vaccine_name = models.CharField(max_length=200)
    vaccine_code = models.CharField(max_length=20, blank=True)
    administered_date = models.DateField()
    administered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    dose_number = models.IntegerField(null=True, blank=True)
    total_doses = models.IntegerField(null=True, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    lot_number = models.CharField(max_length=50, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    site = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class FamilyHistory(models.Model):
    patient = models.ForeignKey(AddPatients, on_delete=models.CASCADE, related_name='family_history')
    relationship = models.CharField(max_length=50, choices=[
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('grandfather', 'Grandfather'),
        ('grandmother', 'Grandmother'),
        ('uncle', 'Uncle'),
        ('aunt', 'Aunt'),
        ('other', 'Other')
    ])
    condition = models.CharField(max_length=200)
    age_at_diagnosis = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=[
        ('living', 'Living'),
        ('deceased', 'Deceased')
    ])
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SocialHistory(models.Model):
    patient = models.ForeignKey(AddPatients, on_delete=models.CASCADE, related_name='social_history')
    occupation = models.CharField(max_length=100, blank=True)
    marital_status = models.CharField(max_length=50, choices=[
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
        ('separated', 'Separated')
    ], blank=True)
    education_level = models.CharField(max_length=50, blank=True)
    smoking_status = models.CharField(max_length=50, choices=[
        ('never', 'Never Smoked'),
        ('former', 'Former Smoker'),
        ('current', 'Current Smoker')
    ], blank=True)
    alcohol_use = models.CharField(max_length=50, choices=[
        ('none', 'None'),
        ('occasional', 'Occasional'),
        ('moderate', 'Moderate'),
        ('heavy', 'Heavy')
    ], blank=True)
    exercise_frequency = models.CharField(max_length=50, choices=[
        ('none', 'None'),
        ('rare', 'Rare'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily')
    ], blank=True)
    diet_type = models.CharField(max_length=50, blank=True)
    living_arrangements = models.TextField(blank=True)
    support_system = models.TextField(blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)


class HealthCampaign(models.Model):
    CAMPAIGN_STATUS = [
        ('active', 'Active'),
        ('upcoming', 'Upcoming'),
        ('completed', 'Completed'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100)  # e.g., 'Prevention', 'Awareness', 'Mental Health'
    target_audience = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=CAMPAIGN_STATUS, default='upcoming')
    participants = models.PositiveIntegerField(default=0)
    image_url = models.URLField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class EducationalResource(models.Model):
    RESOURCE_TYPES = [
        ('article', 'Article'),
        ('video', 'Video'),
        ('infographic', 'Infographic'),
        ('guide', 'Guide'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    content = models.TextField(blank=True)  # For article content
    video_url = models.URLField(blank=True, null=True)
    file = models.FileField(upload_to='resources/', blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    publish_date = models.DateField(auto_now_add=True)
    read_time = models.PositiveIntegerField(default=5)  # in minutes
    views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Feedback(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    category = models.CharField(max_length=100, default='General')
    rating = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.subject} - {self.user.get_full_name()}"


class FeedbackResponse(models.Model):
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, related_name='responses')
    responder = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Response to {self.feedback.subject}"


class SupportRequest(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in-progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100, default='General')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='assigned_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.subject} - {self.user.get_full_name()}"


class SupportResponse(models.Model):
    support_request = models.ForeignKey(SupportRequest, on_delete=models.CASCADE, related_name='responses')
    responder = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Response to {self.support_request.subject}"