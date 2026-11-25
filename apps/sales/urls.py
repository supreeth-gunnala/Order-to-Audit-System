from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('salesman/', views.salesman_dashboard, name='salesman_dashboard'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/new/', views.order_create, name='order_create'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/action/', views.order_review_action, name='order_review_action'),
    path('orders/<int:pk>/generate-invoice/', views.order_generate_invoice, name='order_generate_invoice'),
    path('orders/<int:order_id>/dispatch/', views.dispatch_create, name='dispatch_create'),
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/pdf/', views.invoice_pdf_view, name='invoice_pdf_view'),
    path('invoices/<int:pk>/credit-note/', views.invoice_credit_note, name='invoice_credit_note'),
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/new/', views.payment_create, name='payment_create'),
]
