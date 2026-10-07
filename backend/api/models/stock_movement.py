import logging

from django.db import models, transaction

from .product import Product
from .supplier import Supplier
from .user import User
from .workflow import Workflow
from .workflow_log import WorkflowLog

logger = logging.getLogger(__name__)


class StockMovement(models.Model):
    class Type(models.TextChoices):
        INBOUND = 'INBOUND', 'Inbound'
        OUTBOUND = 'OUTBOUND', 'Outbound'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'
        WRITE_OFF = 'WRITE_OFF', 'Write-off'

    movement_type = models.CharField(max_length=12, choices=Type.choices)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_movements')
    # supplier is optional for adjustments or write-offs where supplier may not apply
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_movements'
    )
    quantity = models.PositiveIntegerField(default=0)
    expected_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='stock_movements_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # A new movement and its effect on the product's stock are saved together, or not at all.
        is_create = self.pk is None
        with transaction.atomic():
            super().save(*args, **kwargs)
            stock_before = self._apply_to_product_stock() if is_create else None

        if stock_before is not None and self._reduced_stock(stock_before):
            try:
                self._evaluate_stock_workflows()
            except Exception:
                # The movement is already saved; a failing workflow must not turn it into an error.
                logger.exception('Stock workflows failed for stock movement %s', self.pk)

    def _apply_to_product_stock(self) -> int:
        """Apply this movement to the product's stock and return the stock before the change.

        The product row is locked until the transaction ends, so two movements saved
        at the same time can't overwrite each other's change.
        """
        product = Product.objects.select_for_update().get(pk=self.product_id)
        stock_before = product.stock_count
        quantity = int(self.quantity)

        if self.movement_type == self.Type.INBOUND:
            product.stock_count = stock_before + quantity
        elif self.movement_type in (self.Type.OUTBOUND, self.Type.WRITE_OFF):
            product.stock_count = max(0, stock_before - quantity)
        elif self.movement_type == self.Type.ADJUSTMENT:
            product.stock_count = quantity

        product.save(update_fields=['stock_count'])
        self.product = product
        return stock_before

    def _reduced_stock(self, stock_before: int) -> bool:
        if self.movement_type in (self.Type.OUTBOUND, self.Type.WRITE_OFF):
            return True
        return self.movement_type == self.Type.ADJUSTMENT and self.product.stock_count < stock_before

    def _evaluate_stock_workflows(self):
        from django.utils import timezone

        workflows = Workflow.objects.filter(trigger_type=Workflow.TriggerType.STOCK_BELOW_MINIMUM, is_active=True)
        for wf in workflows:
            config = wf.trigger_config or {}
            target_product_id = config.get('product_id')
            if target_product_id and str(target_product_id) != str(self.product.id):
                continue

            threshold = config.get('threshold', getattr(self.product, 'min_stock', 10))
            if self.product.stock_count < int(threshold):
                actions_log = []
                for action in wf.actions:
                    act_type = action.get('type', str(action)) if isinstance(action, dict) else str(action)
                    actions_log.append(
                        {
                            'action': act_type,
                            'status': 'success',
                            'message': f'Executed {act_type} for product {self.product.name} (stock {self.product.stock_count} < threshold {threshold})',
                        }
                    )

                WorkflowLog.objects.create(
                    workflow=wf, trigger_type=wf.trigger_type, actions_log=actions_log, success=True
                )
                wf.last_triggered_at = timezone.now()
                wf.save(update_fields=['last_triggered_at'])
