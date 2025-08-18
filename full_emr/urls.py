from django.urls import path
from .views import CreateAccountView, LoginView

urlpatterns = [
    path('register/', CreateAccountView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
]
# Allow credentials (cookies, authorization headers)
