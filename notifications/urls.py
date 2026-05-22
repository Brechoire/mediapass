from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.email_admin, name="email_admin"),
    path("templates/<int:pk>/", views.email_template_edit, name="email_template_edit"),
    path("recipients/ajouter/", views.recipient_add, name="recipient_add"),
    path("recipients/<int:pk>/", views.recipient_edit, name="recipient_edit"),
    path("recipients/<int:pk>/supprimer/", views.recipient_delete, name="recipient_delete"),
]
