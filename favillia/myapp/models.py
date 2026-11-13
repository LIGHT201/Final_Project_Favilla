from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User

class BaseUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True)

    class Meta:
        abstract = True

class Customer(BaseUser):
    delivery_address = models.TextField(blank=True)

    def __str__(self):
        return f"Customer: {self.user.username}"

class Staff(BaseUser):
    role = models.CharField(max_length=50, default="Barista")

    def __str__(self):
        return f"Staff: {self.user.username} ({self.role})"

class MenuItem(models.Model):
    CUP_SIZES = (
        (12, "12 oz"),
        (16, "16 oz"),
        (20, "20 oz"),
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Base price for a 12 oz cup, or the price for a non-cup item.",
    )
    is_cup = models.BooleanField(
        default=True,
        verbose_name="Cup item",
        help_text="Enable cup sizes for this menu item.",
    )
    price_16oz_adjustment = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name="16 oz price adjustment",
        help_text="Amount added to the 12 oz base price.",
    )
    price_20oz_adjustment = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name="20 oz price adjustment",
        help_text="Amount added to the 12 oz base price.",
    )
    is_available = models.BooleanField(default=True)  # False = "86'd" by staff

    def get_price_for_size(self, size):
        adjustments = {
            12: 0,
            16: self.price_16oz_adjustment,
            20: self.price_20oz_adjustment,
        }
        try:
            adjustment = adjustments[size]
        except KeyError:
            raise ValueError(f"Unsupported cup size: {size}") from None
        return Decimal(str(self.price)) + Decimal(str(adjustment))

    def get_size_options(self):
        return [
            (size, label, self.get_price_for_size(size))
            for size, label in self.CUP_SIZES
        ]

    def __str__(self):
        return self.name

class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PREPPING', 'Prepping'),
        ('READY', 'Ready'),
        ('COMPLETED', 'Completed'),
    ]
    FULFILLMENT_CHOICES = [
        ('PICKUP', 'Pickup'),
        ('DELIVERY', 'Delivery'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    fulfillment = models.CharField(max_length=20, choices=FULFILLMENT_CHOICES, default='PICKUP')
    special_instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.customer.user.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name}"