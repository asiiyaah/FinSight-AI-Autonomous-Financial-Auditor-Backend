from django.urls import path
from .views import RegisterView
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView


urlpatterns=[
    path('register/',RegisterView.as_view(),name='register'),
    # The login endpoint to get your tokens
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # The endpoint to get a new access token using a refresh token
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
