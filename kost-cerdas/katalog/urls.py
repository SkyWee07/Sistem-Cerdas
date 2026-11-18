from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("kos/", views.kos_list, name="kos_list"),
    path("kos/<int:pk>/", views.kos_detail, name="kos_detail"),
    path("rekomendasi/", views.recommendations, name="recommendations"),
]
