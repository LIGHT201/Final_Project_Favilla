from django.urls import path
from . import views

urlpatterns = [
    path('', views.menu_view, name='menu'),
    path('cart/', views.cart_view, name='cart'),
    path('staff/', views.staff_queue_view, name='staff_queue'),
]