# -*- coding: utf-8 -*-
"""Management command to backup the PostgreSQL database and delete all demo/business
records while preserving the schema, user accounts, and configuration.

Usage:
    python manage.py clear_demo_data
"""

import os
import subprocess
import datetime
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction

# Import models
from apps.sales.models import (
    SalesOrder,
    SalesOrderItem,
    Invoice,
    InvoiceItem,
    Dispatch,
    DispatchItem,
    Payment,
    PaymentAllocation,
    CreditNote,
)
from apps.production.models import (
    ProductionRun,
    ProductionConsumption,
    BillOfMaterials,
    BOMComponent,
)
from apps.inventory.models import (
    InventoryItem,
    StockLedger,
    Purchase,
    PurchaseItem,
)
from apps.master_data.models import (
    Product,
    Customer,
    Supplier,
    PriceList,
    UnitOfMeasure,
    ProductCategory,
)
from apps.core.models import AuditLog


class Command(BaseCommand):
    help = "Backup database and delete all demo/business data (preserve users & schema)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting demo data cleanup..."))

        # ---------------------------------------------------------------------
        # 1. Database backup using pg_dump
        # ---------------------------------------------------------------------
        backup_dir = os.path.join(settings.BASE_DIR, "backup")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"{settings.DATABASES['default']['NAME']}_{timestamp}.sql")
        env = os.environ.copy()
        env.update({
            "PGHOST": settings.DATABASES['default'].get('HOST', 'localhost'),
            "PGPORT": str(settings.DATABASES['default'].get('PORT', '5432')),
            "PGUSER": settings.DATABASES['default'].get('USER', 'postgres'),
            "PGPASSWORD": settings.DATABASES['default'].get('PASSWORD', '1234'),
        })
        dump_cmd = [
            "pg_dump",
            "-Fc",
            "-f",
            backup_file,
            settings.DATABASES['default']['NAME'],
        ]
        try:
            subprocess.check_call(dump_cmd, env=env)
            self.stdout.write(self.style.SUCCESS(f"Database backup created at {backup_file}"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"pg_dump notification: {e} (Continuing cleanup)"))

        # ---------------------------------------------------------------------
        # 2. Delete data in strict reverse‑dependency order
        # ---------------------------------------------------------------------
        with transaction.atomic():
            summary = {}

            def delete_qs(qs, name):
                count = qs.count()
                if count:
                    qs.delete()
                summary[name] = count

            # Audit logs
            delete_qs(AuditLog.objects.all(), "AuditLog")

            # Sales - Payments & Credit Notes
            delete_qs(PaymentAllocation.objects.all(), "PaymentAllocation")
            delete_qs(Payment.objects.all(), "Payment")
            delete_qs(CreditNote.objects.all(), "CreditNote")

            # Sales - Dispatch & Invoices
            delete_qs(DispatchItem.objects.all(), "DispatchItem")
            delete_qs(Dispatch.objects.all(), "Dispatch")
            delete_qs(InvoiceItem.objects.all(), "InvoiceItem")
            delete_qs(Invoice.objects.all(), "Invoice")

            # Sales - Orders
            delete_qs(SalesOrderItem.objects.all(), "SalesOrderItem")
            delete_qs(SalesOrder.objects.all(), "SalesOrder")

            # Master Data - Price Lists
            delete_qs(PriceList.objects.all(), "PriceList")

            # Production - Runs & Consumption
            delete_qs(ProductionConsumption.objects.all(), "ProductionConsumption")
            delete_qs(ProductionRun.objects.all(), "ProductionRun")

            # Production - BOMs
            delete_qs(BOMComponent.objects.all(), "BOMComponent")
            delete_qs(BillOfMaterials.objects.all(), "BillOfMaterials")

            # Inventory - Stock Movements & Purchases
            delete_qs(StockLedger.objects.all(), "StockLedger")
            delete_qs(PurchaseItem.objects.all(), "PurchaseItem")
            delete_qs(Purchase.objects.all(), "Purchase")

            # Inventory - Items (Raw Materials, Packaging, Finished Goods)
            delete_qs(InventoryItem.objects.all(), "InventoryItem")

            # Master Data - Products, Customers, Suppliers
            delete_qs(Product.objects.all(), "Product")
            delete_qs(Customer.objects.all(), "Customer")
            delete_qs(Supplier.objects.all(), "Supplier")

        # ---------------------------------------------------------------------
        # 3. Report summary
        # ---------------------------------------------------------------------
        self.stdout.write(self.style.SUCCESS("\nDemo data cleanup completed successfully!"))
        self.stdout.write(self.style.NOTICE("Summary of business records deleted:"))
        for model_name, count in summary.items():
            self.stdout.write(f"  - {model_name}: {count} records removed")

        self.stdout.write(self.style.SUCCESS(
            "\nAll business tables are now clean and empty."
            "\nUser accounts, roles, database schema, units of measure, and system configuration are fully preserved."
        ))
