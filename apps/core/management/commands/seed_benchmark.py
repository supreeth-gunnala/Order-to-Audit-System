from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from apps.core.models import UserRole
from apps.master_data.models import (
    UnitOfMeasure, UnitCategory, ProductCategory, Product,
    Customer, CustomerType, Supplier, PriceList
)
from apps.inventory.models import InventoryItem, ItemType, StockMovementType, StockLedger
from apps.inventory.services import InventoryService
from apps.production.models import BillOfMaterials, BOMComponent

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds initial master data, demonstration users, opening inventory, and BOM for the Benchmark Scenario."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Resets existing transaction records before seeding benchmark state.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing Benchmark Seed Data..."))

        # 1. Users
        users_config = [
            ('salesman_a', 'Salesman A', UserRole.SALESMAN, '9876543210'),
            ('salesman_b', 'Salesman B', UserRole.SALESMAN, '9876543211'),
            ('factory_admin', 'Factory Admin', UserRole.FACTORY_ADMIN, '9876543220'),
            ('production_sup', 'Production Supervisor', UserRole.PRODUCTION_SUPERVISOR, '9876543230'),
            ('auditor', 'Internal Auditor', UserRole.ACCOUNTANT_AUDITOR, '9876543240'),
            ('owner', 'Factory Owner', UserRole.OWNER, '9876543250'),
        ]

        created_users = {}
        for username, full_name, role, phone in users_config:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': full_name,
                    'role': role,
                    'phone_number': phone,
                    'is_staff': role in [UserRole.FACTORY_ADMIN, UserRole.OWNER],
                }
            )
            user.set_password('pass1234')
            user.save()
            created_users[username] = user
            status_str = "Created" if created else "Updated"
            self.stdout.write(f"  - User {username} ({role}): {status_str} (Password: pass1234)")

        admin_user = created_users['factory_admin']

        # 2. Units of Measure
        uom_kg, _ = UnitOfMeasure.objects.get_or_create(
            code='kg', defaults={'name': 'Kilogram', 'category': UnitCategory.MASS, 'conversion_factor': Decimal('1.000000')}
        )
        uom_g, _ = UnitOfMeasure.objects.get_or_create(
            code='g', defaults={'name': 'Gram', 'category': UnitCategory.MASS, 'base_unit': uom_kg, 'conversion_factor': Decimal('0.001000')}
        )
        uom_l, _ = UnitOfMeasure.objects.get_or_create(
            code='L', defaults={'name': 'Litre', 'category': UnitCategory.VOLUME, 'conversion_factor': Decimal('1.000000')}
        )
        uom_ml, _ = UnitOfMeasure.objects.get_or_create(
            code='ml', defaults={'name': 'Millilitre', 'category': UnitCategory.VOLUME, 'base_unit': uom_l, 'conversion_factor': Decimal('0.001000')}
        )
        uom_pcs, _ = UnitOfMeasure.objects.get_or_create(
            code='pcs', defaults={'name': 'Piece', 'category': UnitCategory.COUNT, 'conversion_factor': Decimal('1.000000')}
        )
        uom_pkt, _ = UnitOfMeasure.objects.get_or_create(
            code='pkt', defaults={'name': 'Packet', 'category': UnitCategory.COUNT, 'conversion_factor': Decimal('1.000000')}
        )
        uom_ctn, _ = UnitOfMeasure.objects.get_or_create(
            code='ctn', defaults={'name': 'Carton', 'category': UnitCategory.CONTAINER, 'conversion_factor': Decimal('1.000000')}
        )

        # 3. Product Categories & Master Product
        category, _ = ProductCategory.objects.get_or_create(
            name='Traditional Savouries',
            defaults={'description': 'Authentic South Indian crispy snacks'}
        )

        product, p_created = Product.objects.get_or_create(
            sku='MRK-200G',
            defaults={
                'name': 'Murukku 200 g',
                'category': category,
                'pack_size': Decimal('200.00'),
                'pack_unit': uom_g,
                'selling_price': Decimal('50.00'),  # Benchmark selling price ₹50/packet
                'hsn_code': '19059040',
                'gst_rate': Decimal('5.00'),       # Benchmark GST 5%
                'uom': uom_pkt,
                'pieces_per_carton': 20,           # 20 packets per carton
                'is_active': True,
            }
        )
        self.stdout.write(f"  - Product: {product.name} (SKU: {product.sku}, Price: ₹{product.selling_price})")

        # 4. Customers
        customer_a, _ = Customer.objects.get_or_create(
            name='Retailer A',
            defaults={
                'customer_type': CustomerType.RETAILER,
                'gstin': '33AABCR1234A1Z1',  # Tamil Nadu GSTIN
                'state': 'Tamil Nadu',
                'billing_address': '45 Gandhi Market Road, Trichy - 620001, Tamil Nadu',
                'shipping_address': '45 Gandhi Market Road, Trichy - 620001, Tamil Nadu',
                'assigned_salesman': created_users['salesman_a'],
                'phone': '9443123456',
                'email': 'retailer_a@example.com'
            }
        )

        customer_b, _ = Customer.objects.get_or_create(
            name='Distributor B',
            defaults={
                'customer_type': CustomerType.DISTRIBUTOR,
                'gstin': '29BBBCD5678B1Z2',  # Karnataka GSTIN
                'state': 'Karnataka',
                'billing_address': '108 Commercial Street, Bengaluru - 560001, Karnataka',
                'shipping_address': '108 Commercial Street, Bengaluru - 560001, Karnataka',
                'assigned_salesman': created_users['salesman_b'],
                'phone': '9845123456',
                'email': 'distributor_b@example.com'
            }
        )
        self.stdout.write(f"  - Customers: {customer_a.name} (TN) & {customer_b.name} (KA)")

        # 5. Suppliers
        supplier, _ = Supplier.objects.get_or_create(
            name='Venkateswara Flour & Agro Mills',
            defaults={
                'gstin': '33AAAFV9876A1Z9',
                'state': 'Tamil Nadu',
                'address': 'Plot 4, Industrial Estate, Madurai Road, Trichy, Tamil Nadu',
                'contact_person': 'R. Venkatesh',
                'phone': '9442198765',
                'email': 'venkatesh_mills@example.com'
            }
        )

        # 6. Inventory Items (Raw Materials, Packaging, Finished Goods)
        items_def = [
            ('RM-FLOUR', 'Flour', ItemType.RAW_MATERIAL, uom_kg, Decimal('42.0000'), Decimal('100.000')),
            ('RM-OIL', 'Cooking oil', ItemType.RAW_MATERIAL, uom_l, Decimal('140.0000'), Decimal('30.000')),
            ('RM-SPICE', 'Spice mix', ItemType.RAW_MATERIAL, uom_kg, Decimal('200.0000'), Decimal('5.000')),
            ('PKG-POUCH-200G', '200 g pouch', ItemType.PACKAGING, uom_pcs, Decimal('2.5000'), Decimal('500.000')),
            ('PKG-CARTON', 'Carton', ItemType.PACKAGING, uom_pcs, Decimal('15.0000'), Decimal('30.000')),
            ('FG-MRK-200G', 'Finished Murukku 200 g', ItemType.FINISHED_GOOD, uom_pkt, Decimal('31.1436'), Decimal('50.000')),
        ]

        inv_items = {}
        for sku, name, item_type, uom, rate, opening_qty in items_def:
            linked = product if item_type == ItemType.FINISHED_GOOD else None
            item, created = InventoryItem.objects.get_or_create(
                sku=sku,
                defaults={
                    'name': name,
                    'item_type': item_type,
                    'uom': uom,
                    'weighted_avg_cost': rate,
                    'linked_product': linked,
                    'current_stock': Decimal('0.000')  # populated via opening movement below
                }
            )
            inv_items[sku] = item

            # Record opening balance movement if not already recorded
            if not StockLedger.objects.filter(item=item, movement_type=StockMovementType.OPENING_BALANCE).exists():
                InventoryService.record_movement(
                    item=item,
                    movement_type=StockMovementType.OPENING_BALANCE,
                    quantity=opening_qty,
                    unit=uom,
                    unit_cost=rate,
                    source_document='OpeningBalance',
                    reference_id='INIT-2026',
                    user=admin_user,
                    notes=f"Benchmark initial opening stock: {opening_qty} {uom.code} @ ₹{rate}"
                )
            self.stdout.write(f"  - Inventory: {item.name} -> {item.current_stock} {item.uom.code} @ ₹{item.weighted_avg_cost:.2f}")

        # 7. Bill of Materials (BOM) for Murukku 200 g
        bom, b_created = BillOfMaterials.objects.get_or_create(
            product=product,
            version=1,
            defaults={
                'name': 'Standard Murukku 200g Recipe (200 pkts/batch)',
                'expected_output_packets': Decimal('200.00'),
                'is_active': True,
                'notes': 'Benchmark standard recipe: 1 batch produces 200 packets of 200g each'
            }
        )

        bom_components = [
            (inv_items['RM-FLOUR'], Decimal('40.0000'), uom_kg, False, Decimal('42.00')),
            (inv_items['RM-OIL'], Decimal('10.0000'), uom_l, False, Decimal('140.00')),
            (inv_items['RM-SPICE'], Decimal('1.2000'), uom_kg, False, Decimal('200.00')),
            (inv_items['PKG-POUCH-200G'], Decimal('200.0000'), uom_pcs, True, Decimal('2.50')),
            (inv_items['PKG-CARTON'], Decimal('10.0000'), uom_pcs, True, Decimal('15.00')),
        ]

        for item, qty, uom, is_pkg, rate in bom_components:
            BOMComponent.objects.get_or_create(
                bom=bom,
                item=item,
                defaults={
                    'quantity': qty,
                    'unit': uom,
                    'is_packaging': is_pkg,
                    'standard_rate': rate
                }
            )

        self.stdout.write(self.style.SUCCESS("Benchmark Master Data successfully seeded."))
