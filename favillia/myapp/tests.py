from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Customer, MenuItem, Order, OrderItem, Staff


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


class CartTests(TestCase):
    def setUp(self):
        self.latte = MenuItem.objects.create(
            name="Latte",
            price="4.50",
            price_16oz_adjustment="0.50",
            price_20oz_adjustment="0.75",
        )
        self.muffin = MenuItem.objects.create(
            name="Muffin",
            price="3.25",
            is_cup=False,
        )

    def test_add_to_cart_and_calculate_subtotal_tax_and_total(self):
        self.client.post(f"/cart/add/{self.latte.pk}/", {"size": "16"})
        self.client.post(f"/cart/add/{self.latte.pk}/", {"size": "16"})
        self.client.post(f"/cart/add/{self.muffin.pk}/", {"size": ""})

        response = self.client.get("/cart/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Qty: 2")
        self.assertContains(response, "Subtotal <span>$13.25</span>")
        self.assertContains(response, "Tax (2%) <span>$0.27</span>")
        self.assertContains(response, "Total <span>$13.52</span>")

    def test_cart_quantity_controls_and_remove(self):
        self.client.post(f"/cart/add/{self.muffin.pk}/", {"size": ""})
        key = f"{self.muffin.pk}:"

        self.client.post("/cart/", {"action": "increase", "key": key})
        response = self.client.get("/cart/")
        self.assertContains(response, "Qty: 2")

        self.client.post("/cart/", {"action": "decrease", "key": key})
        response = self.client.get("/cart/")
        self.assertContains(response, "Qty: 1")

        self.client.post("/cart/", {"action": "remove", "key": key})
        response = self.client.get("/cart/")
        self.assertContains(response, "Your cart is empty")

    def test_add_to_cart_rejects_invalid_size(self):
        response = self.client.post(
            f"/cart/add/{self.latte.pk}/",
            {"size": "99"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("cart", self.client.session)


class CustomerOrderingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="customer",
            password="secure-test-password",
            email="customer@example.com",
        )
        self.customer = Customer.objects.create(user=self.user)
        self.latte = MenuItem.objects.create(
            name="Latte",
            price="4.50",
            price_16oz_adjustment="0.50",
        )

    def test_customer_registration_creates_account_and_profile(self):
        response = self.client.post("/register/", {
            "username": "new-customer",
            "email": "new@example.com",
            "phone": "555-0100",
            "delivery_address": "10 Coffee Street",
            "password1": "Strong-test-password-2026",
            "password2": "Strong-test-password-2026",
        })

        self.assertRedirects(response, "/")
        customer = Customer.objects.get(user__username="new-customer")
        self.assertEqual(customer.delivery_address, "10 Coffee Street")
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_checkout_creates_order_snapshots_and_clears_cart(self):
        self.client.force_login(self.user)
        self.client.post(f"/cart/add/{self.latte.pk}/", {"size": "16"})
        self.client.post(f"/cart/add/{self.latte.pk}/", {"size": "16"})

        checkout_page = self.client.get("/checkout/")
        self.assertEqual(checkout_page.status_code, 200)
        self.assertContains(checkout_page, "Tax (2%)")

        invalid_checkout = self.client.post("/checkout/", {
            "fulfillment": "DELIVERY",
            "delivery_address": "",
        })
        self.assertEqual(invalid_checkout.status_code, 400)
        self.assertFalse(Order.objects.exists())

        response = self.client.post("/checkout/", {
            "fulfillment": "DELIVERY",
            "delivery_address": "10 Coffee Street",
            "special_instructions": "Leave at the door",
        })

        self.assertRedirects(response, "/orders/")
        order = Order.objects.get(customer=self.customer)
        order_item = OrderItem.objects.get(order=order)
        self.assertEqual(order.fulfillment, "DELIVERY")
        self.assertEqual(order.delivery_address, "10 Coffee Street")
        self.assertEqual(order_item.item_name, "Latte")
        self.assertEqual(order_item.size, "16 oz")
        self.assertEqual(order_item.unit_price, Decimal("5.00"))
        self.assertEqual(order_item.quantity, 2)
        self.assertEqual(order.subtotal, Decimal("10.00"))
        self.assertEqual(order.tax_amount, Decimal("0.20"))
        self.assertEqual(order.total, Decimal("10.20"))
        self.assertEqual(self.client.session["cart"], {})
        history = self.client.get("/orders/")
        self.assertContains(history, "Latte")
        self.assertContains(history, "Total <span>$10.20</span>")

    def test_customer_sees_only_their_own_orders(self):
        other_user = User.objects.create_user(
            username="other",
            password="secure-test-password",
        )
        other_customer = Customer.objects.create(user=other_user)
        order = Order.objects.create(customer=other_customer)

        self.client.force_login(self.user)
        response = self.client.get("/orders/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f"Order #{order.pk}")


class StaffToolsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="barista",
            password="secure-test-password",
        )
        Staff.objects.create(user=self.user)
        self.customer_user = User.objects.create_user(
            username="buyer",
            password="secure-test-password",
        )
        self.customer = Customer.objects.create(user=self.customer_user)
        self.order = Order.objects.create(customer=self.customer)
        self.client.force_login(self.user)

    def test_staff_can_advance_order_status(self):
        queue = self.client.get("/staff/")
        self.assertContains(queue, "Start preparing")

        response = self.client.post(
            f"/staff/orders/{self.order.pk}/status/",
            {"status": "PREPPING"},
        )

        self.assertRedirects(response, "/staff/")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "PREPPING")

    def test_non_staff_cannot_open_staff_tools(self):
        self.client.force_login(self.customer_user)
        response = self.client.get("/staff/")

        self.assertEqual(response.status_code, 403)
