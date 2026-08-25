from django.contrib import admin
from .models import ActivityLog, AssetTimelineEvent, Brand, Notification, Product, RolePermission, SpareCategory, UserProfile


@admin.register(SpareCategory)
class SpareCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'serial_no', 'category', 'brand', 'model', 'created_at')
    search_fields = ('serial_no', 'name')
    list_filter = ('category', 'brand', 'model', 'created_at')
    
@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)    


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_at')
    search_fields = ('user__username', 'user__email')
    list_filter = ('role',)


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'updated_at')
    readonly_fields = ('updated_at',)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'role', 'action', 'module', 'entity', 'warehouse', 'location')
    search_fields = ('action', 'module', 'entity', 'barcode', 'remarks', 'location', 'warehouse')
    list_filter = ('action', 'module', 'role', 'timestamp')
    readonly_fields = ('timestamp',)
    list_per_page = 100


@admin.register(AssetTimelineEvent)
class AssetTimelineEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'product', 'event_type', 'performed_by', 'warehouse', 'location')
    search_fields = ('product__serial_no', 'product__name', 'event_type', 'remarks', 'warehouse', 'location')
    list_filter = ('event_type', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'notification_type', 'title', 'is_read')
    search_fields = ('title', 'message', 'user__username')
    list_filter = ('notification_type', 'is_read', 'created_at')

