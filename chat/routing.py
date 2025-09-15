from django.urls import re_path
from . import consumer  # <- FIXED THE IMPORT (lowercase 'c')

# Use this improved regex to only match digits for user IDs
websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<user1_id>\d+)/(?P<user2_id>\d+)/$", consumer.PrivateChatConsumer.as_asgi()),
]