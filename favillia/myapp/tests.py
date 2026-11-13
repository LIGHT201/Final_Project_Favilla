from decimal import Decimal

from django.test import TestCase
from .models import MenuItem


class MenuItemTests(TestCase):
    def test_size_prices_use_16_oz_base_and_item_adjustments(self):
        item = MenuItem.objects.create(
            name="Latte",
            price="4.50",
            price_16oz_adjustment="0.50",
            price_20oz_adjustment="0.75",
        )

        self.assertEqual(item.get_price_for_size(12), Decimal("4.50"))
        self.assertEqual(item.get_price_for_size(16), Decimal("5.00"))
        self.assertEqual(item.get_price_for_size(20), Decimal("5.25"))
        self.assertEqual(
            [option[0] for option in item.get_size_options()],
            [12, 16, 20],
        )

    def test_menu_displays_sizes_for_cups_and_price_for_non_cups(self):
        MenuItem.objects.create(
            name="Latte",
            price="4.50",
            price_16oz_adjustment="0.50",
            price_20oz_adjustment="0.75",
        )
        MenuItem.objects.create(
            name="Muffin",
            price="3.25",
            is_cup=False,
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode().count("<select"), 1)
        self.assertContains(response, "12 oz - $4.50")
        self.assertContains(response, "16 oz - $5.00")
        self.assertContains(response, "20 oz - $5.25")
        self.assertContains(response, "Muffin")
        self.assertContains(response, "$3.25")
