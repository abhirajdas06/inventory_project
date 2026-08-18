# ============================================================
# apps/servers/models.py  — FULL SERVER MODULE
# ============================================================

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from apps.core.models import Product, SpareCategory, Brand


class Server(models.Model):
 
    MACHINE_TYPE_CHOICES = (
        ('RACK SERVER',  'Rack Server'),
        ('TOWER SERVER', 'Tower Server'),
        ('BLADE SERVER', 'Blade Server'),
        ('STORAGE',      'Storage'),
        ('OTHER',        'Other'),
    )
 
    STATUS_CHOICES = (
        ('WORKING',     'Working'),
        ('NOT WORKING', 'Not Working'),
        ('PARTIAL',     'Partial'),
        ('SCRAPPED',    'Scrapped'),
    )
 
    # ── Server identity ──────────────────────────────────────
    machine_type = models.CharField(
        max_length=50, choices=MACHINE_TYPE_CHOICES,
        null=True, blank=True
    )
    machine_no   = models.CharField(max_length=100, null=True, blank=True)
    service_tag  = models.CharField(max_length=100, unique=True)
    model        = models.CharField(max_length=255, null=True, blank=True)
 
    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL,
        null=True, blank=True
    )
 
    # ── Cabinet fields (same as Controller) ──────────────────
    part_no            = models.CharField(max_length=100, null=True, blank=True)
    alt_part_no        = models.CharField(max_length=100, null=True, blank=True)
    alt_serial_no      = models.CharField(max_length=100, null=True, blank=True)
    specs              = models.CharField(max_length=255, null=True, blank=True)
    qty                = models.IntegerField(default=1)
    barcode            = models.CharField(max_length=100, unique=True, null=True, blank=True)
 
    # ── Testing ───────────────────────────────────────────────
    testing_date = models.DateField(null=True, blank=True)
    tested_by    = models.CharField(max_length=255, null=True, blank=True)
 
    # ── Status ────────────────────────────────────────────────
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='WORKING'
    )
 
    # ── Location ──────────────────────────────────────────────
    location              = models.CharField(max_length=255, null=True, blank=True)
    reference_location    = models.CharField(max_length=255, null=True, blank=True)
    parent_child_location = models.CharField(max_length=255, null=True, blank=True)
    remark                = models.TextField(null=True, blank=True)
 
    # ── Inventory link ────────────────────────────────────────
    # The server/cabinet itself gets a Product entry + stock IN
    product = models.OneToOneField(
        Product, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='server'
    )
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        verbose_name        = "Server"
        verbose_name_plural = "Servers"
        ordering            = ['-created_at']
 
    def __str__(self):
        return f"{self.model} ({self.service_tag})"

    @property
    def component_count(self):
        return self.components.count()

    @property
    def sold_component_count(self):
        from apps.inventory.models import InventoryTransaction
        from django.db.models import OuterRef, Subquery
        latest = InventoryTransaction.objects.filter(
            product=OuterRef('product')
        ).order_by('-created_at').values('transaction_type')[:1]
        return self.components.annotate(
            lt=Subquery(latest)
        ).filter(lt='OUT').count()


class ServerComponent(models.Model):
    """
    Maps any Product (any category table) to a Server.
    Exactly mirrors how Spare.controller links to Controller.
    """
    server  = models.ForeignKey(
        Server, on_delete=models.CASCADE,
        related_name='components'
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='server_component'
    )
 
    spare_type            = models.CharField(max_length=100, null=True, blank=True)
    part_no               = models.CharField(max_length=100, null=True, blank=True)
    alt_part_no           = models.CharField(max_length=100, null=True, blank=True)
    serial_no             = models.CharField(max_length=100, null=True, blank=True)
    alt_serial_no         = models.CharField(max_length=100, null=True, blank=True)
    specs                 = models.CharField(max_length=255, null=True, blank=True)
    barcode               = models.CharField(max_length=100, null=True, blank=True)
    qty                   = models.IntegerField(default=1)
    working_status        = models.CharField(max_length=20, default='WORKING')
    location              = models.CharField(max_length=255, null=True, blank=True)
    reference_location    = models.CharField(max_length=255, null=True, blank=True)
    parent_child_location = models.CharField(max_length=255, null=True, blank=True)
    remark                = models.TextField(null=True, blank=True)
 
    attached_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
 
    class Meta:
        unique_together = ('server', 'product')
 
    def __str__(self):
        return f"{self.spare_type} → {self.server}"
