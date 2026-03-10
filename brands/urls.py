from django.urls import path

from . import views

app_name = "brands"

urlpatterns = [
    path("", views.home, name="home"),
    path("brands/live-search/", views.live_search, name="live_search"),
    path("brands/selected-brand/", views.selected_brand, name="selected_brand"),
    path("brands/<int:pk>/detail/", views.brand_detail, name="brand_detail"),
    path("healthz", views.healthz, name="healthz"),
    path("healthz/", views.healthz),
]
