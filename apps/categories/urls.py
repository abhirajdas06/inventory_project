from django.urls import path
from .views import add_card, add_controller, add_controller_component, add_cpu, add_harddisk, add_memory, add_railkit, add_sfp, add_spare, card_list, check_barcode, check_serial, controller_components, controller_list, cpu_list, harddisk_list, memory_list, railkit_list, sfp_list, spare_list, spare_out_report, update_controller_field, update_cpu_field, update_harddisk_field, update_memory_field, update_railkit_field, update_sfp_field, update_spare_field

urlpatterns = [
    
    #// Spare URLs
    path('add-spare/', add_spare, name='add_spare'),
    path('check-serial/', check_serial, name='check_serial'),
    path('spares/', spare_list, name='spare_list'),
    path('update-spare/', update_spare_field, name='update_spare'),
    path('spare-out-report/', spare_out_report, name='spare_out_report'),
    
    
    #// Card URLs
    path('add-card/', add_card, name='add_card'),
    path('card-list/', card_list, name='card_list'),
    
    #// CPU URLs
    path('cpu-add/', add_cpu, name='add_cpu'),
    path('cpu-list/', cpu_list, name='cpu_list'),
    path('cpu-update/', update_cpu_field, name='update_cpu'),
    
    
    #// Controller URLs
    path('controller-add/',    add_controller,          name='add_controller'),
    path('controller-list/',   controller_list,         name='controller_list'),
    path('controller-update/', update_controller_field, name='update_controller'),
    path('controller-components/<int:controller_id>/', controller_components, name='controller_components'),
    path('controller-add-component/',
     add_controller_component,
     name='add_controller_component'),
 
    path('controller-components/<int:controller_id>/',
     controller_components,
     name='controller_components'),
    
    #// Memory URLs
    path('memory-add/',    add_memory,          name='add_memory'),
    path('memory-list/',   memory_list,         name='memory_list'),
    path('memory-update/', update_memory_field, name='update_memory'),
    
    
    #// SFP URLs
    path('sfp-add/',    add_sfp,          name='add_sfp'),
    path('sfp-list/',   sfp_list,         name='sfp_list'),
    path('sfp-update/', update_sfp_field, name='update_sfp'),
    
    
    #// railkit URLs
    path('railkit-add/',    add_railkit,          name='add_railkit'),
    path('railkit-list/',   railkit_list,         name='railkit_list'),
    path('railkit-update/', update_railkit_field, name='update_railkit'),
    
    
    #/// Hard Disk URLs
    path('harddisk-add/',    add_harddisk,          name='add_harddisk'),
    path('harddisk-list/',   harddisk_list,         name='harddisk_list'),
    path('harddisk-update/', update_harddisk_field, name='update_harddisk'),
    
    path('spare/check-barcode/', check_barcode, name='check_barcode'),
    

    
]