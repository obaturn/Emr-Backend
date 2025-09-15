from django.urls import path
from . import chat_views

urlpatterns = [
    path('doctor/<int:doctor_id>/patients/', chat_views.get_doctor_patients, name='get_doctor_patients'),
    path('patient/<int:patient_id>/doctors/', chat_views.get_patient_doctors, name='get_patient_doctors'),
    path('users/<int:user_id>/', chat_views.get_user_profile, name='get_user_profile'),
    path('chat/history/<int:user1_id>/<int:user2_id>/', chat_views.get_chat_history, name='get_chat_history'),
    path('chat/send/', chat_views.send_message, name='send_message'),
    path('chat/conversations/', chat_views.get_conversations, name='get_conversations'),
    path('chat/user/<str:username>/', chat_views.get_user_info, name='get_user_info'),
]