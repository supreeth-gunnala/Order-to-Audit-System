from decimal import Decimal
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.master_data.models import Product, Customer, Supplier
from apps.inventory.models import InventoryItem, Purchase, PurchaseItem, StockLedger, StockMovementType
from apps.inventory.services import InventoryService
from apps.production.models import BillOfMaterials, ProductionRun, ProductionRunStatus
from apps.production.services import ProductionService
from apps.sales.models import SalesOrder, SalesOrderItem, OrderStatus, Invoice, PaymentMode
from apps.sales.services import SalesBillingService

User = get_user_model()


class Command(BaseCommand):
    help = "Executes the complete NIT Trichy Order-to-Audit Benchmark Scenario end-to-end and verifies all acceptance criteria."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Resets any previous benchmark transaction records prior to execution.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=" * 78))
        self.stdout.write(self.style.NOTICE("EXECUTING NIT TRICHY BENCHMARK SCENARIO: ORDER-TO-AUDIT SYSTEM"))
        self.stdout.write(self.style.NOTICE("=" * 78))

        if options.get('reset'):
            self.stdout.write("Resetting previous transactions...")
            # Clean transactions in reverse dependency order
            from apps.sales.models import PaymentAllocation, Payment, CreditNote, DispatchItem, Dispatch, InvoiceItem, Invoice, SalesOrderItem, SalesOrder
            from apps.production.models import ProductionConsumption, ProductionRun
            from apps.inventory.models import PurchaseItem, Purchase, StockLedger

            PaymentAllocation.objects.all().delete()
            Payment.objects.all().delete()
            CreditNote.objects.all().delete()
            DispatchItem.objects.all().delete()
            Dispatch.objects.all().delete()
            InvoiceItem.objects.all().delete()
            Invoice.objects.all().delete()
            SalesOrderItem.objects.all().delete()
            SalesOrder.objects.all().delete()
            ProductionConsumption.objects.all().delete()
            ProductionRun.objects.all().delete()
            PurchaseItem.objects.all().delete()
            Purchase.objects.all().delete()
            StockLedger.objects.exclude(movement_type=StockMovementType.OPENING_BALANCE).delete()

            # Reset inventory items to opening stock
            openings = {
                'RM-FLOUR': (Decimal('100.000'), Decimal('42.0000')),
                'RM-OIL': (Decimal('30.000'), Decimal('140.0000')),
                'RM-SPICE': (Decimal('5.000'), Decimal('200.0000')),
                'PKG-POUCH-200G': (Decimal('500.000'), Decimal('2.5000')),
                'PKG-CARTON': (Decimal('30.000'), Decimal('15.0000')),
                'FG-MRK-200G': (Decimal('50.000'), Decimal('31.1436')),
            }
            for sku, (qty, rate) in openings.items():
                InventoryItem.objects.filter(sku=sku).update(current_stock=qty, weighted_avg_cost=rate)
            self.stdout.write(self.style.SUCCESS("Transactions reset to initial benchmark state."))

        admin_user = User.objects.get(username='factory_admin')
        salesman_a = User.objects.get(username='salesman_a')
        salesman_b = User.objects.get(username='salesman_b')
        production_sup = User.objects.get(username='production_sup')

        product = Product.objects.get(sku='MRK-200G')
        retailer_a = Customer.objects.get(name='Retailer A')
        distributor_b = Customer.objects.get(name='Distributor B')
        supplier = Supplier.objects.first()

        flour_item = InventoryItem.objects.get(sku='RM-FLOUR')
        oil_item = InventoryItem.objects.get(sku='RM-OIL')
        spice_item = InventoryItem.objects.get(sku='RM-SPICE')
        pouch_item = InventoryItem.objects.get(sku='PKG-POUCH-200G')
        carton_item = InventoryItem.objects.get(sku='PKG-CARTON')
        fg_item = InventoryItem.objects.get(sku='FG-MRK-200G')

        # -------------------------------------------------------------
        # STEP 1: PURCHASE
        # -------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[STEP 1] Recording Purchase: 60 kg Flour @ ₹45/kg"))
        po_num = "PO-BENCH-001"
        purchase, _ = Purchase.objects.get_or_create(
            purchase_number=po_num,
            defaults={
                'supplier': supplier,
                'purchase_date': timezone.now().date(),
                'supplier_invoice_no': 'BILL-8890',
                'total_amount': Decimal('2700.00'),
                'created_by': production_sup,
                'notes': 'Benchmark purchase of 60 kg raw flour'
            }
        )
        PurchaseItem.objects.get_or_create(
            purchase=purchase,
            item=flour_item,
            defaults={
                'quantity': Decimal('60.000'),
                'unit': flour_item.uom,
                'unit_price': Decimal('45.00'),
                'total_price': Decimal('2700.00')
            }
        )
        InventoryService.post_purchase_receipt(purchase, user=production_sup)
        flour_item.refresh_from_db()

        self.stdout.write(f"  -> Flour Stock after purchase: {flour_item.current_stock} kg (Expected: 160.000 kg)")
        self.stdout.write(f"  -> Weighted-Average Flour Cost: ₹{flour_item.weighted_avg_cost:.4f}/kg (Expected: ₹43.1250/kg)")
        assert flour_item.current_stock == Decimal('160.000'), f"Expected 160 kg, got {flour_item.current_stock}"
        assert flour_item.weighted_avg_cost == Decimal('43.1250'), f"Expected 43.1250, got {flour_item.weighted_avg_cost}"
        self.stdout.write(self.style.SUCCESS("  [PASS] Step 1 Purchase and Weighted-Average Cost Verified."))

        # -------------------------------------------------------------
        # STEP 2 & 3: PRODUCTION RUN AND INVENTORY UPDATES
        # -------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[STEP 2 & 3] Murukku 200g Production Run (Batch Size: 1)"))
        bom = BillOfMaterials.objects.get(product=product, version=1)

        run, _ = ProductionRun.objects.get_or_create(
            run_number='PR-BENCH-001',
            defaults={
                'product': product,
                'bom': bom,
                'batch_size': Decimal('1.00'),
                'production_date': timezone.now().date(),
                'supervisor': production_sup,
                'expected_output': Decimal('200.00'),
                'actual_good_output': Decimal('188.00'),
                'status': ProductionRunStatus.DRAFT
            }
        )

        consumptions = {
            flour_item.id: Decimal('40.000'),
            oil_item.id: Decimal('10.500'),
            spice_item.id: Decimal('1.200'),
        }

        ProductionService.complete_run(
            production_run=run,
            raw_materials_consumed=consumptions,
            actual_good_output=Decimal('188.00'),
            damaged_pouches=Decimal('6.00'),
            cartons_used=Decimal('9.00'),
            labour_cost=Decimal('1200.00'),
            gas_power_cost=Decimal('600.00'),
            user=production_sup
        )
        run.refresh_from_db()

        # Check Stock Balances
        flour_item.refresh_from_db()
        oil_item.refresh_from_db()
        spice_item.refresh_from_db()
        pouch_item.refresh_from_db()
        carton_item.refresh_from_db()
        fg_item.refresh_from_db()

        self.stdout.write(f"  -> Closing Flour Stock: {flour_item.current_stock} kg (Expected: 120.000 kg)")
        self.stdout.write(f"  -> Closing Oil Stock: {oil_item.current_stock} L (Expected: 19.500 L)")
        self.stdout.write(f"  -> Closing Spice Mix Stock: {spice_item.current_stock} kg (Expected: 3.800 kg)")
        self.stdout.write(f"  -> Closing Pouches: {pouch_item.current_stock} pcs (Expected: 306.000 pcs)")
        self.stdout.write(f"  -> Closing Cartons: {carton_item.current_stock} pcs (Expected: 21.000 pcs)")
        self.stdout.write(f"  -> Finished Goods Stock: {fg_item.current_stock} pkts (Expected: 238.000 pkts)")

        assert flour_item.current_stock == Decimal('120.000')
        assert oil_item.current_stock == Decimal('19.500')
        assert spice_item.current_stock == Decimal('3.800')
        assert pouch_item.current_stock == Decimal('306.000')
        assert carton_item.current_stock == Decimal('21.000')
        assert fg_item.current_stock == Decimal('238.000')

        self.stdout.write(f"  -> Yield Variance: {run.yield_variance_percent}% [Flagged: {run.yield_variance_flagged}] (Expected: -6.00%, Flagged=True)")
        oil_c = run.consumptions.get(item=oil_item)
        self.stdout.write(f"  -> Oil Variance: {oil_c.variance_percent}% [Flagged: {oil_c.variance_flagged}] (Expected: +5.00%, Flagged=True)")
        assert run.yield_variance_percent == Decimal('-6.00')
        assert run.yield_variance_flagged is True
        assert oil_c.variance_percent == Decimal('5.00')
        assert oil_c.variance_flagged is True

        self.stdout.write(f"  -> Packaging Capacity Warning: {run.packaging_capacity_warning}")
        assert "Packaging Capacity Warning" in run.packaging_capacity_warning
        self.stdout.write(self.style.SUCCESS("  [PASS] Steps 2 & 3 Production Run & Stock Verification Succeeded."))

        # -------------------------------------------------------------
        # STEP 4: SALESMAN A ORDER (Retailer A: 150 pkts)
        # -------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[STEP 4] Salesman A Submitting Order for Retailer A (150 pkts)"))
        so_a, _ = SalesOrder.objects.get_or_create(
            order_number='SO-BENCH-001',
            defaults={
                'salesman': salesman_a,
                'customer': retailer_a,
                'status': OrderStatus.SUBMITTED,
                'notes': 'Benchmark Order 1 - 150 pkts Murukku 200g'
            }
        )
        so_item_a, _ = SalesOrderItem.objects.get_or_create(
            order=so_a,
            product=product,
            defaults={
                'quantity': Decimal('150.00'),
                'unit_price': product.selling_price,
                'subtotal': Decimal('7500.00'),
                'gst_rate': product.gst_rate,
                'tax_amount': Decimal('375.00'),
                'total_amount': Decimal('7875.00')
            }
        )
        so_a.subtotal = Decimal('7500.00')
        so_a.tax_estimate = Decimal('375.00')
        so_a.total_amount = Decimal('7875.00')
        so_a.save()
        self.stdout.write(f"  -> Order {so_a.order_number} submitted: {so_item_a.quantity} pkts @ ₹{so_item_a.unit_price} = ₹{so_a.total_amount}")
        self.stdout.write(self.style.SUCCESS("  [PASS] Step 4 Order Entry Succeeded."))

        # -------------------------------------------------------------
        # STEP 5: ADMIN APPROVAL, GST INVOICING & DISPATCH
        # -------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[STEP 5] Admin Approval, GST Invoicing & Dispatch (150 pkts)"))
        so_a.status = OrderStatus.APPROVED
        so_a.reviewed_by = admin_user
        so_a.reviewed_at = timezone.now()
        so_a.save()

        # Invoicing
        invoice_a = SalesBillingService.generate_invoice(so_a, user=admin_user)
        self.stdout.write(f"  -> Invoice Generated: {invoice_a.invoice_number}")
        self.stdout.write(f"  -> Taxable Value: ₹{invoice_a.taxable_value}")
        self.stdout.write(f"  -> CGST (2.5%): ₹{invoice_a.cgst_amount}")
        self.stdout.write(f"  -> SGST (2.5%): ₹{invoice_a.sgst_amount}")
        self.stdout.write(f"  -> Invoice Total: ₹{invoice_a.total_amount}")

        assert invoice_a.taxable_value == Decimal('7500.00')
        assert invoice_a.cgst_amount == Decimal('187.50')
        assert invoice_a.sgst_amount == Decimal('187.50')
        assert invoice_a.total_amount == Decimal('7875.00')

        # Dispatch
        dispatch_a = SalesBillingService.process_dispatch(
            order=so_a,
            items_to_dispatch={product.id: Decimal('150.00')},
            user=admin_user,
            transporter_name='SRT Logistics',
            vehicle_number='TN-45-AZ-1234'
        )
        fg_item.refresh_from_db()
        self.stdout.write(f"  -> Finished Goods Stock after dispatch: {fg_item.current_stock} pkts (Expected: 88.000 pkts)")
        assert fg_item.current_stock == Decimal('88.000')
        self.stdout.write(self.style.SUCCESS("  [PASS] Step 5 Approval, Invoicing (CGST+SGST) and Dispatch Succeeded."))

        # -------------------------------------------------------------
        # STEP 6: SALESMAN B ORDER & SHORTAGE VALIDATION
        # -------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[STEP 6] Salesman B Order for Distributor B (120 pkts) & Stock Shortage Check"))
        so_b, _ = SalesOrder.objects.get_or_create(
            order_number='SO-BENCH-002',
            defaults={
                'salesman': salesman_b,
                'customer': distributor_b,
                'status': OrderStatus.SUBMITTED,
                'notes': 'Benchmark Order 2 - 120 pkts Murukku 200g (Distributor Karnataka)'
            }
        )
        SalesOrderItem.objects.get_or_create(
            order=so_b,
            product=product,
            defaults={
                'quantity': Decimal('120.00'),
                'unit_price': product.selling_price,
                'subtotal': Decimal('6000.00'),
                'gst_rate': product.gst_rate,
                'tax_amount': Decimal('300.00'),
                'total_amount': Decimal('6300.00')
            }
        )
        so_b.subtotal = Decimal('6000.00')
        so_b.tax_estimate = Decimal('300.00')
        so_b.total_amount = Decimal('6300.00')
        so_b.status = OrderStatus.APPROVED
        so_b.save()

        # Attempting dispatch beyond stock must raise ValidationError
        shortage_detected = False
        try:
            SalesBillingService.process_dispatch(
                order=so_b,
                items_to_dispatch={product.id: Decimal('120.00')},
                user=admin_user
            )
        except ValidationError as e:
            shortage_detected = True
            self.stdout.write(self.style.WARNING(f"  -> System correctly caught stock shortage: {e}"))

        assert shortage_detected is True, "System failed to block invalid dispatch when stock is insufficient!"
        fg_item.refresh_from_db()
        assert fg_item.current_stock == Decimal('88.000'), "Stock must remain intact at 88 packets!"
        self.stdout.write(self.style.SUCCESS("  [PASS] Step 6 Stock Shortage (Requested: 120, Available: 88, Shortage: 32) Correctly Blocked."))

        # -------------------------------------------------------------
        # STEP 7: PAYMENT RECEIPT
        # -------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[STEP 7] Recording Payment: ₹4,000 from Retailer A"))
        payment = SalesBillingService.record_customer_payment(
            customer=retailer_a,
            amount=Decimal('4000.00'),
            payment_mode=PaymentMode.BANK_TRANSFER,
            reference_number='NEFT-SBI-443322',
            invoice_id=invoice_a.id,
            user=admin_user,
            notes='Benchmark partial payment on invoice'
        )
        invoice_a.refresh_from_db()
        self.stdout.write(f"  -> Invoice Total: ₹{invoice_a.total_amount}")
        self.stdout.write(f"  -> Amount Paid: ₹{invoice_a.paid_amount}")
        self.stdout.write(f"  -> Outstanding Balance: ₹{invoice_a.outstanding_amount} (Expected: ₹3875.00)")
        assert invoice_a.paid_amount == Decimal('4000.00')
        assert invoice_a.outstanding_amount == Decimal('3875.00')
        self.stdout.write(self.style.SUCCESS("  [PASS] Step 7 Payment & Receivables Update Succeeded."))

        # -------------------------------------------------------------
        # STEP 8: PRODUCTION COSTING VERIFICATION
        # -------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[STEP 8] Production Costing Verification"))
        self.stdout.write(f"  -> Direct Material Cost: ₹{run.direct_material_cost} (Expected: ₹4,055.00)")
        self.stdout.write(f"  -> Labour Cost: ₹{run.labour_cost} (Expected: ₹1,200.00)")
        self.stdout.write(f"  -> Gas & Power Cost: ₹{run.gas_power_cost} (Expected: ₹600.00)")
        self.stdout.write(f"  -> Total Production Cost: ₹{run.total_production_cost} (Expected: ₹5,855.00)")
        self.stdout.write(f"  -> Actual Good Packets: {run.actual_good_output}")
        self.stdout.write(f"  -> Cost Per Good Packet: ₹{run.cost_per_good_packet:.4f} (Expected: ~₹31.14)")

        assert run.direct_material_cost == Decimal('4055.00')
        assert run.labour_cost == Decimal('1200.00')
        assert run.gas_power_cost == Decimal('600.00')
        assert run.total_production_cost == Decimal('5855.00')
        assert run.actual_good_output == Decimal('188.00')
        assert round(run.cost_per_good_packet, 2) == Decimal('31.14')
        self.stdout.write(self.style.SUCCESS("  [PASS] Step 8 Costing Calculation Succeeded."))

        # -------------------------------------------------------------
        # STEP 9: MONTHLY REPORTS
        # -------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[STEP 9] Monthly Management & Audit Reports Validation"))
        from apps.reports.services import ReportService

        sales_reg = ReportService.get_sales_register()
        self.stdout.write(f"  -> Sales Register Count: {sales_reg.count()}")

        gst_summary = ReportService.get_gst_outward_summary()
        self.stdout.write(f"  -> Outward Taxable Supplies: ₹{gst_summary['totals']['taxable']}")
        self.stdout.write(f"  -> CGST Total: ₹{gst_summary['totals']['cgst']}")
        self.stdout.write(f"  -> SGST Total: ₹{gst_summary['totals']['sgst']}")
        assert gst_summary['totals']['taxable'] == Decimal('7500.00')
        assert gst_summary['totals']['cgst'] == Decimal('187.50')
        assert gst_summary['totals']['sgst'] == Decimal('187.50')

        receivables = ReportService.get_receivables_ageing()
        self.stdout.write(f"  -> Receivables Ageing Records: {len(receivables)}, Total Due: ₹{receivables[0]['total_due']}")
        assert receivables[0]['total_due'] == Decimal('3875.00')

        self.stdout.write(self.style.SUCCESS("  [PASS] Step 9 Audit & GST Reports Verified."))

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 78))
        self.stdout.write(self.style.SUCCESS("BENCHMARK SCENARIO COMPLETED WITH 100% ACCURACY & ACCEPTANCE."))
        self.stdout.write(self.style.SUCCESS("=" * 78))
