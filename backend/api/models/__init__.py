"""Django models, one file per model.

Every model is re-exported here so `from api.models import X` keeps working.
A new model must be imported below, or Django will not register it.
"""

from .asset import Asset
from .attendance import Attendance
from .contract import Contract
from .conversation_message import ConversationMessage
from .conversation_session import ConversationSession
from .customer import Customer
from .department import Department
from .invoice import Invoice
from .leave_request import LeaveRequest
from .notification import Notification
from .order import Order
from .order_item import OrderItem
from .payroll_entry import PayrollEntry
from .product import Product
from .report import Report
from .stock_movement import StockMovement
from .supplier import Supplier
from .system_statistic import SystemStatistic
from .system_status import SystemStatus
from .ticket import Ticket
from .ticket_comment import TicketComment
from .user import User
from .workflow import Workflow
from .workflow_log import WorkflowLog

__all__ = [
    'Asset',
    'Attendance',
    'Contract',
    'ConversationMessage',
    'ConversationSession',
    'Customer',
    'Department',
    'Invoice',
    'LeaveRequest',
    'Notification',
    'Order',
    'OrderItem',
    'PayrollEntry',
    'Product',
    'Report',
    'StockMovement',
    'Supplier',
    'SystemStatistic',
    'SystemStatus',
    'Ticket',
    'TicketComment',
    'User',
    'Workflow',
    'WorkflowLog',
]
