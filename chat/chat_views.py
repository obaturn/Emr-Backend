from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.apps import apps  # Add this import
from django.db.models import Q
import json

from .models import Chat

User = get_user_model()


def get_appointment_model():
    return apps.get_model('full_emr', 'Appointment')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_history(request, user1_id, user2_id):
    try:
        messages = Chat.objects.filter(
            Q(sender_id=user1_id, receiver_id=user2_id) |
            Q(sender_id=user2_id, receiver_id=user1_id)
        ).order_by('timestamp')

        message_data = [{
            'id': msg.id,
            'sender': msg.sender_id,
            'receiver': msg.receiver_id,
            'message': msg.message,
            'timestamp': msg.timestamp.isoformat()
        } for msg in messages]

        return Response(message_data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctor_patients(request, doctor_id):
    try:
        Appointment = get_appointment_model()
        appointments = Appointment.objects.filter(doctor_id=doctor_id).select_related('patient')
        patients = list(set([apt.patient for apt in appointments]))

        patient_data = [{
            'id': patient.id,
            'first_name': patient.first_name,
            'last_name': patient.last_name,
            'email': patient.email,
            'phone': patient.phone,
            'category': patient.category,
        } for patient in patients]

        return Response(patient_data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_doctors(request, patient_id):
    """Get list of doctors for a patient"""
    try:
        Appointment = get_appointment_model()
        appointments = Appointment.objects.filter(patient_id=patient_id).select_related('doctor')
        doctors = list(set([apt.doctor for apt in appointments if apt.doctor]))

        doctor_data = [{
            'id': doctor.id,
            'first_name': doctor.first_name,
            'last_name': doctor.last_name,
            'speciality': doctor.speciality,
            'role': doctor.role,
        } for doctor in doctors]

        return Response(doctor_data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request):
    """Send a chat message"""
    try:
        data = json.loads(request.body)
        sender_id = data.get('sender')
        receiver_id = data.get('receiver')
        message = data.get('message')

        if request.user.id != sender_id:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        chat_message = Chat.objects.create(
            sender=User.objects.get(id=sender_id),
            receiver=User.objects.get(id=receiver_id),
            message=message
        )

        return Response({
            'id': chat_message.id,
            'sender': chat_message.sender_id,
            'receiver': chat_message.receiver_id,
            'message': chat_message.message,
            'timestamp': chat_message.timestamp.isoformat()
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request, user_id):
    """Get user profile information"""
    try:
        user = User.objects.get(id=user_id)
        return Response({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'speciality': user.speciality,
            'profile_image': user.profile_image,
        })
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversations(request):
    """List all chat conversations for a user"""
    user = request.user
    chats = Chat.objects.filter(Q(sender=user) | Q(receiver=user))
    participants = set()
    for chat in chats:
        participants.add(chat.sender)
        participants.add(chat.receiver)
    participants.discard(user)
    data = [{'id': u.id, 'first_name': u.first_name, 'last_name': u.last_name} for u in participants]
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_info(request, username):
    """Fetch user by username"""
    try:
        user = User.objects.get(username=username)
        return Response({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
        })
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)