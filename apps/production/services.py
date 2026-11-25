from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import ProductionRun, ProductionConsumption, ProductionRunStatus, BillOfMaterials
from apps.inventory.models import InventoryItem, StockMovementType
from apps.inventory.services import InventoryService
from apps.core.models import AuditLog


class ProductionService:
    @classmethod
    @transaction.atomic
    def complete_run(
        cls,
        production_run: ProductionRun,
        raw_materials_consumed: dict,  # {item_id: actual_quantity}
        actual_good_output: Decimal,
        damaged_pouches: Decimal,
        cartons_used: Decimal,
        labour_cost: Decimal,
        gas_power_cost: Decimal,
        user=None
    ) -> ProductionRun:
        """
        Executes complete production run accounting:
        1. Validates BOM and inputs.
        2. Calculates planned vs actual consumption and variances.
        3. Flags variances exceeding tolerance (default 3%).
        4. Calculates direct materials, overheads, and cost per good packet.
        5. Atomically posts stock ledger deductions for raw materials and packaging.
        6. Atomically posts stock ledger addition for finished goods.
        7. Records audit logs.
        """
        if production_run.status == ProductionRunStatus.COMPLETED:
            raise ValidationError("This production run has already been completed and posted.")

        tolerance = Decimal(str(getattr(settings, 'VARIANCE_TOLERANCE_PERCENT', 3.0)))
        bom = production_run.bom
        batch_size = production_run.batch_size
        product = production_run.product

        # 1. Output and Yield Variance
        expected_output = bom.expected_output_packets * batch_size
        production_run.expected_output = expected_output
        production_run.actual_good_output = actual_good_output

        # Formula: Yield variance % = ((Actual output - Expected output) / Expected output) * 100
        yield_var = ((actual_good_output - expected_output) / expected_output) * Decimal('100.0')
        production_run.yield_variance_percent = yield_var.quantize(Decimal('0.01'))
        production_run.yield_variance_flagged = abs(yield_var) > tolerance

        # 2. Packaging capacity verification
        carton_capacity = cartons_used * Decimal(str(product.pieces_per_carton))
        packaging_warning = ""
        if cartons_used > 0 and carton_capacity < actual_good_output:
            diff = actual_good_output - carton_capacity
            packaging_warning = (
                f"Packaging Capacity Warning: {cartons_used:.0f} cartons can hold {carton_capacity:.0f} packets "
                f"({product.pieces_per_carton} pkts/carton), whereas actual good output is {actual_good_output:.0f} packets "
                f"({diff:.0f} packets unboxed/overflow)."
            )
        production_run.cartons_used = cartons_used
        production_run.damaged_packaging_pouches = damaged_pouches
        production_run.packaging_capacity_warning = packaging_warning

        # 3. Process Raw Material Consumptions
        direct_material_cost = Decimal('0.00')

        # Clear existing draft consumptions if any
        production_run.consumptions.all().delete()

        # Iterate over BOM components
        for comp in bom.components.select_related('item', 'unit').all():
            item = comp.item
            planned_qty = comp.quantity * batch_size

            if comp.is_packaging:
                # Packaging handled separately below according to specific counts
                continue

            actual_qty = raw_materials_consumed.get(item.id, planned_qty)
            if not isinstance(actual_qty, Decimal):
                actual_qty = Decimal(str(actual_qty))

            # Variance calculation: ((Actual - Planned) / Planned) * 100
            if planned_qty > Decimal('0.000'):
                var_pct = ((actual_qty - planned_qty) / planned_qty) * Decimal('100.0')
            else:
                var_pct = Decimal('0.00')

            flagged = abs(var_pct) > tolerance
            unit_cost = item.weighted_avg_cost
            line_cost = (actual_qty * unit_cost).quantize(Decimal('0.01'))
            direct_material_cost += line_cost

            ProductionConsumption.objects.create(
                production_run=production_run,
                item=item,
                planned_quantity=planned_qty,
                actual_quantity=actual_qty,
                unit=comp.unit,
                variance_percent=var_pct.quantize(Decimal('0.01')),
                variance_flagged=flagged,
                unit_cost=unit_cost,
                total_cost=line_cost,
                is_packaging=False,
                notes=f"Raw material issue for {production_run.run_number}"
            )

            # Deduct from inventory
            InventoryService.record_movement(
                item=item,
                movement_type=StockMovementType.PRODUCTION_ISSUE,
                quantity=-actual_qty,
                unit=comp.unit,
                unit_cost=unit_cost,
                source_document='ProductionRun',
                reference_id=production_run.run_number,
                user=user,
                notes=f"Production Run {production_run.run_number} raw material issue"
            )

        # 4. Packaging Materials Consumptions: Pouches and Cartons
        pouch_comp = bom.components.filter(item__item_type='PACKAGING', item__name__icontains='pouch').first()
        if pouch_comp:
            pouch_item = pouch_comp.item
            planned_pouches = pouch_comp.quantity * batch_size
            total_pouches_used = actual_good_output + damaged_pouches
            pouch_var_pct = ((total_pouches_used - planned_pouches) / planned_pouches) * Decimal('100.0')
            pouch_cost = (total_pouches_used * pouch_item.weighted_avg_cost).quantize(Decimal('0.01'))
            direct_material_cost += pouch_cost

            ProductionConsumption.objects.create(
                production_run=production_run,
                item=pouch_item,
                planned_quantity=planned_pouches,
                actual_quantity=total_pouches_used,
                unit=pouch_comp.unit,
                variance_percent=pouch_var_pct.quantize(Decimal('0.01')),
                variance_flagged=abs(pouch_var_pct) > tolerance,
                unit_cost=pouch_item.weighted_avg_cost,
                total_cost=pouch_cost,
                is_packaging=True,
                notes=f"Pouches: {actual_good_output} good + {damaged_pouches} damaged"
            )

            # Deduct good pouches
            InventoryService.record_movement(
                item=pouch_item,
                movement_type=StockMovementType.PRODUCTION_ISSUE,
                quantity=-actual_good_output,
                unit=pouch_comp.unit,
                unit_cost=pouch_item.weighted_avg_cost,
                source_document='ProductionRun',
                reference_id=production_run.run_number,
                user=user,
                notes=f"Pouches used for {actual_good_output} good packets"
            )

            # Deduct damaged pouches as scrap
            if damaged_pouches > Decimal('0.00'):
                InventoryService.record_movement(
                    item=pouch_item,
                    movement_type=StockMovementType.DAMAGE_SCRAP,
                    quantity=-damaged_pouches,
                    unit=pouch_comp.unit,
                    unit_cost=pouch_item.weighted_avg_cost,
                    source_document='ProductionRun',
                    reference_id=production_run.run_number,
                    user=user,
                    notes=f"Damaged packaging pouches during production run"
                )

        carton_comp = bom.components.filter(item__item_type='PACKAGING', item__name__icontains='carton').first()
        if carton_comp:
            carton_item = carton_comp.item
            planned_cartons = carton_comp.quantity * batch_size
            carton_var_pct = ((cartons_used - planned_cartons) / planned_cartons) * Decimal('100.0') if planned_cartons else Decimal('0.00')
            carton_cost = (cartons_used * carton_item.weighted_avg_cost).quantize(Decimal('0.01'))
            direct_material_cost += carton_cost

            ProductionConsumption.objects.create(
                production_run=production_run,
                item=carton_item,
                planned_quantity=planned_cartons,
                actual_quantity=cartons_used,
                unit=carton_comp.unit,
                variance_percent=carton_var_pct.quantize(Decimal('0.01')),
                variance_flagged=abs(carton_var_pct) > tolerance,
                unit_cost=carton_item.weighted_avg_cost,
                total_cost=carton_cost,
                is_packaging=True,
                notes=f"Cartons used: {cartons_used}"
            )

            # Deduct cartons
            InventoryService.record_movement(
                item=carton_item,
                movement_type=StockMovementType.PRODUCTION_ISSUE,
                quantity=-cartons_used,
                unit=carton_comp.unit,
                unit_cost=carton_item.weighted_avg_cost,
                source_document='ProductionRun',
                reference_id=production_run.run_number,
                user=user,
                notes=f"Outer cartons used for packing run {production_run.run_number}"
            )

        # 5. Costing Calculation
        production_run.direct_material_cost = direct_material_cost
        production_run.labour_cost = labour_cost
        production_run.gas_power_cost = gas_power_cost
        total_cost = direct_material_cost + labour_cost + gas_power_cost
        production_run.total_production_cost = total_cost

        cost_per_pkt = (total_cost / actual_good_output) if actual_good_output > Decimal('0.00') else Decimal('0.00')
        production_run.cost_per_good_packet = cost_per_pkt.quantize(Decimal('0.0001'))

        production_run.status = ProductionRunStatus.COMPLETED
        production_run.completed_at = timezone.now()
        production_run.save()

        # 6. Add Finished Goods to Inventory
        fg_item = InventoryItem.objects.filter(linked_product=product).first()
        if not fg_item:
            fg_item = InventoryItem.objects.filter(
                name__icontains=product.name,
                item_type='FINISHED_GOOD'
            ).first()

        if fg_item:
            InventoryService.record_movement(
                item=fg_item,
                movement_type=StockMovementType.PRODUCTION_OUTPUT,
                quantity=actual_good_output,
                unit=fg_item.uom,
                unit_cost=cost_per_pkt,
                source_document='ProductionRun',
                reference_id=production_run.run_number,
                user=user,
                notes=f"Finished goods output from Run {production_run.run_number} (Cost: ₹{cost_per_pkt:.2f}/pkt)"
            )

        AuditLog.objects.create(
            user=user,
            action='PRODUCTION_RUN_COMPLETED',
            entity='ProductionRun',
            entity_id=str(production_run.id),
            new_value=(
                f"Output: {actual_good_output} pkts, Direct Materials: ₹{direct_material_cost}, "
                f"Total Cost: ₹{total_cost}, Cost/Pkt: ₹{cost_per_pkt:.2f}"
            ),
            reason=f"Completed Run {production_run.run_number}"
        )

        return production_run
