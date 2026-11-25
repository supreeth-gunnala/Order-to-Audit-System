from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.core.permissions import admin_only
from .models import Product, ProductCategory, Customer, CustomerType, Supplier, UnitOfMeasure, UnitCategory
from .services import UnitConversionService


@login_required
@admin_only
def product_list(request):
    products = Product.objects.select_related('category', 'pack_unit', 'uom').all()
    categories = ProductCategory.objects.all()
    uoms = UnitOfMeasure.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name')
        sku = request.POST.get('sku')
        cat_id = request.POST.get('category')
        pack_size = Decimal(request.POST.get('pack_size', '200'))
        pack_unit_id = request.POST.get('pack_unit')
        price = Decimal(request.POST.get('selling_price', '50'))
        hsn = request.POST.get('hsn_code', '19059040')
        gst_rate = Decimal(request.POST.get('gst_rate', '5'))
        uom_id = request.POST.get('uom')
        carton_cap = int(request.POST.get('pieces_per_carton', '20'))

        Product.objects.create(
            name=name,
            sku=sku,
            category_id=cat_id,
            pack_size=pack_size,
            pack_unit_id=pack_unit_id,
            selling_price=price,
            hsn_code=hsn,
            gst_rate=gst_rate,
            uom_id=uom_id,
            pieces_per_carton=carton_cap
        )
        messages.success(request, f"Product '{name}' created successfully.")
        return redirect('master_data:product_list')

    return render(request, 'master_data/product_list.html', {
        'products': products,
        'categories': categories,
        'uoms': uoms
    })


@login_required
@admin_only
def customer_list(request):
    customers = Customer.objects.select_related('assigned_salesman').all()
    from apps.core.models import User, UserRole
    salesmen = User.objects.filter(role=UserRole.SALESMAN)

    if request.method == 'POST':
        name = request.POST.get('name')
        c_type = request.POST.get('customer_type', CustomerType.RETAILER)
        gstin = request.POST.get('gstin', '')
        state = request.POST.get('state', 'Tamil Nadu')
        billing_address = request.POST.get('billing_address')
        salesman_id = request.POST.get('assigned_salesman') or None
        phone = request.POST.get('phone')
        email = request.POST.get('email', '')

        Customer.objects.create(
            name=name,
            customer_type=c_type,
            gstin=gstin,
            state=state,
            billing_address=billing_address,
            shipping_address=billing_address,
            assigned_salesman_id=salesman_id,
            phone=phone,
            email=email
        )
        messages.success(request, f"Customer '{name}' added successfully.")
        return redirect('master_data:customer_list')

    return render(request, 'master_data/customer_list.html', {
        'customers': customers,
        'salesmen': salesmen,
        'customer_types': CustomerType.choices
    })


@login_required
@admin_only
def supplier_list(request):
    suppliers = Supplier.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name')
        gstin = request.POST.get('gstin', '')
        state = request.POST.get('state', 'Tamil Nadu')
        address = request.POST.get('address')
        phone = request.POST.get('phone')
        email = request.POST.get('email', '')

        Supplier.objects.create(
            name=name,
            gstin=gstin,
            state=state,
            address=address,
            phone=phone,
            email=email
        )
        messages.success(request, f"Supplier '{name}' registered successfully.")
        return redirect('master_data:supplier_list')

    return render(request, 'master_data/supplier_list.html', {'suppliers': suppliers})


@login_required
@admin_only
def uom_list(request):
    uoms = UnitOfMeasure.objects.all()
    converted_result = None

    if request.method == 'POST' and 'convert' in request.POST:
        try:
            qty = Decimal(request.POST.get('quantity', '1'))
            from_uom = UnitOfMeasure.objects.get(id=request.POST.get('from_uom'))
            to_uom = UnitOfMeasure.objects.get(id=request.POST.get('to_uom'))
            prod_id = request.POST.get('product')
            prod = Product.objects.get(id=prod_id) if prod_id else None

            res = UnitConversionService.convert(qty, from_uom, to_uom, product=prod)
            converted_result = f"{qty} {from_uom.code} = {res} {to_uom.code}"
        except Exception as e:
            messages.error(request, str(e))

    return render(request, 'master_data/uom_list.html', {
        'uoms': uoms,
        'converted_result': converted_result,
        'products': Product.objects.all()
    })
