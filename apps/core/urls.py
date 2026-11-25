from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard_router, name='dashboard_router'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('dashboard/', views.owner_dashboard, name='dashboard'),
    path('dashboard/owner/', views.owner_dashboard, name='owner_dashboard'),
    path('audit-trail/', views.audit_trail, name='audit_trail'),
]
