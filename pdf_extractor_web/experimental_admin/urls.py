from django.urls import path
from . import views

app_name = "experimental_admin"

urlpatterns = [
    path("", views.index, name="index"),
    path("transactions/", views.transaction_list, name="transaction_list"),
    path("tasks/", views.task_list, name="task_list"),
]
