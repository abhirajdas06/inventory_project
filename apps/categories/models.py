from django.db import models
from django.utils import timezone
from apps.core.models import Product, Brand


class Spare(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='spare'
    )

    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    controller = models.ForeignKey(
      'Controller',
      on_delete=models.SET_NULL,
      null=True,
      blank=True,
      related_name='components'
    )

    model = models.CharField(max_length=100, null=True, blank=True)

    part_no = models.CharField(max_length=100, null=True, blank=True)
    alt_part_no = models.CharField(max_length=100, null=True, blank=True)

    alt_serial_no = models.CharField(max_length=100, null=True, blank=True)

    specs = models.CharField(max_length=255, null=True, blank=True)

    qty = models.IntegerField(default=1)

    barcode = models.CharField(max_length=100, null=True, blank=True, unique=True)

    location = models.CharField(max_length=255, null=True, blank=True)
    reference_location = models.CharField(max_length=255, null=True, blank=True)

    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Battery"
        verbose_name_plural = "Battery"

    def __str__(self):
        return self.product.name
    

class Card(models.Model):

    INTERFACE_CHOICES = (
        ('SAS', 'SAS'),
        ('SATA', 'SATA'),
        ('FC', 'FC'),
        ('SCSI', 'SCSI'),
    )

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='card'
    )

    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    oem = models.CharField(max_length=100, null=True, blank=True)
    brand_model_no = models.CharField(max_length=100, null=True, blank=True)

    # ✅ UPDATED
    interface = models.CharField(
        max_length=100,
        choices=INTERFACE_CHOICES,
        null=True,
        blank=True
    )

    part_no = models.CharField(max_length=100, null=True, blank=True)
    alt_part_no = models.CharField(max_length=100, null=True, blank=True)

    brand_serial_no_1 = models.CharField(max_length=100, null=True, blank=True)

    capacity = models.CharField(max_length=50, null=True, blank=True)
    port = models.CharField(max_length=50, null=True, blank=True)

    barcode = models.CharField(max_length=100, null=True, blank=True, unique=True)

    location = models.CharField(max_length=255, null=True, blank=True)
    reference_location = models.CharField(max_length=255, null=True, blank=True)

    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Card"
        verbose_name_plural = "Cards"
        
        
class CPU(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='cpu'
    )

    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    model = models.CharField(max_length=100, null=True, blank=True)
    part_no = models.CharField(max_length=100, null=True, blank=True)

    no_of_cores = models.CharField(max_length=20, null=True, blank=True)
    no_of_threads = models.CharField(max_length=20, null=True, blank=True)
    ghz = models.CharField(max_length=20, null=True, blank=True)
    frequency = models.CharField(max_length=50, null=True, blank=True)
    cache = models.CharField(max_length=50, null=True, blank=True)

    barcode = models.CharField(max_length=100, null=True, blank=True, unique=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    reference_location = models.CharField(max_length=255, null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "CPU"
        verbose_name_plural = "CPUs"

    def __str__(self):
        return self.product.name



class Controller(models.Model):
    """
    Represents a Cabinet (parent) that groups spare components.
    Each Controller has one Product (the cabinet itself) and
    multiple Spare entries linked back via spare.controller FK.
    """
 
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='controller'
    )
 
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
 
    model = models.CharField(max_length=100, null=True, blank=True)
 
    part_no = models.CharField(max_length=100, null=True, blank=True)
    alt_part_no = models.CharField(max_length=100, null=True, blank=True)
 
    alt_serial_no = models.CharField(max_length=100, null=True, blank=True)
 
    specs = models.CharField(max_length=255, null=True, blank=True)
 
    qty = models.IntegerField(default=1)
 
    barcode = models.CharField(max_length=100, null=True, blank=True, unique=True)
 
    location = models.CharField(max_length=255, null=True, blank=True)
    reference_location = models.CharField(max_length=255, null=True, blank=True)
    parent_child_location = models.CharField(max_length=255, null=True, blank=True)
 
    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
 
    class Meta:
        verbose_name = "Controller"
        verbose_name_plural = "Controllers"
 
    def __str__(self):
        return self.product.name
    

class Memory(models.Model):
 
    RAM_TYPE_CHOICES = (
        ('ECC REGD',  'ECC Registered'),
        ('FB DIMM',   'FB DIMM'),
        ('ECC UDIMM', 'ECC UDIMM'),
        ('UDIMM',     'UDIMM'),
        ('RDIMM',     'RDIMM'),
        ('LRDIMM',    'LRDIMM'),
    )
 
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='memory'
    )
 
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
 
    oem   = models.CharField(max_length=100, null=True, blank=True)
    model = models.CharField(max_length=100, null=True, blank=True)
 
    part_no_1 = models.CharField(max_length=100, null=True, blank=True)
    part_no_2 = models.CharField(max_length=100, null=True, blank=True)
    part_no_3 = models.CharField(max_length=100, null=True, blank=True)
 
    size        = models.CharField(max_length=20,  null=True, blank=True)
    ram_type    = models.CharField(max_length=20,  choices=RAM_TYPE_CHOICES, null=True, blank=True)
    ddr_version = models.CharField(max_length=20,  null=True, blank=True)   # e.g. PC3
    frequency   = models.CharField(max_length=30,  null=True, blank=True)   # e.g. 12800R
    rank        = models.CharField(max_length=20,  null=True, blank=True)   # e.g. 2R*4
 
    qty     = models.IntegerField(default=1)
    barcode = models.CharField(max_length=100, null=True, blank=True, unique=True)
 
    location           = models.CharField(max_length=255, null=True, blank=True)
    reference_location = models.CharField(max_length=255, null=True, blank=True)
    remark             = models.TextField(null=True, blank=True)
    created_at         = models.DateTimeField(default=timezone.now, editable=False)
 
    class Meta:
        verbose_name        = "Memory"
        verbose_name_plural = "Memory"
 
    def __str__(self):
        return self.product.name
    
