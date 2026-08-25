from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class SpareCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(SpareCategory, on_delete=models.PROTECT)
    serial_no = models.CharField(max_length=100, null=True, blank=True)

    part_no = models.CharField(max_length=100, null=True, blank=True)

    brand = models.CharField(max_length=100, null=True, blank=True)
    model = models.CharField(max_length=100, null=True, blank=True)

    name = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('STOCK_IN', 'Stock In User'),
        ('STOCK_OUT', 'Stock Out User'),
        ('AUDIT', 'Audit User'),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='ADMIN')
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class RolePermission(models.Model):
    """Optional role-level overrides for the inventory permission defaults."""
    role = models.CharField(max_length=20, choices=UserProfile.ROLE_CHOICES, unique=True)
    permissions = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Permissions: {self.get_role_display()}"


class ActivityLog(models.Model):
    MODULE_CHOICES = (
        ('INVENTORY', 'Inventory'),
        ('AUDIT', 'Audit'),
        ('IMPORT', 'Import'),
        ('EXPORT', 'Export'),
        ('USER', 'User'),
        ('SERVER', 'Server'),
        ('CONTROLLER', 'Controller'),
        ('SYSTEM', 'System'),
    )

    timestamp = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
    )
    role = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=100, db_index=True)
    module = models.CharField(max_length=20, choices=MODULE_CHOICES, db_index=True)
    entity = models.CharField(max_length=100, blank=True, db_index=True)
    entity_id = models.CharField(max_length=100, blank=True, db_index=True)
    barcode = models.CharField(max_length=100, blank=True, db_index=True)
    warehouse = models.CharField(max_length=100, blank=True, db_index=True)
    location = models.CharField(max_length=255, blank=True, db_index=True)
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    remarks = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp', '-id']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('ActivityLog is immutable and cannot be edited.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('ActivityLog is immutable and cannot be deleted.')

    def __str__(self):
        return f"{self.module}:{self.action}:{self.entity_id}"


class AssetTimelineEvent(models.Model):
    EVENT_CHOICES = (
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('AUDIT', 'Audit'),
        ('IMPORT', 'Import'),
        ('MAP', 'Mapping'),
        ('UNMAP', 'Unmapping'),
        ('FREEZE', 'Freeze'),
        ('UNFREEZE', 'Unfreeze'),
        ('TRANSFER', 'Transfer'),
        ('RETURN', 'Sales Return'),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='timeline_events',
    )
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES, db_index=True)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='timeline_events',
    )
    warehouse = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f"{self.product_id}:{self.event_type}"


class Notification(models.Model):
    TYPE_CHOICES = (
        ('AUDIT_FINDING', 'Audit Finding'),
        ('TRANSFER', 'Transfer'),
        ('FREEZE', 'Freeze'),
        ('IMPORT', 'Import'),
        ('SYSTEM', 'System'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, db_index=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user_id}:{self.notification_type}"
