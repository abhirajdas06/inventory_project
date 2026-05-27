from django.urls import path
from . import views
 
urlpatterns = [
    path('add/',               views.add_server,               name='add_server'),
    path('list/',              views.server_list,              name='server_list'),
    path('update/',            views.update_server_field,      name='update_server'),
    path('components/<int:server_id>/',  views.server_components,  name='server_components'),
    path('add-component/',     views.add_server_component_view, name='add_server_component'),
]