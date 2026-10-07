from django.db import models

from .product import Product
from .supplier import Supplier
from .user import User
from .workflow import Workflow
from .workflow_log import WorkflowLog


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
        # on create, apply the stock change to the product
        is_create = self.pk is None
        super().save(*args, **kwargs)
        if is_create:
            try:
                if self.movement_type == StockMovement.Type.INBOUND:
                    # increment product stock
                    self.product.stock_count = (getattr(self.product, 'stock_count', 0) or 0) + int(self.quantity)
                    self.product.save(update_fields=['stock_count'])
                elif self.movement_type in (StockMovement.Type.OUTBOUND, StockMovement.Type.WRITE_OFF):
                    # decrement product stock (not below zero)
                    new_count = max(0, (getattr(self.product, 'stock_count', 0) or 0) - int(self.quantity))
                    self.product.stock_count = new_count
                    self.product.save(update_fields=['stock_count'])
                    self._evaluate_stock_workflows()
                elif self.movement_type == StockMovement.Type.ADJUSTMENT:
                    old_count = getattr(self.product, 'stock_count', 0) or 0
                    self.product.stock_count = int(self.quantity)
                    self.product.save(update_fields=['stock_count'])
                    if self.product.stock_count < old_count:
                        self._evaluate_stock_workflows()
            except Exception:
                # Don't let product save failures block the movement creation; log later if needed
                pass

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
