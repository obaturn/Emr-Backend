from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView

def home(request):
    return JsonResponse({"message": "EMR backend is running"})

urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),
    path('api/', include('full_emr.urls')),
    path('api/', include('chat.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # All urls from full_emr app will be prefixed with /api/
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)