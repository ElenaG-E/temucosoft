import re
from datetime import date
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

# Importación de modelos
from .models import (
    User, Company, Subscription, Product, Branch, Supplier, Inventory,
    Purchase, PurchaseItem, Sale, SaleItem, Order, OrderItem, CartItem,
    UserRoles, SubscriptionPlans, OrderStatus
)

# Importación del validador de RUT (se asume que existe el archivo validators.py)
from .validators import validate_chilean_rut 

# ==============================================================================
# 2. SERIALIZERS BASE (User, Company, Subscription)
# ==============================================================================

class UserSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'rut', 'role', 'role_display', 'company', 
            'company_name', 'is_active', 'created_at', 'password'
        )
        read_only_fields = ('id', 'created_at', 'company_name', 'role_display')
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}, 
            'company': {'required': False, 'allow_null': True},
            'is_active': {'required': False} # Permite a admin_cliente desactivar/activar
        }

    def validate_rut(self, value):
        """Aplicación del validador de RUT Chileno."""
        try:
            return validate_chilean_rut(value)
        except ValidationError as e:
            raise ValidationError({'rut': str(e)})

    def create(self, validated_data):
        # Lógica para hashear la contraseña al crear el usuario
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def update(self, instance, validated_data):
        # Lógica para hashear la contraseña al actualizar
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'
        read_only_fields = ('created_at',)
    
    def validate_rut(self, value):
        """Validación de RUT para la Compañía (Tenant)."""
        try:
            return validate_chilean_rut(value)
        except ValidationError as e:
            raise ValidationError({'rut': str(e)})


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = '__all__'

    def validate(self, data):
        """Validación de fechas: end_date > start_date."""
        start = data.get('start_date')
        end = data.get('end_date')
        
        # Validación de end_date > start_date
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": "La fecha de fin debe ser posterior a la fecha de inicio."}
            )
        return data

# ==============================================================================
# 3. SERIALIZERS OPERACIONALES (Products, Branches, Suppliers, Inventory)
# ==============================================================================

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = '__all__'
        read_only_fields = ('company',)

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'
        read_only_fields = ('company',)
    
    def validate_rut(self, value):
        """Validación de RUT Chileno para Proveedores."""
        try:
            return validate_chilean_rut(value)
        except ValidationError as e:
            raise ValidationError({'rut': str(e)})

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ('company',)

class InventorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = Inventory
        fields = ('branch', 'branch_name', 'product', 'product_name', 'stock', 'reorder_point')
        
# ==============================================================================
# 4. SERIALIZERS TRANSACCIONALES (Purchase, Sale, Order, Items)
# ==============================================================================

class PurchaseItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = PurchaseItem
        # Se excluye 'purchase' porque se asigna automáticamente en el serializer de Purchase
        fields = ('id', 'product', 'product_name', 'quantity', 'cost_at_purchase')
        extra_kwargs = {
            'cost_at_purchase': {'required': True} # El costo debe ser fijo al momento de la compra
        }

class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Purchase
        fields = (
            'id', 'company', 'supplier', 'supplier_name', 'branch', 'branch_name', 'user', 
            'user_username', 'total', 'purchase_date', 'items'
        )
        read_only_fields = ('company', 'total', 'user_username')
        extra_kwargs = {
            'user': {'required': False},
        }

    def validate_purchase_date(self, value):
        """Validación de fecha: Purchase.date no mayor a hoy."""
        # Comparación solo de fecha, ignorando la hora
        if value.date() > timezone.now().date(): 
            raise serializers.ValidationError("La fecha de compra no puede ser futura.")
        return value
    
    # Se debe implementar la lógica de create/update para manejar los items y actualizar el stock.


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = SaleItem
        fields = ('id', 'product', 'product_name', 'quantity', 'price_at_sale')
        extra_kwargs = {
            'price_at_sale': {'required': True} # Precio de venta debe ser fijo al momento de la venta
        }

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Sale
        fields = ('id', 'company', 'branch', 'branch_name', 'user', 'user_username', 'total', 'payment_method', 'created_at', 'items')
        read_only_fields = ('company', 'total', 'user_username')
        extra_kwargs = {
            'user': {'required': False},
        }

    def validate_created_at(self, value):
        """Validación de fecha: Sale.created_at no puede ser futura."""
        if value > timezone.now(): 
            raise serializers.ValidationError("La fecha de la venta POS no puede ser futura.")
        return value

    # Se debe implementar la lógica de create para manejar los items y actualizar el stock.


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'quantity', 'price_at_order')
        extra_kwargs = {
            'price_at_order': {'required': True}
        }

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True) # Los items se crean en el checkout, no aquí.
    client_username = serializers.CharField(source='client_user.username', read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'company', 'client_user', 'client_username', 'client_name', 'client_email', 'status', 'total', 'created_at', 'items')
        read_only_fields = ('company', 'total', 'created_at', 'status', 'items')
        extra_kwargs = {
            'client_user': {'required': False, 'allow_null': True}
        }


# --- 5. Carrito de Compras (CartItem) ---

class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    # Price y Stock se deben obtener y mostrar aquí, pero son campos read_only
    current_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = CartItem
        fields = ('id', 'user', 'session_key', 'product', 'product_name', 'quantity', 'current_price', 'added_at')
        read_only_fields = ('user', 'session_key', 'added_at', 'current_price')
        
    def validate_quantity(self, value):
        """Validación de cantidad: CartItem.quantity >= 1."""
        if value < 1:
            raise serializers.ValidationError("La cantidad debe ser al menos 1.")
        return value
