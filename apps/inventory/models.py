from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Product
from django.utils import timezone


class InventoryTransaction(models.Model):

    TRANSACTION_TYPE = (
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('AUDIT', 'Audit'),
    )

    AUDIT_RESULT = (
        ('FOUND', 'Found'),
        ('NOT_FOUND', 'Not Found'),
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
        ('DAMAGED', 'Damaged'),
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
    olf_dc_number = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    # 🔹 AUDIT fields (UPDATED)
    audited_on = models.DateField(null=True, blank=True)

    audited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audited_transactions'
    )

    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_transactions'
    )

    audit_remark = models.TextField(null=True, blank=True)
    audit_result = models.CharField(max_length=20, choices=AUDIT_RESULT, null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # "latest transaction per product" lookups drive every list view.
            models.Index(fields=['product', '-created_at'], name='invtxn_prod_created_idx'),
            models.Index(fields=['product', 'transaction_type', '-created_at'], name='invtxn_prod_type_idx'),
            models.Index(fields=['transaction_type', 'stock_status'], name='invtxn_type_status_idx'),
        ]

    def __str__(self):
        return f"{self.product.serial_no} - {self.transaction_type}"


class InventoryTransfer(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='transfers'
    )
    source_warehouse = models.CharField(max_length=50, choices=InventoryTransaction.STORE_LOCATION)
    destination_warehouse = models.CharField(max_length=50, choices=InventoryTransaction.STORE_LOCATION)
    source_location = models.CharField(max_length=255, blank=True)
    destination_location = models.CharField(max_length=255, blank=True)
    remarks = models.TextField()
    transferred_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_transfers'
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product_id}:{self.source_warehouse}->{self.destination_warehouse}"


class SalesReturn(models.Model):
    REASON_CHOICES = (
        ('NORMAL', 'Normal return'),
        ('FAULTY', 'Faulty'),
        ('DAMAGED', 'Damaged'),
    )
    DISPOSITION_CHOICES = (
        ('LIVE', 'Return to stock'),
        ('FAULTY', 'Move to faulty stock'),
        ('SCRAP', 'Move to scrap'),
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales_returns')
    stock_out_transaction = models.ForeignKey(InventoryTransaction, on_delete=models.PROTECT, related_name='sales_returns')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    disposition = models.CharField(max_length=20, choices=DISPOSITION_CHOICES)
    remarks = models.TextField(blank=True)
    returned_on = models.DateField(default=timezone.localdate)
    returned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_sales_returns')
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-created_at']


class TransferRequest(models.Model):
    STATUS_CHOICES = (('PENDING', 'Pending receipt'), ('PARTIAL', 'Partially received'), ('COMPLETED', 'Completed'))
    source_warehouse = models.CharField(max_length=50, choices=InventoryTransaction.STORE_LOCATION)
    destination_warehouse = models.CharField(max_length=50, choices=InventoryTransaction.STORE_LOCATION)
    remarks = models.TextField(blank=True)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='transfer_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'TR-{self.pk}'


class TransferRequestItem(models.Model):
    request = models.ForeignKey(TransferRequest, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='transfer_request_items')
    barcode = models.CharField(max_length=100, db_index=True)
    source_location = models.CharField(max_length=255, blank=True)
    destination_location = models.CharField(max_length=255, blank=True)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_transfer_items')
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('request', 'product'), name='unique_transfer_request_product')]


class InventoryFreezeRecord(models.Model):
    STATUS_CHOICES = (
        ('FROZEN', 'Frozen'),
        ('UNFROZEN', 'Unfrozen'),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='freeze_records'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='FROZEN')
    reason = models.TextField()
    frozen_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='frozen_inventory'
    )
    unfrozen_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unfrozen_inventory'
    )
    frozen_at = models.DateTimeField(default=timezone.now, editable=False)
    unfrozen_at = models.DateTimeField(null=True, blank=True)
    parent_product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_freeze_records'
    )

    class Meta:
        ordering = ['-frozen_at']
        indexes = [
            models.Index(fields=['product', '-frozen_at'], name='freeze_prod_frozen_idx'),
        ]

    def __str__(self):
        return f"{self.product_id}:{self.status}"


class RentalRecord(models.Model):
    STATUS_CHOICES = (
        ('ON_RENT', 'On Rent'),
        ('RETURNED', 'Returned'),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='rental_records',
    )
    client_name = models.CharField(max_length=255, blank=True)
    invoice_no = models.CharField(max_length=100, blank=True)
    olf_dc_number = models.CharField(max_length=100, blank=True, db_index=True)
    store_location = models.CharField(max_length=50, blank=True)

    rent_out_date = models.DateField(null=True, blank=True)
    expected_return_date = models.DateField(null=True, blank=True)
    actual_return_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ON_RENT', db_index=True)

    rented_out_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rented_out_records',
    )
    returned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='returned_rental_records',
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-rent_out_date', '-id']

    def __str__(self):
        return f"Rental:{self.product_id}:{self.status}"


class AuditFinding(models.Model):
    audit_date = models.DateField()
    remarks = models.TextField()
    attachment = models.FileField(upload_to='audit_findings/', null=True, blank=True)
    person_involved = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_findings'
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-audit_date', '-id']

    def __str__(self):
        return f"AuditFinding:{self.id}"


class GeneralAuditFinding(models.Model):
    STATUS_CHOICES = (
        ('OPEN', 'Open'),
        ('ATTENDED', 'Attended'),
    )

    audit_date = models.DateField()
    title = models.CharField(max_length=255)
    remarks = models.TextField()
    attachment = models.FileField(upload_to='general_audit_findings/', null=True, blank=True)
    person = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='general_audit_findings'
    )
    attended_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attended_general_audit_findings'
    )
    attended_at = models.DateTimeField(null=True, blank=True)
    attended_remarks = models.TextField(blank=True)
    attended_attachment = models.FileField(upload_to='general_audit_findings/attended/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-audit_date', '-id']

    def __str__(self):
        return self.title
