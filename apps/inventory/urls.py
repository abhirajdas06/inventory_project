from django.urls import path
from . import views

urlpatterns = [
    path('stock-out/', views.stock_out, name='stock_out'),
    path('audit/', views.audit_spare, name='audit_spare'),
    path('audit-history/<int:product_id>/', views.audit_history, name='audit_history'),
    path('audit-report/', views.audit_report, name='audit_report'),
    path('check-membership/', views.check_product_membership, name='check_product_membership'),
]