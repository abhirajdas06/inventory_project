from django.contrib import admin
from .models import (
    AuditFinding,
    GeneralAuditFinding,
    InventoryFreezeRecord,
    InventoryTransaction,
    InventoryTransfer,
    SalesReturn,
    TransferRequest,
    TransferRequestItem,
)


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):

    # 🔹 LIST VIEW (what you see in table)
    list_display = (
        'id',
        'get_serial_no',
        'get_category',
        'transaction_type',
        'store_location',
        'stock_status',
        'client_name',
        'invoice_no',
        'stock_in_date',
        'stock_out_date',
        'audited_by',
        'created_at',
    )

    # 🔹 SEARCH
    search_fields = (
        'product__serial_no',
        'product__name',
        'client_name',
        'invoice_no',
    )

    # 🔹 FILTERS (VERY IMPORTANT FOR ERP)
    list_filter = (
        'transaction_type',
        'store_location',
        'stock_status',
        'created_at',
    )

    # 🔹 ORDER
    ordering = ('-created_at',)

    # 🔹 PAGINATION
    list_per_page = 50

    # 🔹 READONLY
    readonly_fields = ('created_at',)

    # 🔹 FORM LAYOUT
    fieldsets = (

        ("Product Info", {
            'fields': (
                'product',
            )
        }),

        ("Transaction Info", {
            'fields': (
                'transaction_type',
                'store_location',
                'stock_status',
            )
        }),

        ("Stock Dates", {
            'fields': (
                'stock_in_date',
                'stock_out_date',
            )
        }),

        ("Client Details", {
            'fields': (
                'client_name',
                'invoice_no',
            )
        }),

        ("Audit Info", {
            'fields': (
                'audited_on',
                'audited_by',
                'audit_remark',
            )
        }),

        ("Meta", {
            'fields': (
                'created_at',
            )
        }),
    )

    # 🔹 HELPERS (IMPORTANT)

    def get_serial_no(self, obj):
        return obj.product.serial_no
    get_serial_no.short_description = "Serial No"

    def get_category(self, obj):
        return obj.product.category.name
    get_category.short_description = "Category"


@admin.register(InventoryTransfer)
class InventoryTransferAdmin(admin.ModelAdmin):
    list_display = ('product', 'source_warehouse', 'destination_warehouse', 'transferred_by', 'created_at')
    search_fields = ('product__serial_no', 'product__name', 'source_location', 'destination_location', 'remarks')
    list_filter = ('source_warehouse', 'destination_warehouse', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(SalesReturn)
class SalesReturnAdmin(admin.ModelAdmin):
    list_display = ('product', 'reason', 'disposition', 'returned_on', 'returned_by')
    search_fields = ('product__serial_no', 'product__name', 'remarks')
    list_filter = ('reason', 'disposition', 'returned_on')
    readonly_fields = ('created_at',)


class TransferRequestItemInline(admin.TabularInline):
    model = TransferRequestItem
    extra = 0
    readonly_fields = ('received_at',)


@admin.register(TransferRequest)
class TransferRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_warehouse', 'destination_warehouse', 'status', 'requested_by', 'created_at')
    list_filter = ('status', 'source_warehouse', 'destination_warehouse')
    inlines = (TransferRequestItemInline,)


@admin.register(InventoryFreezeRecord)
class InventoryFreezeRecordAdmin(admin.ModelAdmin):
    list_display = ('product', 'status', 'reason', 'frozen_by', 'unfrozen_by', 'frozen_at', 'unfrozen_at')
    search_fields = ('product__serial_no', 'product__name', 'reason')
    list_filter = ('status', 'frozen_at', 'unfrozen_at')
    readonly_fields = ('frozen_at',)


@admin.register(AuditFinding)
class AuditFindingAdmin(admin.ModelAdmin):
    list_display = ('audit_date', 'person_involved', 'created_by', 'created_at')
    search_fields = ('person_involved', 'remarks')
    list_filter = ('audit_date', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(GeneralAuditFinding)
class GeneralAuditFindingAdmin(admin.ModelAdmin):
    list_display = ('audit_date', 'title', 'person', 'status', 'created_by', 'attended_by', 'created_at')
    search_fields = ('title', 'person', 'remarks', 'attended_remarks')
    list_filter = ('status', 'audit_date', 'created_at')
    readonly_fields = ('created_at', 'attended_at')
