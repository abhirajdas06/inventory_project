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
    # Which list the machine belongs to (Rack Server, Storage, Networking
    # Switch, ...) — see apps.servers.groups. Set by the group's import option,
    # or inferred from Machine Type / Model.
    group        = models.CharField(max_length=40, blank=True, default='', db_index=True,
                                    choices=(
                                        ('blade_server', 'Blade Server'),
                                        ('cisco_chassis', 'Cisco Chassis'),
                                        ('desktop', 'Desktop'),
                                        ('hp_ibm_dell_chassis', 'HP-IBM-DELL Chassis'),
                                        ('rack_server', 'Rack Server'),
                                        ('storage', 'Storage'),
                                        ('sun_servers', 'Sun Servers'),
                                        ('networking_firewall', 'Networking Firewall'),
                                        ('networking_router_modem', 'Networking Router & Modem'),
                                        ('networking_switch', 'Networking Switch'),
                                    ))
    service_tag  = models.CharField(max_length=100, unique=True)
    # True when the import sheet had no System Service Tag No: service_tag then
    # holds a placeholder ("NOTAG-<Machine no>") purely so the machine's rows
    # can still be grouped and stored; lists show it as missing on hover.
    service_tag_missing = models.BooleanField(default=False)
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