class SFP(models.Model):
 
    FIBRE_TYPE_CHOICES = (
        ('SMF', 'SMF - Single Mode Fibre'),
        ('MMF', 'MMF - Multi Mode Fibre'),
    )
 
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='sfp'
    )
 
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
 
    model       = models.CharField(max_length=100, null=True, blank=True)
    part_no     = models.CharField(max_length=100, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
 
    fibre_type  = models.CharField(
        max_length=100,
        choices=FIBRE_TYPE_CHOICES,
        null=True,
        blank=True
    )
 
    data_rate   = models.CharField(max_length=50,  null=True, blank=True)  # e.g. 10GBPS
 
    barcode            = models.CharField(max_length=100, null=True, blank=True, unique=True)
    location           = models.CharField(max_length=255, null=True, blank=True)
    reference_location = models.CharField(max_length=255, null=True, blank=True)
    remark             = models.TextField(null=True, blank=True)
    created_at         = models.DateTimeField(default=timezone.now, editable=False)
 
    class Meta:
        verbose_name        = "SFP"
        verbose_name_plural = "SFPs"
 
    def __str__(self):
        return self.product.name
    

class RailKit(models.Model):
 
    SIDE_CHOICES = (
        ('LEFT',  'Left'),
        ('RIGHT', 'Right'),
        ('PAIR',  'Pair'),
    )
 
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='railkit'
    )
 
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
 
    side            = models.CharField(
                          max_length=100,
                          choices=SIDE_CHOICES,
                          null=True,
                          blank=True
                      )
    part_no         = models.CharField(max_length=100, null=True, blank=True)
    specs           = models.CharField(max_length=255, null=True, blank=True)
    supported_model = models.CharField(max_length=255, null=True, blank=True)
    qty             = models.IntegerField(default=1)
 
    barcode            = models.CharField(max_length=100, null=True, blank=True, unique=True)
    location           = models.CharField(max_length=255, null=True, blank=True)
    reference_location = models.CharField(max_length=255, null=True, blank=True)
    remark             = models.TextField(null=True, blank=True)
    created_at         = models.DateTimeField(default=timezone.now, editable=False)
 
    class Meta:
        verbose_name        = "Rail Kit"
        verbose_name_plural = "Rail Kits"
 
    def __str__(self):
        return self.product.name
    
    
    
