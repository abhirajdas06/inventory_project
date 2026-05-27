from django.contrib import admin
from .models import SpareCategory, Product, Brand


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

