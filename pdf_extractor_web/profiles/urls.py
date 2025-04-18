from django.urls import path
from . import views

urlpatterns = [
    path("upload-transactions/", views.upload_transactions, name="upload-transactions"),
    path("", views.BusinessProfileListView.as_view(), name="profile-list"),
]
