"""Imports every module's models so Base.metadata is complete (Alembic, tests)."""

from app.admin.models import Banner  # noqa: F401
from app.audit.models import AuditLog  # noqa: F401
from app.auth.models import UserSession, UserToken  # noqa: F401
from app.cart.models import Cart, CartItem  # noqa: F401
from app.catalog.models import (  # noqa: F401
    Attribute,
    AttributeValue,
    Category,
    Collection,
    Product,
    ProductMedia,
    ProductVariant,
    Tag,
    VariantAttributeValue,
)
from app.core.database import Base  # noqa: F401
from app.coupons.models import Coupon, CouponUsage, coupon_categories, coupon_products  # noqa: F401
from app.inventory.models import Inventory, InventoryReservation, InventoryTransaction  # noqa: F401
from app.notifications.models import Notification, NotificationTemplate  # noqa: F401
from app.orders.models import Order, OrderItem, OrderReturn, OrderStatusHistory  # noqa: F401
from app.payments.models import Payment, Refund, WebhookEvent  # noqa: F401
from app.reviews.models import Review, ReviewMedia  # noqa: F401
from app.shipping.models import Shipment, ShipmentTrackingEvent  # noqa: F401
from app.users.models import Address, Role, User, user_roles  # noqa: F401
from app.wishlist.models import WishlistItem  # noqa: F401
