from django.contrib import admin
from .models import SFP, Card, Memory, RailKit, Spare, CPU, Controller, HardDisk


@admin.register(Spare)
class SpareAdmin(admin.ModelAdmin):

    # 🔹 List View
    list_display = (
        'id',
        'get_category',
        'get_serial_no',
        'brand',
        'model',
        'qty',
        'location',
    )

    # 🔹 Search
    search_fields = (
        'product__serial_no',
        'product__name',
        'model',
        'part_no',
        'barcode',
    )

    # 🔹 Filters
    list_filter = (
        'product__category',
        'brand',
        'location',
    )

    ordering = ('-id',)
    list_per_page = 50

    # 🔹 Fieldsets (FIXED)
    fieldsets = (

        ("Product Info", {
            'fields': (
                'product',   # ✅ ONLY HERE
            )
        }),

        ("Spare Details", {
            'fields': (
                'brand',
                'model',
                'qty',
            )
        }),

        ("Part Info", {
            'fields': (
                'part_no',
                'alt_part_no',
            )
        }),

        ("Serial Info", {
            'fields': (
                'alt_serial_no',   # ❌ removed product from here
            )
        }),

        ("Extra Info", {
            'fields': (
                'specs',
                'barcode',
                'location',
                'reference_location',
                'remark',
            )
        }),
    )

    # 🔹 Helper methods

    def get_serial_no(self, obj):
        return obj.product.serial_no
    get_serial_no.short_description = "Serial No"

    def get_category(self, obj):
        return obj.product.category.name
    get_category.short_description = "Category"


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'get_category',
        'get_serial',
        'brand',
        'brand_model_no',
        'interface',
        'capacity',
        'location',
    )

    list_select_related = ('product', 'product__category')

    def get_serial(self, obj):
        return obj.product.serial_no

    def get_category(self, obj):
        return obj.product.category.name
    


@admin.register(CPU)
class CPUAdmin(admin.ModelAdmin):

    list_display = (
        'id', 'get_category', 'get_serial',
        'brand', 'model', 'no_of_cores',
        'ghz', 'cache', 'location'
    )

    list_select_related = ('product', 'product__category')

    search_fields = (
        'product__serial_no', 'model',
        'part_no', 'barcode'
    )

    list_filter = ('brand', 'no_of_cores', 'location')

    fieldsets = (
        ("Product", {'fields': ('product',)}),
        ("CPU Details", {'fields': (
            'brand', 'model', 'part_no',
            'no_of_cores', 'no_of_threads',
            'ghz', 'frequency', 'cache'
        )}),
        ("Location", {'fields': (
            'barcode', 'location',
            'reference_location', 'remark'
        )}),
    )

    def get_serial(self, obj):
        return obj.product.serial_no
    get_serial.short_description = "Serial No"
    get_serial.admin_order_field = 'product__serial_no'

    def get_category(self, obj):
        return obj.product.category.name
    get_category.short_description = "Category"
    
    
@admin.register(Controller)
class ControllerAdmin(admin.ModelAdmin):
 
    list_display = (
        'id', 'get_serial', 'brand', 'model',
        'part_no', 'location', 'get_component_count'
    )
 
    list_select_related = ('product', 'product__category', 'brand')
 
    search_fields = ('product__serial_no', 'model', 'part_no', 'barcode')
 
    list_filter = ('brand', 'location')
 
    fieldsets = (
        ("Cabinet / Product", {'fields': ('product',)}),
        ("Details", {'fields': (
            'brand', 'model', 'part_no', 'alt_part_no',
            'alt_serial_no', 'specs', 'qty',
        )}),
        ("Location", {'fields': (
            'barcode', 'location', 'reference_location',
            'parent_child_location', 'remark',
        )}),
    )
 
    def get_serial(self, obj):
        return obj.product.serial_no
    get_serial.short_description = 'Serial No'
    get_serial.admin_order_field = 'product__serial_no'
 
    def get_component_count(self, obj):
        return obj.components.count()
    get_component_count.short_description = 'Components'


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
 
    list_display = (
        'id', 'get_category', 'get_serial',
        'brand', 'oem', 'model',
        'size', 'ram_type', 'ddr_version',
        'frequency', 'rank', 'barcode', 'location',
    )
 
    list_select_related = ('product', 'product__category', 'brand')
 
    search_fields = (
        'product__serial_no', 'model',
        'part_no_1', 'barcode', 'oem',
    )
 
    list_filter = ('brand', 'ram_type', 'ddr_version', 'size', 'location')
 
    ordering = ('-id',)
    list_per_page = 50
 
    fieldsets = (
        ("Product", {'fields': ('product',)}),
        ("Identity", {'fields': (
            'brand', 'oem', 'model',
            'part_no_1', 'part_no_2', 'part_no_3',
        )}),
        ("Specs", {'fields': (
            'size', 'ram_type', 'ddr_version',
            'frequency', 'rank',
        )}),
        ("Location", {'fields': (
            'qty', 'barcode',
            'location', 'reference_location', 'remark',
        )}),
    )
 
    def get_serial(self, obj):
        return obj.product.serial_no
    get_serial.short_description = 'Serial No'
    get_serial.admin_order_field = 'product__serial_no'
 
    def get_category(self, obj):
        return obj.product.category.name
    get_category.short_description = 'Category'



