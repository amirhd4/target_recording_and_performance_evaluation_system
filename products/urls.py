from django.urls import path
from . import views

urlpatterns = [
    path("", views.projects_products_list, name="projects_products"),
]