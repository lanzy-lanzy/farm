from decimal import Decimal
from django.test import TestCase
from sales.models import Product
from buyers.forms import OrderRequestForm
from api.serializers_v2 import OrderRequestPortalSerializer

class CatalogOrderingTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name="Eggs", product_type="eggs", unit_label="tray", unit_price=Decimal("180.00"))

    def test_web_uses_catalog_without_date(self):
        form = OrderRequestForm({"product": self.product.pk, "quantity": "2", "requested_unit_price": "1"})
        self.assertTrue(form.is_valid(), form.errors)
        order = form.save(commit=False)
        self.assertEqual(order.product_name, "Eggs")
        self.assertEqual(order.requested_unit_price, Decimal("180"))
        self.assertIsNone(order.requested_date)

    def test_api_overrides_client_price_and_name(self):
        serializer = OrderRequestPortalSerializer(data={"product_id": self.product.pk, "quantity": "2", "product_name": "Other", "requested_unit_price": "1"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["product_name"], "Eggs")
        self.assertEqual(serializer.validated_data["requested_unit_price"], Decimal("180"))

    def test_inactive_product_and_nonpositive_quantity_rejected(self):
        self.product.is_active = False
        self.product.save()
        self.assertFalse(OrderRequestForm({"product": self.product.pk, "quantity": "2"}).is_valid())
        serializer = OrderRequestPortalSerializer(data={"product_id": self.product.pk, "quantity": "2"})
        self.assertFalse(serializer.is_valid())
        self.product.is_active = True
        self.product.save()
        serializer = OrderRequestPortalSerializer(data={"product_id": self.product.pk, "quantity": "0"})
        self.assertFalse(serializer.is_valid())
