from decimal import Decimal

from django.db import migrations, models


def backfill_order_item_snapshots(apps, schema_editor):
    OrderItem = apps.get_model("myapp", "OrderItem")
    database = schema_editor.connection.alias
    for order_item in OrderItem.objects.using(database).select_related("menu_item").iterator():
        order_item.item_name = order_item.menu_item.name
        order_item.unit_price = order_item.menu_item.price
        order_item.save(update_fields=("item_name", "unit_price"))


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0002_rebase_prices_to_12oz"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_address",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="order",
            name="tax_rate",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0.02"),
                max_digits=5,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="tax_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=8,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="item_name",
            field=models.CharField(default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="orderitem",
            name="size",
            field=models.CharField(blank=True, default="", max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="orderitem",
            name="unit_price",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=6,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_order_item_snapshots, migrations.RunPython.noop),
    ]
