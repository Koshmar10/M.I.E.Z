"""Business rules for orders and invoices."""

from ..models import Invoice, Order
from . import BusinessRuleError

# Processing → Shipped → Delivered, or Processing → Cancelled. Delivered and Cancelled are final.
ORDER_STATUS_TRANSITIONS: dict[str, list[str]] = {
    Order.Status.PROCESSING: [Order.Status.SHIPPED, Order.Status.CANCELLED],
    Order.Status.SHIPPED: [Order.Status.DELIVERED],
    Order.Status.DELIVERED: [],
    Order.Status.CANCELLED: [],
}


def change_order_status(order: Order, new_status: str) -> Order:
    if new_status not in Order.Status.values:
        raise BusinessRuleError(f'Invalid status value: {new_status}.')
    if new_status == order.status:
        return order
    if new_status not in ORDER_STATUS_TRANSITIONS.get(order.status, []):
        raise BusinessRuleError(f'Invalid status transition from {order.status} to {new_status}.')

    order.status = new_status
    order.save(update_fields=['status', 'updated_at'])
    return order


def mark_invoice_paid(invoice: Invoice) -> Invoice:
    if invoice.status != Invoice.Status.PAID:
        invoice.status = Invoice.Status.PAID
        invoice.save(update_fields=['status', 'updated_at'])
    return invoice
