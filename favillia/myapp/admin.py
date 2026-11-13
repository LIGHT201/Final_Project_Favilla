from django.contrib import admin
from .models import Customer, Staff, MenuItem, Order, OrderItem

admin.site.register(Customer)
admin.site.register(Staff)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "is_cup", "is_available")
    list_filter = ("is_cup", "is_available")
    search_fields = ("name", "description")
    fields = (
        "name",
        "description",
        "price",
        "is_cup",
        "price_16oz_adjustment",
        "price_20oz_adjustment",
        "is_available",
    )


admin.site.register(Order)
admin.site.register(OrderItem) 