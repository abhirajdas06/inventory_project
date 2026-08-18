from django.urls import path
from . import views
from apps.core.permissions import require_any_permission, require_permission
 
urlpatterns = [
    path('add/',               require_permission('stock_in')(views.add_server),               name='add_server'),
    path('list/',              views.server_list,              name='server_list'),
    path('sold/',              require_any_permission('sold_view', 'reports')(views.server_out_list),          name='server_out_list'),
    path('faulty/',            require_any_permission('sold_view', 'reports')(views.server_faulty_list),       name='server_faulty_list'),
    path('export/<str:state>/', require_permission('reports')(views.export_servers),          name='server_export'),
    path('update/',            require_permission('mapping')(views.update_server_field),      name='update_server'),
    path('components/<int:server_id>/',  views.server_components,  name='server_components'),
    path('add-component/',     require_permission('stock_in')(views.add_server_component_view), name='add_server_component'),
]
