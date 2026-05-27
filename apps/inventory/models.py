from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Product


class InventoryTransaction(models.Model):

    TRANSACTION_TYPE = (
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('AUDIT', 'Audit'),
    )

    STORE_LOCATION = (
        ('WH1', 'WH1'),
        ('WH2', 'WH2'),
        ('DELHI', 'Delhi'),
        ('BANGALORE', 'Bangalore'),
        ('HYDERABAD', 'Hyderabad'),
        ('CHENNAI', 'Chennai'),
        ('KOLKATA', 'Kolkata'),
    )

    STOCK_STATUS = (
        ('SALE', 'Sale'),
        ('TESTING', 'Testing'),
        ('RENT', 'Rent'),
        ('FAULTY', 'Faulty'),
        ('REPLACEMENT', 'Replacement'),
        ('ADV_REPLACEMENT', 'Adv Replacement'),
        ('ON_APPROVAL', 'On Approval'),
        ('EMPTY', 'Empty'),
        ('REFILL', 'Refill'),
        ('SCRAP', 'Scrap'),
        ('LIVE', 'Live'),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='transactions'
    )

    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)

    store_location = models.CharField(max_length=50, choices=STORE_LOCATION)
    stock_status = models.CharField(max_length=50, choices=STOCK_STATUS)

    # 🔹 Dates
    stock_in_date = models.DateField(null=True, blank=True)
    stock_out_date = models.DateField(null=True, blank=True)

    # 🔹 OUT fields
    client_name = models.CharField(max_length=255, null=True, blank=True)
    invoice_no = models.CharField(max_length=100, null=True, blank=True)

    # 🔹 AUDIT fields (UPDATED)
    audited_on = models.DateField(null=True, blank=True)

    audited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    audit_remark = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.serial_no} - {self.transaction_type}"