@admin.register(SFP)
class SFPAdmin(admin.ModelAdmin):
 
    list_display = (
        'id', 'get_category', 'get_serial',
        'brand', 'model', 'part_no',
        'fibre_type', 'data_rate',
        'barcode', 'location',
    )
 
    list_select_related = ('product', 'product__category', 'brand')
 
    search_fields = (
        'product__serial_no', 'model',
        'part_no', 'barcode', 'description',
    )
 
    list_filter = ('brand', 'fibre_type', 'data_rate', 'location')
 
    ordering = ('-id',)
    list_per_page = 50
 
    fieldsets = (
        ("Product", {'fields': ('product',)}),
        ("SFP Details", {'fields': (
            'brand', 'model', 'part_no',
            'description', 'fibre_type', 'data_rate',
        )}),
        ("Location", {'fields': (
            'barcode', 'location',
            'reference_location', 'remark',
        )}),
    )
 
    def get_serial(self, obj):
        return obj.product.serial_no
    get_serial.short_description = 'Serial No'
    get_serial.admin_order_field = 'product__serial_no'
 
    def get_category(self, obj):
        return obj.product.category.name
    get_category.short_description = 'Category'
    
    

@admin.register(RailKit)
class RailKitAdmin(admin.ModelAdmin):
 
    list_display = (
        'id', 'get_category', 'get_serial',
        'brand', 'side', 'part_no',
        'supported_model', 'barcode', 'location',
    )
 
    list_select_related = ('product', 'product__category', 'brand')
 
    search_fields = (
        'product__serial_no', 'part_no',
        'barcode', 'supported_model',
    )
 
    list_filter = ('brand', 'side', 'supported_model', 'location')
 
    ordering = ('-id',)
    list_per_page = 50
 
    fieldsets = (
        ("Product", {'fields': ('product',)}),
        ("Rail Kit Details", {'fields': (
            'brand', 'side', 'part_no',
            'specs', 'supported_model', 'qty',
        )}),
        ("Location", {'fields': (
            'barcode', 'location',
            'reference_location', 'remark',
        )}),
    )
 
    def get_serial(self, obj):
        return obj.product.serial_no
    get_serial.short_description = 'Serial No'
    get_serial.admin_order_field = 'product__serial_no'
 
    def get_category(self, obj):
        return obj.product.category.name
    get_category.short_description = 'Category'


@admin.register(HardDisk)
class HardDiskAdmin(admin.ModelAdmin):
 
    list_display = (
        'id', 'get_category', 'get_serial',
        'brand', 'oem', 'capacity', 'rpm',
        'interface', 'size', 'health',
        'barcode', 'location',
    )
 
    list_select_related = ('product', 'product__category', 'brand')
 
    search_fields = (
        'product__serial_no', 'oem_model_no', 'brand_model_no',
        'part_no', 'barcode', 'brand_serial_no', 'oem_serial_no',
    )
 
    list_filter = (
        'brand', 'interface', 'size',
        'capacity', 'rpm', 'location',
    )
 
    ordering = ('-id',)
    list_per_page = 50
 
    fieldsets = (
        ("Product", {'fields': ('product',)}),
        ("Identity", {'fields': (
            'brand', 'oem',
            'brand_model_no', 'oem_model_no',
        )}),
        ("Specs", {'fields': (
            'capacity', 'rpm', 'interface',
            'size', 'firmware', 'health', 'gb_s',
        )}),
        ("Part Numbers", {'fields': (
            'part_no', 'alt_part_no',
            'alt_fru_1', 'alt_fru_2', 'alt_fru_3',
            'retail_part_no', 'spare_part_tray', 'gpn_code',
        )}),
        ("Serials", {'fields': (
            'brand_serial_no', 'oem_serial_no',
        )}),
        ("Location", {'fields': (
            'barcode', 'tray_barcode',
            'location', 'reference_location', 'remark',
        )}),
    )
 
    def get_serial(self, obj):
        return obj.product.serial_no
    get_serial.short_description = 'Serial No'
    get_serial.admin_order_field = 'product__serial_no'
 
    def get_category(self, obj):
        return obj.product.category.name
    get_category.short_description = 'Category'
    

