from django.shortcuts import render
from .models import MenuItem

def menu_view(request):
    menu_items = MenuItem.objects.filter(is_available=True).order_by("name")
    return render(request, 'menu.html', {'menu_items': menu_items})

def cart_view(request):
    return render(request, 'cart.html')

def staff_queue_view(request):
    return render(request, 'staff_queue.html')