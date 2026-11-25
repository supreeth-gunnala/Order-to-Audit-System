from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.models import UserRole
from apps.master_data.models import (
    UnitOfMeasure, UnitCategory, ProductCategory, Product,
    Customer, CustomerType, Supplier
)
from apps.master_data.services import UnitConversionService
from apps.inventory.models import InventoryItem, ItemType, Purchase, PurchaseItem, StockLedger, StockMovementType
from apps.inventory.services import InventoryService
from apps.production.models import BillOfMaterials, BOMComponent, ProductionRun, ProductionRunStatus
from apps.production.services import ProductionService
from apps.sales.models import SalesOrder, SalesOrderItem, OrderStatus, Invoice, InvoiceStatus, PaymentMode
from apps.sales.services import SalesBillingService

User = get_user_model()


class OrderToAuditComprehensiveTests(TestCase):
    def setUp(self):
        # 1. Users for each role
        self.salesman_a = User.objects.create_user(username='salesman_a', password='pass1234', role=UserRole.SALESMAN)
        self.salesman_b = User.objects.create_user(username='salesman_b', password='pass1234', role=UserRole.SALESMAN)
        self.factory_admin = User.objects.create_user(username='factory_admin', password='pass1234', role=UserRole.FACTORY_ADMIN, is_staff=True)
        self.production_sup = User.objects.create_user(username='production_sup', password='pass1234', role=UserRole.PRODUCTION_SUPERVISOR)
        self.auditor = User.objects.create_user(username='auditor', password='pass1234', role=UserRole.ACCOUNTANT_AUDITOR)
        self.owner = User.objects.create_user(username='owner', password='pass1234', role=UserRole.OWNER)

        # 2. Units
        self.uom_kg = UnitOfMeasure.objects.create(code='kg', name='Kilogram', category=UnitCategory.MASS, conversion_factor=Decimal('1.000000'))
        self.uom_g = UnitOfMeasure.objects.create(code='g', name='Gram', category=UnitCategory.MASS, base_unit=self.uom_kg, conversion_factor=Decimal('0.001000'))
        self.uom_l = UnitOfMeasure.objects.create(code='L', name='Litre', category=UnitCategory.VOLUME, conversion_factor=Decimal('1.000000'))
        self.uom_pcs = UnitOfMeasure.objects.create(code='pcs', name='Piece', category=UnitCategory.COUNT, conversion_factor=Decimal('1.000000'))
        self.uom_pkt = UnitOfMeasure.objects.create(code='pkt', name='Packet', category=UnitCategory.COUNT, conversion_factor=Decimal('1.000000'))
        self.uom_ctn = UnitOfMeasure.objects.create(code='ctn', name='Carton', category=UnitCategory.CONTAINER, conversion_factor=Decimal('1.000000'))

        # 3. Product & Customers
        cat = ProductCategory.objects.create(name='Murukku')
        self.product = Product.objects.create(
            sku='MRK-200G',
            name='Murukku 200 g',
            category=cat,
            pack_size=Decimal('200.00'),
            pack_unit=self.uom_g,
            selling_price=Decimal('50.00'),
            hsn_code='19059040',
            gst_rate=Decimal('5.00'),
            uom=self.uom_pkt,
            pieces_per_carton=20
        )

        self.retailer_a = Customer.objects.create(
            name='Retailer A', customer_type=CustomerType.RETAILER, state='Tamil Nadu',
            gstin='33AABCR1234A1Z1', billing_address='Trichy', phone='9443123456',
            assigned_salesman=self.salesman_a
        )
        self.distributor_b = Customer.objects.create(
            name='Distributor B', customer_type=CustomerType.DISTRIBUTOR, state='Karnataka',
            gstin='29BBBCD5678B1Z2', billing_address='Bengaluru', phone='9845123456',
            assigned_salesman=self.salesman_b
        )

        self.supplier = Supplier.objects.create(name='Venkateswara Flour Mills', state='Tamil Nadu', address='Trichy', phone='9442198765')

        # 4. Opening Inventory
        self.flour = InventoryItem.objects.create(sku='RM-FLOUR', name='Flour', item_type=ItemType.RAW_MATERIAL, uom=self.uom_kg, weighted_avg_cost=Decimal('42.0000'), current_stock=Decimal('100.000'))
        self.oil = InventoryItem.objects.create(sku='RM-OIL', name='Cooking oil', item_type=ItemType.RAW_MATERIAL, uom=self.uom_l, weighted_avg_cost=Decimal('140.0000'), current_stock=Decimal('30.000'))
        self.spice = InventoryItem.objects.create(sku='RM-SPICE', name='Spice mix', item_type=ItemType.RAW_MATERIAL, uom=self.uom_kg, weighted_avg_cost=Decimal('200.0000'), current_stock=Decimal('5.000'))
        self.pouches = InventoryItem.objects.create(sku='PKG-POUCH-200G', name='200 g pouch', item_type=ItemType.PACKAGING, uom=self.uom_pcs, weighted_avg_cost=Decimal('2.5000'), current_stock=Decimal('500.000'))
        self.cartons = InventoryItem.objects.create(sku='PKG-CARTON', name='Carton', item_type=ItemType.PACKAGING, uom=self.uom_pcs, weighted_avg_cost=Decimal('15.0000'), current_stock=Decimal('30.000'))
        self.fg_murukku = InventoryItem.objects.create(sku='FG-MRK-200G', name='Finished Murukku 200 g', item_type=ItemType.FINISHED_GOOD, uom=self.uom_pkt, weighted_avg_cost=Decimal('31.1436'), current_stock=Decimal('50.000'), linked_product=self.product)

        # 5. Bill of Materials
        self.bom = BillOfMaterials.objects.create(product=self.product, version=1, name='Standard Murukku 200g Recipe', expected_output_packets=Decimal('200.00'))
        BOMComponent.objects.create(bom=self.bom, item=self.flour, quantity=Decimal('40.0000'), unit=self.uom_kg, is_packaging=False, standard_rate=Decimal('42.00'))
        BOMComponent.objects.create(bom=self.bom, item=self.oil, quantity=Decimal('10.0000'), unit=self.uom_l, is_packaging=False, standard_rate=Decimal('140.00'))
        BOMComponent.objects.create(bom=self.bom, item=self.spice, quantity=Decimal('1.2000'), unit=self.uom_kg, is_packaging=False, standard_rate=Decimal('200.00'))
        BOMComponent.objects.create(bom=self.bom, item=self.pouches, quantity=Decimal('200.0000'), unit=self.uom_pcs, is_packaging=True, standard_rate=Decimal('2.50'))
        BOMComponent.objects.create(bom=self.bom, item=self.cartons, quantity=Decimal('10.0000'), unit=self.uom_pcs, is_packaging=True, standard_rate=Decimal('15.00'))

    def test_a_weighted_average_flour_valuation(self):
        """Test A: Purchase 60 kg @ ₹45. (100*42 + 60*45)/160 = ₹43.1250/kg."""
        po = Purchase.objects.create(
            purchase_number='PO-TEST-001', supplier=self.supplier, purchase_date=timezone.now().date(),
            total_amount=Decimal('2700.00'), created_by=self.production_sup
        )
        PurchaseItem.objects.create(purchase=po, item=self.flour, quantity=Decimal('60.000'), unit=self.uom_kg, unit_price=Decimal('45.00'), total_price=Decimal('2700.00'))
        InventoryService.post_purchase_receipt(po, user=self.production_sup)
        self.flour.refresh_from_db()
        self.assertEqual(self.flour.current_stock, Decimal('160.000'))
        self.assertEqual(self.flour.weighted_avg_cost, Decimal('43.1250'))

    def test_b_through_j_production_and_variances(self):
        """Tests B through J: Production run material consumption, stock deductions, yield & oil variance."""
        # Execute purchase first to bring flour to 160 kg @ ₹43.1250
        self.test_a_weighted_average_flour_valuation()

        run = ProductionRun.objects.create(
            run_number='PR-TEST-001', product=self.product, bom=self.bom,
            batch_size=Decimal('1.00'), production_date=timezone.now().date(),
            supervisor=self.production_sup, expected_output=Decimal('200.00'),
            actual_good_output=Decimal('188.00')
        )
        consumptions = {
            self.flour.id: Decimal('40.000'),
            self.oil.id: Decimal('10.500'),
            self.spice.id: Decimal('1.200'),
        }
        ProductionService.complete_run(
            production_run=run, raw_materials_consumed=consumptions,
            actual_good_output=Decimal('188.00'), damaged_pouches=Decimal('6.00'),
            cartons_used=Decimal('9.00'), labour_cost=Decimal('1200.00'),
            gas_power_cost=Decimal('600.00'), user=self.production_sup
        )

        self.flour.refresh_from_db()
        self.oil.refresh_from_db()
        self.spice.refresh_from_db()
        self.pouches.refresh_from_db()
        self.cartons.refresh_from_db()
        self.fg_murukku.refresh_from_db()

        # Test B: 100 + 60 - 40 = 120 kg flour
        self.assertEqual(self.flour.current_stock, Decimal('120.000'))
        # Test C: 30 - 10.5 = 19.5 L oil
        self.assertEqual(self.oil.current_stock, Decimal('19.500'))
        # Test D: 5 - 1.2 = 3.8 kg spice mix
        self.assertEqual(self.spice.current_stock, Decimal('3.800'))
        # Test E: 500 - 188 - 6 = 306 pouches
        self.assertEqual(self.pouches.current_stock, Decimal('306.000'))
        # Test F: 30 - 9 = 21 cartons
        self.assertEqual(self.cartons.current_stock, Decimal('21.000'))
        # Test G: 50 + 188 = 238 finished goods
        self.assertEqual(self.fg_murukku.current_stock, Decimal('238.000'))

        # Test I: Yield variance: (188 - 200)/200 * 100 = -6%
        run.refresh_from_db()
        self.assertEqual(run.yield_variance_percent, Decimal('-6.00'))
        self.assertTrue(run.yield_variance_flagged)

        # Test J: Oil consumption variance: (10.5 - 10)/10 * 100 = +5%
        oil_c = run.consumptions.get(item=self.oil)
        self.assertEqual(oil_c.variance_percent, Decimal('5.00'))
        self.assertTrue(oil_c.variance_flagged)

        # Test N: Costing: ₹4,055 material + ₹1,200 labour + ₹600 power = ₹5,855 total. ₹5,855 / 188 = ~₹31.14
        self.assertEqual(run.direct_material_cost, Decimal('4055.00'))
        self.assertEqual(run.labour_cost, Decimal('1200.00'))
        self.assertEqual(run.gas_power_cost, Decimal('600.00'))
        self.assertEqual(run.total_production_cost, Decimal('5855.00'))
        self.assertEqual(round(run.cost_per_good_packet, 2), Decimal('31.14'))

    def test_k_gst_invoicing_and_dispatch(self):
        """Test K, H, L: Salesman A order for 150 pkts -> GST Invoice (₹7500 + ₹187.50 CGST + ₹187.50 SGST = ₹7875) -> Dispatch (238 - 150 = 88) -> Payment ₹4000 (Due ₹3875)."""
        self.test_b_through_j_production_and_variances()

        # Sales Order
        order = SalesOrder.objects.create(order_number='SO-TEST-001', salesman=self.salesman_a, customer=self.retailer_a, status=OrderStatus.APPROVED)
        SalesOrderItem.objects.create(order=order, product=self.product, quantity=Decimal('150.00'), unit_price=Decimal('50.00'), subtotal=Decimal('7500.00'), gst_rate=Decimal('5.00'), tax_amount=Decimal('375.00'), total_amount=Decimal('7875.00'))

        # Invoicing
        invoice = SalesBillingService.generate_invoice(order, user=self.factory_admin)
        self.assertEqual(invoice.taxable_value, Decimal('7500.00'))
        self.assertEqual(invoice.cgst_amount, Decimal('187.50'))
        self.assertEqual(invoice.sgst_amount, Decimal('187.50'))
        self.assertEqual(invoice.total_amount, Decimal('7875.00'))
        self.assertEqual(invoice.outstanding_amount, Decimal('7875.00'))

        # Dispatch 150 packets (Test H: 238 - 150 = 88)
        SalesBillingService.process_dispatch(order, {self.product.id: Decimal('150.00')}, user=self.factory_admin)
        self.fg_murukku.refresh_from_db()
        self.assertEqual(self.fg_murukku.current_stock, Decimal('88.000'))

        # Payment (Test L: ₹7875 - ₹4000 = ₹3875)
        payment = SalesBillingService.record_customer_payment(
            customer=self.retailer_a, amount=Decimal('4000.00'),
            payment_mode=PaymentMode.BANK_TRANSFER, invoice_id=invoice.id,
            user=self.factory_admin
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal('4000.00'))
        self.assertEqual(invoice.outstanding_amount, Decimal('3875.00'))
        self.assertEqual(invoice.status, InvoiceStatus.PARTIALLY_PAID)

    def test_m_distributor_b_shortage_validation(self):
        """Test M: Distributor B orders 120 pkts, available 88, shortage 32 -> Dispatch must be blocked."""
        self.test_k_gst_invoicing_and_dispatch()

        order_b = SalesOrder.objects.create(order_number='SO-TEST-002', salesman=self.salesman_b, customer=self.distributor_b, status=OrderStatus.APPROVED)
        SalesOrderItem.objects.create(order=order_b, product=self.product, quantity=Decimal('120.00'), unit_price=Decimal('50.00'), subtotal=Decimal('6000.00'), gst_rate=Decimal('5.00'), tax_amount=Decimal('300.00'), total_amount=Decimal('6300.00'))

        with self.assertRaises(ValidationError) as ctx:
            SalesBillingService.process_dispatch(order_b, {self.product.id: Decimal('120.00')}, user=self.factory_admin)

        self.assertIn("Insufficient finished goods stock", str(ctx.exception))
        self.fg_murukku.refresh_from_db()
        self.assertEqual(self.fg_murukku.current_stock, Decimal('88.000'))

    def test_o_role_permissions(self):
        """Test O: Salesman cannot access admin-only URLs."""
        client = Client()
        client.login(username='salesman_a', password='pass1234')

        # Attempt to access admin audit trail
        res = client.get(reverse('core:audit_trail'))
        self.assertEqual(res.status_code, 403)

        # Factory admin can access
        client.login(username='factory_admin', password='pass1234')
        res = client.get(reverse('core:audit_trail'))
        self.assertEqual(res.status_code, 200)

    def test_p_credit_note_workflow(self):
        """Test P: Lawful cancellation retains original invoice and creates CreditNote."""
        order = SalesOrder.objects.create(order_number='SO-CN-001', salesman=self.salesman_a, customer=self.retailer_a, status=OrderStatus.APPROVED)
        SalesOrderItem.objects.create(order=order, product=self.product, quantity=Decimal('10.00'), unit_price=Decimal('50.00'), subtotal=Decimal('500.00'), gst_rate=Decimal('5.00'), tax_amount=Decimal('25.00'), total_amount=Decimal('525.00'))
        inv = SalesBillingService.generate_invoice(order, user=self.factory_admin)

        cn = SalesBillingService.cancel_invoice_via_credit_note(inv, reason="Customer cancelled order prior to shipment", user=self.factory_admin)
        inv.refresh_from_db()
        self.assertEqual(inv.status, InvoiceStatus.CANCELLED)
        self.assertEqual(inv.outstanding_amount, Decimal('0.00'))
        self.assertEqual(cn.total_amount, Decimal('525.00'))
        self.assertEqual(cn.invoice, inv)

    def test_q_stock_ledger_reconciliation(self):
        """Test Q: Stock ledger balances reconcile with calculated movements."""
        init_balance = self.flour.current_stock
        delta = Decimal('25.000')
        entry = InventoryService.record_movement(
            item=self.flour, movement_type=StockMovementType.ADJUSTMENT,
            quantity=delta, unit=self.uom_kg, unit_cost=Decimal('42.00'),
            source_document='Test', reference_id='RECON-001'
        )
        self.flour.refresh_from_db()
        self.assertEqual(entry.balance_before, init_balance)
        self.assertEqual(entry.balance_after, init_balance + delta)
        self.assertEqual(self.flour.current_stock, init_balance + delta)

    def test_r_duplicate_dispatch_prevention(self):
        """Test R: Prevent double dispatching an order."""
        self.test_b_through_j_production_and_variances()
        order = SalesOrder.objects.create(order_number='SO-DISP-001', salesman=self.salesman_a, customer=self.retailer_a, status=OrderStatus.APPROVED)
        SalesOrderItem.objects.create(order=order, product=self.product, quantity=Decimal('20.00'), unit_price=Decimal('50.00'), subtotal=Decimal('1000.00'), gst_rate=Decimal('5.00'), tax_amount=Decimal('50.00'), total_amount=Decimal('1050.00'))

        SalesBillingService.process_dispatch(order, {self.product.id: Decimal('20.00')}, user=self.factory_admin)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.DISPATCHED)

        # Subsequent dispatch must fail because order is already DISPATCHED
        with self.assertRaises(ValidationError):
            SalesBillingService.process_dispatch(order, {self.product.id: Decimal('20.00')}, user=self.factory_admin)
