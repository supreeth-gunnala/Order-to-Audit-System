from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import UnitOfMeasure, Product


class UnitConversionService:
    @classmethod
    def convert(cls, quantity: Decimal, from_unit: UnitOfMeasure, to_unit: UnitOfMeasure, product: Product = None) -> Decimal:
        """
        Centralized conversion logic.
        Guarantees physical dimensional compatibility.
        """
        if from_unit.code == to_unit.code:
            return quantity

        if not isinstance(quantity, Decimal):
            quantity = Decimal(str(quantity))

        # Handle container conversions if Product is provided
        if from_unit.code == 'ctn' and to_unit.code in ['pkt', 'pcs']:
            if not product:
                raise ValidationError("Product definition required to convert carton containers to individual packets.")
            return quantity * Decimal(str(product.pieces_per_carton))

        if from_unit.code in ['pkt', 'pcs'] and to_unit.code == 'ctn':
            if not product:
                raise ValidationError("Product definition required to convert packets to carton containers.")
            return quantity / Decimal(str(product.pieces_per_carton))

        # Standard physical unit conversion
        if from_unit.category != to_unit.category:
            raise ValidationError(
                f"Incompatible unit conversion requested: {from_unit.name} ({from_unit.category}) to {to_unit.name} ({to_unit.category})."
            )

        # Base conversion
        qty_in_base = quantity * from_unit.conversion_factor
        return qty_in_base / to_unit.conversion_factor
