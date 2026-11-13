import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("myapp", "0003_checkout_order_snapshots"),
    ]

    operations = [
        migrations.AlterField(
            model_name="orderitem",
            name="menu_item",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="myapp.menuitem",
            ),
        ),
    ]
