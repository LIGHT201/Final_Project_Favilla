from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CustomerSignupForm
from .models import Customer, MenuItem, Order, OrderItem, Staff


def _cart_key(item_id, size):
    return f"{item_id}:{size if size is not None else ''}"


def _cart_lines(request):
    cart = request.session.get("cart", {})
    if not isinstance(cart, dict):
        cart = {}

    item_ids = set()
    parsed_entries = []
    for key, quantity in cart.items():
        try:
            item_id, size_value = key.split(":", 1)
            item_id = int(item_id)
            quantity = int(quantity)
            size = int(size_value) if size_value else None
        except (AttributeError, TypeError, ValueError):
            continue
        if quantity > 0:
            parsed_entries.append((key, item_id, size, quantity))
            item_ids.add(item_id)

    menu_items = MenuItem.objects.in_bulk(item_ids)
    lines = []
    valid_cart = {}
    removed_items = False
    for key, item_id, size, quantity in parsed_entries:
        item = menu_items.get(item_id)
        if item is None or not item.is_available:
            removed_items = True
            continue

        if item.is_cup:
            if size not in dict(item.CUP_SIZES):
                continue
            unit_price = item.get_price_for_size(size)
            size_label = dict(item.CUP_SIZES)[size]
        else:
            if size is not None:
                continue
            unit_price = item.price
            size_label = None

        valid_cart[key] = quantity
        lines.append({
            "key": key,
            "item": item,
            "size_label": size_label,
            "unit_price": unit_price,
            "quantity": quantity,
            "line_total": unit_price * quantity,
        })

    if valid_cart != cart:
        request.session["cart"] = valid_cart
    if removed_items:
        messages.warning(
            request,
            "Unavailable items were removed from your cart.",
        )
    return lines


def menu_view(request):
    menu_items = MenuItem.objects.filter(is_available=True).order_by("name")
    return render(request, 'menu.html', {'menu_items': menu_items})


