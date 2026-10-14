"""Business rules for HR: leave requests."""

from ..models import LeaveRequest, User
from . import BusinessRuleError


def decide_leave_request(leave_request: LeaveRequest, *, approve: bool, actor: User) -> LeaveRequest:
    """Approve or reject a leave request. Only pending requests can be decided."""
    if leave_request.status != LeaveRequest.Status.PENDING:
        raise BusinessRuleError(
            f'Leave request {leave_request.id} is not pending (current status: {leave_request.status}).'
        )

    leave_request.status = LeaveRequest.Status.APPROVED if approve else LeaveRequest.Status.REJECTED
    leave_request.approved_by = actor
    leave_request.save(update_fields=['status', 'approved_by', 'updated_at'])
    return leave_request
