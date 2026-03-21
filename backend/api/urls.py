from django.urls import path, include
from . import views


urlpatterns = [
  path('is_even/', views.is_even, name='is_even'),
  # Add your app urls here, for example:
  # path('myapp/', include('myapp.urls')),
]