def register_view(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        redirect_to = next_url
    else:
        redirect_to = "menu"

    if request.user.is_authenticated:
        return redirect(redirect_to)

    form = CustomerSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
        login(request, user)
        return redirect(redirect_to)
    return render(request, "register.html", {
        "form": form,
        "next": next_url,
    })


@require_POST
def add_to_cart_view(request, item_id):
    item = get_object_or_404(MenuItem, pk=item_id, is_available=True)
    size_value = request.POST.get("size", "")
    if item.is_cup:
        try:
            size = int(size_value)
        except (TypeError, ValueError):
            return HttpResponseBadRequest("Choose a valid cup size.")
        if size not in dict(item.CUP_SIZES):
            return HttpResponseBadRequest("Choose a valid cup size.")
    else:
        if size_value:
            return HttpResponseBadRequest("This item does not have cup sizes.")
        size = None

    cart = request.session.get("cart", {})
    if not isinstance(cart, dict):
        cart = {}
    key = _cart_key(item.pk, size)
    try:
        quantity = int(cart.get(key, 0))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("The cart item quantity is invalid.")
    if quantity < 0:
        return HttpResponseBadRequest("The cart item quantity is invalid.")
    cart[key] = quantity + 1
    request.session["cart"] = cart
    return redirect("cart")


def cart_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        key = request.POST.get("key", "")
        cart = request.session.get("cart", {})
        if not isinstance(cart, dict) or key not in cart:
            return HttpResponseBadRequest("That item is not in your cart.")
        try:
            quantity = int(cart[key])
        except (TypeError, ValueError):
            return HttpResponseBadRequest("The cart item quantity is invalid.")

        if action == "remove" or (action == "decrease" and quantity <= 1):
            del cart[key]
        elif action == "increase":
            cart[key] = quantity + 1
        elif action == "decrease":
            cart[key] = quantity - 1
        else:
            return HttpResponseBadRequest("Choose a valid cart action.")
        request.session["cart"] = cart
        return redirect("cart")

    lines = _cart_lines(request)
    subtotal = sum((line["line_total"] for line in lines), Decimal("0.00"))
    tax_rate = settings.SALES_TAX_RATE
    tax = (subtotal * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return render(request, 'cart.html', {
        "cart_items": lines,
        "subtotal": subtotal,
        "tax": tax,
        "tax_rate_percent": tax_rate * 100,
        "total": subtotal + tax,
    })


@login_required
def checkout_view(request):
    lines = _cart_lines(request)
    if not lines:
        return redirect("cart")

    customer, _ = Customer.objects.get_or_create(user=request.user)
    fulfillment = request.POST.get("fulfillment", "PICKUP")
    delivery_address = request.POST.get(
        "delivery_address",
        customer.delivery_address,
    ).strip()
    special_instructions = request.POST.get("special_instructions", "").strip()
    error = None

    if request.method == "POST":
        valid_fulfillments = dict(Order.FULFILLMENT_CHOICES)
        if fulfillment not in valid_fulfillments:
            error = "Choose pickup or delivery."
        elif fulfillment == "DELIVERY" and not delivery_address:
            error = "Enter a delivery address."
        else:
            subtotal = sum(
                (line["line_total"] for line in lines),
                Decimal("0.00"),
            )
            tax_rate = settings.SALES_TAX_RATE
            tax = (subtotal * tax_rate).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            with transaction.atomic():
                if fulfillment == "DELIVERY":
                    customer.delivery_address = delivery_address
                    customer.save(update_fields=("delivery_address",))

                order = Order.objects.create(
                    customer=customer,
                    fulfillment=fulfillment,
                    delivery_address=(
                        delivery_address if fulfillment == "DELIVERY" else ""
                    ),
                    special_instructions=special_instructions,
                    tax_rate=tax_rate,
                    tax_amount=tax,
                )
                OrderItem.objects.bulk_create([
                    OrderItem(
                        order=order,
                        menu_item=line["item"],
                        item_name=line["item"].name,
                        size=line["size_label"] or "",
                        unit_price=line["unit_price"],
                        quantity=line["quantity"],
                    )
                    for line in lines
                ])
                request.session["cart"] = {}
            return redirect("order_history")

    subtotal = sum((line["line_total"] for line in lines), Decimal("0.00"))
    tax = (subtotal * settings.SALES_TAX_RATE).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return render(request, "checkout.html", {
        "cart_items": lines,
        "subtotal": subtotal,
        "tax": tax,
        "tax_rate_percent": settings.SALES_TAX_RATE * 100,
        "total": subtotal + tax,
        "fulfillment": fulfillment,
        "delivery_address": delivery_address,
        "special_instructions": special_instructions,
        "error": error,
    }, status=400 if error else 200)


@login_required
def order_history_view(request):
    orders = (
        Order.objects.filter(customer__user=request.user)
        .prefetch_related("items")
        .order_by("-created_at")
    )
    return render(request, "order_history.html", {"orders": orders})


def _require_staff(request):
    if not request.user.is_authenticated:
        raise PermissionDenied
    if (
        not request.user.is_staff
        and not Staff.objects.filter(user=request.user).exists()
    ):
        raise PermissionDenied


def staff_queue_view(request):
    _require_staff(request)
    orders = (
        Order.objects.filter(status__in=("PENDING", "PREPPING", "READY"))
        .select_related("customer__user")
        .prefetch_related("items")
        .order_by("created_at")
    )
    return render(request, "staff_queue.html", {"orders": orders})


@require_POST
def update_order_status_view(request, order_id):
    _require_staff(request)
    order = get_object_or_404(Order, pk=order_id)
    next_status = {
        "PENDING": "PREPPING",
        "PREPPING": "READY",
        "READY": "COMPLETED",
    }.get(order.status)
    if not next_status or request.POST.get("status") != next_status:
        return HttpResponseBadRequest("Choose the next valid order status.")
    order.status = next_status
    order.save(update_fields=("status",))
    return redirect("staff_queue")
