from django.urls import path
from django.contrib.auth.decorators import login_required
from .views import add_card, add_controller, add_controller_component, add_cpu, add_harddisk, add_memory, add_railkit, add_sfp, add_spare, card_list, check_barcode, check_serial, controller_components, controller_list, cpu_list, harddisk_list, memory_list, railkit_list, sfp_list, spare_list, spare_out_report, update_controller_field, update_cpu_field, update_harddisk_field, update_memory_field, update_railkit_field, update_sfp_field, update_spare_field
from . import views
from apps.core.permissions import require_any_permission, require_permission

urlpatterns = [
    
    #// Spare URLs
    path('add-spare/', require_permission('stock_in')(add_spare), name='add_spare'),
    path('check-serial/', check_serial, name='check_serial'),
    path('spares/', spare_list, name='spare_list'),
    path('update-spare/', require_permission('mapping')(update_spare_field), name='update_spare'),
    path('spare-out-report/', require_any_permission('sold_view', 'reports')(spare_out_report), name='spare_out_report'),
    
    
    #// Card URLs
    path('add-card/', require_permission('stock_in')(add_card), name='add_card'),
    path('card-list/', card_list, name='card_list'),
    
    #// CPU URLs
    path('cpu-add/', require_permission('stock_in')(add_cpu), name='add_cpu'),
    path('cpu-list/', cpu_list, name='cpu_list'),
    path('cpu-update/', require_permission('mapping')(update_cpu_field), name='update_cpu'),
    
    
    #// Controller URLs
    path('controller-add/',    require_permission('stock_in')(add_controller),          name='add_controller'),
    path('controller-list/',   controller_list,         name='controller_list'),
    path('controller-update/', require_permission('mapping')(update_controller_field), name='update_controller'),
    path('controller-components/<int:controller_id>/', controller_components, name='controller_components'),
    path('controller-add-component/',
     require_permission('stock_in')(add_controller_component),
     name='add_controller_component'),
 
    path('controller-components/<int:controller_id>/',
     controller_components,
     name='controller_components'),
    
    #// Memory URLs
    path('memory-add/',    require_permission('stock_in')(add_memory),          name='add_memory'),
    path('memory-list/',   memory_list,         name='memory_list'),
    path('memory-update/', require_permission('mapping')(update_memory_field), name='update_memory'),
    
    
    #// SFP URLs
    path('sfp-add/',    require_permission('stock_in')(add_sfp),          name='add_sfp'),
    path('sfp-list/',   sfp_list,         name='sfp_list'),
    path('sfp-update/', require_permission('mapping')(update_sfp_field), name='update_sfp'),
    
    
    #// railkit URLs
    path('railkit-add/',    require_permission('stock_in')(add_railkit),          name='add_railkit'),
    path('railkit-list/',   railkit_list,         name='railkit_list'),
    path('railkit-update/', require_permission('mapping')(update_railkit_field), name='update_railkit'),
    
    
    #/// Hard Disk URLs
    path('harddisk-add/',    require_permission('stock_in')(add_harddisk),          name='add_harddisk'),
    path('harddisk-list/',   harddisk_list,         name='harddisk_list'),
    path('harddisk-update/', require_permission('mapping')(update_harddisk_field), name='update_harddisk'),
    
    path('spare/check-barcode/', check_barcode, name='check_barcode'),
    path('networking-spare/add/', require_permission('stock_in')(views.add_networking_spare), name='add_networking_spare'),
    path('networking-spare/list/', views.networking_spare_list, name='networking_spare_list'),
    path('sold/<str:kind>/', require_any_permission('sold_view', 'reports')(views.inventory_sold_list), name='inventory_sold'),
    path('faulty/<str:kind>/', require_any_permission('sold_view', 'reports')(views.inventory_faulty_list), name='inventory_faulty'),
    path('export/<str:kind>/<str:state>/', require_any_permission('sold_view', 'reports')(views.export_inventory), name='inventory_export'),
    path('export-controllers/<str:state>/', require_permission('reports')(views.export_controllers), name='controller_export'),
    path('import/', views.import_inventory_page, name='inventory_import'),
    path('import/template/<str:model_key>/', login_required(views.import_template_download), name='inventory_import_template'),
    path('import/start/', views.start_import, name='inventory_import_start'),
    path('import/process/<int:job_id>/', views.process_import, name='inventory_import_process'),
    path('universal-search/', views.universal_search, name='universal_search'),
    

    
]
