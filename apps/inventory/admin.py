from django.contrib import admin
from .models import InventoryTransaction


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