class HardDisk(models.Model):
 
    INTERFACE_CHOICES = (
        ('SAS',  'SAS'),
        ('SATA', 'SATA'),
        ('FC',   'FC'),
        ('NVMe', 'NVMe'),
    )
 
    SIZE_CHOICES = (
        ('2.5', '2.5 inch'),
        ('3.5', '3.5 inch'),
    )
 
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='harddisk'
    )
 
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
 
    oem            = models.CharField(max_length=100, null=True, blank=True)
    brand_model_no = models.CharField(max_length=100, null=True, blank=True)
    oem_model_no   = models.CharField(max_length=100, null=True, blank=True)
 
    capacity  = models.CharField(max_length=20,  null=True, blank=True)   # e.g. 1TB
    rpm       = models.CharField(max_length=20,  null=True, blank=True)   # e.g. 7.2K
    interface = models.CharField(
                    max_length=100,
                    choices=INTERFACE_CHOICES,
                    null=True, blank=True
                )
    size      = models.CharField(
                    max_length=100,
                    choices=SIZE_CHOICES,
                    null=True, blank=True
                )
 
    part_no     = models.CharField(max_length=100, null=True, blank=True)
    alt_part_no = models.CharField(max_length=100, null=True, blank=True)
 
    alt_fru_1   = models.CharField(max_length=100, null=True, blank=True)
    alt_fru_2   = models.CharField(max_length=100, null=True, blank=True)
    alt_fru_3   = models.CharField(max_length=100, null=True, blank=True)
 
    retail_part_no = models.CharField(max_length=100, null=True, blank=True)
    spare_part_tray= models.CharField(max_length=100, null=True, blank=True)
    gpn_code       = models.CharField(max_length=100, null=True, blank=True)
 
    brand_serial_no = models.CharField(max_length=100, null=True, blank=True)
    oem_serial_no   = models.CharField(max_length=100, null=True, blank=True)
 
    firmware = models.CharField(max_length=50,  null=True, blank=True)
    health   = models.CharField(max_length=20,  null=True, blank=True)   # e.g. 100%
    gb_s     = models.CharField(max_length=20,  null=True, blank=True)   # e.g. 6GBPS
 
    barcode      = models.CharField(max_length=100, null=True, blank=True, unique=True)
    tray_barcode = models.CharField(max_length=100, null=True, blank=True)
 
    location           = models.CharField(max_length=255, null=True, blank=True)
    reference_location = models.CharField(max_length=255, null=True, blank=True)
    remark             = models.TextField(null=True, blank=True)
    created_at         = models.DateTimeField(default=timezone.now, editable=False)
 
    class Meta:
        verbose_name        = "Hard Disk"
        verbose_name_plural = "Hard Disks"
 
    def __str__(self):
        return self.product.name


class NetworkingSpare(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='networking_spare'
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    part_no = models.CharField(max_length=100, null=True, blank=True)
    alt_part_no = models.CharField(max_length=100, null=True, blank=True)
    alt_serial_no = models.CharField(max_length=100, null=True, blank=True)
    specs = models.CharField(max_length=255, null=True, blank=True)
    qty = models.IntegerField(default=1)
    barcode = models.CharField(max_length=100, null=True, blank=True, unique=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    reference_location = models.CharField(max_length=255, null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Networking Spare"
        verbose_name_plural = "Networking Spares"

    def __str__(self):
        return self.product.name


class ImportJob(models.Model):
    MODEL_CHOICES = (
        ('battery', 'Battery'),
        ('card', 'Card'),
        ('controller', 'Controller'),
        ('cpu', 'CPU'),
        ('harddisk', 'Hard Disk'),
        ('memory', 'Memory'),
        ('networking_spare', 'Networking Spare'),
        ('railkit', 'Rail Kit'),
        ('server', 'Server'),
        ('sfp', 'SFP'),
        ('stock_out', 'Stock Out'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('DONE', 'Done'),
        ('FAILED', 'Failed'),
    )

    model_key = models.CharField(max_length=50, choices=MODEL_CHOICES)
    upload = models.FileField(upload_to='imports/')
    total_rows = models.PositiveIntegerField(default=0)
    processed_rows = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    # Warehouse every row in this import is stocked into. User-selected at
    # upload time instead of always defaulting to WH1.
    store_location = models.CharField(max_length=50, default='WH1')
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_jobs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_model_key_display()} import #{self.pk}"


