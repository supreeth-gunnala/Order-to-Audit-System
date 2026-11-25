from django.urls import path
from . import views

app_name = 'production'

urlpatterns = [
    path('dashboard/', views.production_dashboard, name='dashboard'),
    path('boms/', views.bom_list, name='bom_list'),
    path('boms/<int:pk>/', views.bom_detail, name='bom_detail'),
    path('runs/', views.production_run_list, name='run_list'),
    path('runs/new/', views.production_run_create, name='run_create'),
    path('runs/<int:pk>/', views.production_run_detail, name='run_detail'),
]
