from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('stock/', views.stock_summary, name='stock_summary'),
    path('ledger/', views.stock_ledger_view, name='stock_ledger'),
    path('purchases/', views.purchase_list, name='purchase_list'),
    path('purchases/new/', views.purchase_create, name='purchase_create'),
    path('items/new/', views.item_create, name='item_create'),
]
