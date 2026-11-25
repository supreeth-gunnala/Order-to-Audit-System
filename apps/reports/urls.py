from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('dashboard/', views.auditor_dashboard, name='auditor_dashboard'),
    path('sales-register/', views.sales_register, name='sales_register'),
    path('gst-outward/', views.gst_outward_report, name='gst_outward'),
    path('gstr3b/', views.gstr3b_report, name='gstr3b'),
    path('production-costing/', views.production_costing_report, name='production_costing'),
    path('receivables-ageing/', views.receivables_ageing_report, name='receivables_ageing'),
]
