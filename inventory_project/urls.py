"""
URL configuration for inventory_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from apps.core import views as core_views

urlpatterns = [
    path('', core_views.home, name='home'),
    path('dashboard/', core_views.dashboard, name='dashboard'),
    path('login/', core_views.login_view, name='login'),
    path('logout/', core_views.logout_view, name='logout'),
    path('users/', core_views.user_list, name='user_list'),
    path('users/permissions/', core_views.role_permission_settings, name='role_permission_settings'),
    path('users/create/', core_views.user_create, name='user_create'),
    path('users/<int:user_id>/edit/', core_views.user_edit, name='user_edit'),
    path('users/<int:user_id>/toggle-active/', core_views.user_toggle_active, name='user_toggle_active'),
    path('admin/', admin.site.urls),
    path('spare/', include('apps.categories.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('servers/', include('apps.servers.urls')),

]

# Serve uploaded files (audit-finding attachments, import files, etc.).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
