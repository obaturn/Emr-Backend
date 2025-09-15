import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from .models import Chat

User = get_user_model()

print("🔍 DEBUG CONSUMER LOADED - WebSocket consumer is being imported!")

class PrivateChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1. Get user IDs from URL and create room name
        self.user1_id = self.scope["url_route"]["kwargs"]["user1_id"]
        self.user2_id = self.scope["url_route"]["kwargs"]["user2_id"]
        print(f"[WS CONSUMER] Connecting to chat between users {self.user1_id} and {self.user2_id}")

        user_ids = sorted([int(self.user1_id), int(self.user2_id)])
        self.room_group_name = f"chat_{user_ids[0]}_{user_ids[1]}"
        print(f"[WS CONSUMER] Room group name: {self.room_group_name}")

        # 2. Check for JWT Token in query string (e.g., ?token=xyz)
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        print(f"[WS CONSUMER] Query string: {query_string}")

        token_key = None
        for part in query_string.split('&'):
            if part.startswith('token='):
                token_key = part.split('=')[1]
                break

        print(f"[WS CONSUMER] Token found: {token_key is not None}")
        print(f"[WS CONSUMER] Token length: {len(token_key) if token_key else 0}")

        if not token_key:
            print("[WS CONSUMER] No token provided - closing connection")
            await self.close(code=4403)  # Custom code for "No Token"
            return

        # 3. Validate JWT Token and get user
        print("[WS CONSUMER] Validating JWT token...")
        user = await self.get_user_from_token(token_key)
        print(f"[WS CONSUMER] User from token: {user}")
        print(f"[WS CONSUMER] User ID: {user.id if user and not isinstance(user, AnonymousUser) else 'None'}")

        if user is None or isinstance(user, AnonymousUser):
            print("[WS CONSUMER] Invalid token - closing connection")
            await self.close(code=4401)  # Custom code for "Invalid Token"
            return

        # 4. AUTHORIZATION: Check if the authenticated user is one of the chat participants
        print(f"[WS CONSUMER] Checking authorization for user {user.id} in chat between {self.user1_id} and {self.user2_id}")
        if user.id != int(self.user1_id) and user.id != int(self.user2_id):
            print(f"[WS CONSUMER] User {user.id} not authorized for chat between {self.user1_id} and {self.user2_id}")
            await self.close(code=4403)  # Custom code for "Not a Participant"
            return

        print(f"[WS CONSUMER] Authentication successful for user {user.id}")
        # 5. All checks passed, store user and accept connection
        self.scope["user"] = user
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print("[WS CONSUMER] WebSocket connection accepted!")

    async def disconnect(self, close_code):
        print(f"[WS CONSUMER] Disconnecting with code: {close_code}")
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """Receive a message from WebSocket, save it, then broadcast"""
        print(f"[WS CONSUMER] Received message: {text_data}")
        try:
            data = json.loads(text_data)
            message_text = data["message"]
            sender_id = str(self.scope["user"].id)  # Use the authenticated user's ID

            print(f"[WS CONSUMER] Processing message from user {sender_id}: {message_text}")

            # Save message in DB
            await self.save_message(sender_id, self.user2_id if sender_id == self.user1_id else self.user1_id, message_text)

            # Send to group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "sender": sender_id,
                    "message": message_text,
                }
            )
            print("[WS CONSUMER] Message broadcasted to group")
        except json.JSONDecodeError as e:
            print(f"[WS CONSUMER] JSON decode error: {e}")
            # Handle invalid JSON
            pass
        except KeyError as e:
            print(f"[WS CONSUMER] Missing key error: {e}")
            # Handle missing 'message' key
            pass

    async def chat_message(self, event):
        """Receive message from group and send to WebSocket"""
        print(f"[WS CONSUMER] Broadcasting message to WebSocket: {event}")
        await self.send(text_data=json.dumps({
            "sender": event["sender"],
            "message": event["message"],
        }))

    @database_sync_to_async
    def get_user_from_token(self, token_key):
        print(f"[WS CONSUMER] Decoding token: {token_key[:50]}...")
        try:
            access_token = AccessToken(token_key)
            user_id = access_token['user_id']
            print(f"[WS CONSUMER] Token decoded successfully, user_id: {user_id}")
            user = User.objects.get(id=user_id)
            print(f"[WS CONSUMER] User found: {user}")
            return user
        except (TokenError, InvalidToken) as e:
            print(f"[WS CONSUMER] Token validation error: {e}")
            return AnonymousUser()
        except User.DoesNotExist as e:
            print(f"[WS CONSUMER] User not found: {e}")
            return AnonymousUser()

    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, message):
        print(f"[WS CONSUMER] Saving message from {sender_id} to {receiver_id}")
        chat_message = Chat.objects.create(
            sender_id=int(sender_id),
            receiver_id=int(receiver_id),
            message=message
        )
        print(f"[WS CONSUMER] Message saved with ID: {chat_message.id}")
        return chat_message