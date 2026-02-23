from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from championship import views
from rest_framework_simplejwt.views import TokenObtainPairView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('app/', include('championship.urls')),
    path('', views.index),
    path('api/auth/login/', TokenObtainPairView.as_view()),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
