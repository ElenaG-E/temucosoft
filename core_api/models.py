from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.utils import timezone

# ==============================================================================
# 1. CHOICES (Opciones Fijas)
# ==============================================================================

class UserRoles(models.TextChoices):
    # Roles mínimos obligatorios
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Administrador (TemucoSoft)'
    ADMIN_CLIENTE = 'ADMIN_CLIENTE', 'Administrador Cliente (Dueño)'
    GERENTE = 'GERENTE', 'Gerente'
    VENDEDOR = 'VENDEDOR', 'Vendedor (POS)'
    # Opcional, pero recomendado para e-commerce
    CLIENTE_FINAL = 'CLIENTE_FINAL', 'Cliente Final (E-commerce)'

class SubscriptionPlans(models.TextChoices):
    BASICO = 'BASICO', 'Básico'
    ESTANDAR = 'ESTANDAR', 'Estándar'
    PREMIUM = 'PREMIUM', 'Premium'

class OrderStatus(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    ENVIADO = 'ENVIADO', 'Enviado'
    ENTREGADO = 'ENTREGADO', 'Entregado'
    ANULADA = 'ANULADA', 'Anulada' # Añadido para gestión

class PaymentMethods(models.TextChoices):
    EFECTIVO = 'EFECTIVO', 'Efectivo'
    TARJETA = 'TARJETA', 'Tarjeta (Crédito/Débito)'
    TRANSFERENCIA = 'TRANSFERENCIA', 'Transferencia Bancaria'
    OTRO = 'OTRO', 'Otro'

# ==============================================================================
# 2. MODELOS BASE (Tenant, User, Subscription)
# ==============================================================================

class Company(models.Model):
    """Representa al cliente (tenant) de TemucoSoft."""
    name = models.CharField(max_length=100)
    rut = models.CharField(max_length=12, unique=True, help_text="RUT chileno de la empresa")
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name

class User(AbstractUser):
    """Modelo de Usuario Customizado (AUTH_USER_MODEL)."""
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Cliente/Tenant al que pertenece el usuario (NULL para Super Admin)"
    )
    rut = models.CharField(max_length=12, unique=True, help_text="RUT chileno (a validar)")
    role = models.CharField(max_length=20, choices=UserRoles.choices, default=UserRoles.VENDEDOR)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_super_admin(self):
        return self.role == UserRoles.SUPER_ADMIN
    
    def is_admin_cliente(self):
        return self.role == UserRoles.ADMIN_CLIENTE
        
    def is_gerente(self):
        return self.role == UserRoles.GERENTE

class Subscription(models.Model):
    """Modelo para gestionar los planes de suscripción de cada Company."""
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='subscription')
    plan_name = models.CharField(max_length=20, choices=SubscriptionPlans.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.company.name} - {self.get_plan_name_display()}"

# ==============================================================================
# 3. MODELOS OPERACIONALES Y TRANSACCIONALES
# ==============================================================================

class Product(models.Model):
    """Producto de una tienda/tenant."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='products')
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0)],
        help_text="Precio de venta al público (>=0)"
    )
    cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(0)],
        help_text="Costo para la empresa (>=0)"
    )
    category = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True) # Para activar/desactivar en e-commerce

    def __str__(self):
        return f"[{self.company.name}] {self.name}"

class Branch(models.Model):
    """Sucursal o punto de venta de una Company."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"[{self.company.name}] {self.name}"

class Supplier(models.Model):
    """Proveedor de productos."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='suppliers')
    name = models.CharField(max_length=100)
    rut = models.CharField(max_length=12, help_text="RUT chileno del proveedor (a validar)")
    contact = models.CharField(max_length=255)

    def __str__(self):
        return f"[{self.company.name}] {self.name}"

class Inventory(models.Model):
    """Relación Branch x Product (Inventario)."""
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    stock = models.IntegerField(
        validators=[MinValueValidator(0)], 
        help_text="Stock físico (>=0)"
    )
    reorder_point = models.IntegerField(default=5)

    class Meta:
        unique_together = ('branch', 'product')
        verbose_name_plural = "Inventories"
        
    def __str__(self):
        return f"{self.product.name} en {self.branch.name} (Stock: {self.stock})"


# --- 4. Compras (Purchase) ---

class Purchase(models.Model):
    """Orden de Compra / Ingreso de Stock desde Proveedor."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='purchases')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, related_name='purchases')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='purchases')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, help_text="Usuario que registra la compra (Gerente/Admin)")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    purchase_date = models.DateTimeField(default=timezone.now, help_text="Fecha de la compra (no puede ser futura)")

    def __str__(self):
        return f"Compra #{self.id} de {self.supplier.name if self.supplier else 'N/A'}"

class PurchaseItem(models.Model):
    """Detalle de productos en una Purchase."""
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT) # Proteger la eliminación del producto
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    cost_at_purchase = models.DecimalField(max_digits=10, decimal_places=2) # Costo unitario registrado

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

# --- 5. Ventas POS (Sale) ---

class Sale(models.Model):
    """Registro de Venta Presencial (POS)."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sales')
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='sales')
    user = models.ForeignKey(User, on_delete=models.PROTECT, help_text="Vendedor que realizó la venta")
    total = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethods.choices)
    created_at = models.DateTimeField(default=timezone.now, help_text="Fecha de la venta (no puede ser futura)")

    def __str__(self):
        return f"Venta POS #{self.id} en {self.branch.name}"

class SaleItem(models.Model):
    """Detalle de productos en una Sale."""
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2) # Precio unitario registrado

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

# --- 6. Órdenes E-commerce (Order) ---

class Order(models.Model):
    """Orden de Venta Online (E-commerce)."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='orders')
    client_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ecommerce_orders',
        help_text="Cliente final autenticado (Opcional)"
    )
    client_name = models.CharField(max_length=255) # Para clientes no autenticados
    client_email = models.EmailField() # Para clientes no autenticados
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDIENTE)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order E-comm #{self.id} ({self.get_status_display()})"

class OrderItem(models.Model):
    """Detalle de productos en una Order."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2) # Precio unitario registrado

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

# --- 7. Carrito de Compras Temporal (CartItem) ---

class CartItem(models.Model):
    """Ítem en el carrito de compras (E-commerce)."""
    # Identificación del carrito, puede ser por usuario autenticado O por sesión
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True) # Para usuarios no autenticados
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)]) # Validación quantity >= 1
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Asegura unicidad: Un producto solo puede estar una vez en el carrito por usuario/sesión
        unique_together = (('user', 'product'), ('session_key', 'product'))

    def __str__(self):
        user_id = self.user.username if self.user else self.session_key
        return f"Carrito de {user_id}: {self.product.name} ({self.quantity})"
