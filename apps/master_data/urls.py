from django.urls import path
from . import views

app_name = 'master_data'

urlpatterns = [
    path('products/', views.product_list, name='product_list'),
    path('customers/', views.customer_list, name='customer_list'),
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('uom/', views.uom_list, name='uom_list'),
]
