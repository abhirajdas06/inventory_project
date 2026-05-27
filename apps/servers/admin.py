from django.contrib import admin
from .models import Server, ServerComponent
 
 
class ServerComponentInline(admin.TabularInline):
    model  = ServerComponent
    extra  = 0
    fields = ('spare_type', 'serial_no', 'barcode', 'working_status', 'remark')
    readonly_fields = ('spare_type', 'serial_no', 'barcode')
 
 
@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display  = ('id', 'machine_no', 'service_tag', 'model', 'machine_type',
                     'status', 'testing_date', 'tested_by', 'location')
    search_fields = ('service_tag', 'model', 'machine_no')
    list_filter   = ('machine_type', 'status')
    ordering      = ('-created_at',)
    inlines       = [ServerComponentInline]
    list_per_page = 50
 
 
@admin.register(ServerComponent)
class ServerComponentAdmin(admin.ModelAdmin):
    list_display  = ('id', 'server', 'spare_type', 'serial_no', 'barcode', 'working_status')
    search_fields = ('server__service_tag', 'spare_type', 'serial_no', 'barcode')
    list_filter   = ('spare_type', 'working_status')
    list_per_page = 50