"""Business rules for IT tickets."""

from ..models import Ticket, User
from . import BusinessRuleError

# Open → In progress → Resolved. Resolved and Closed are final.
TICKET_STATUS_TRANSITIONS: dict[str, list[str]] = {
    Ticket.Status.OPEN: [Ticket.Status.IN_PROGRESS],
    Ticket.Status.IN_PROGRESS: [Ticket.Status.RESOLVED],
    Ticket.Status.RESOLVED: [],
    Ticket.Status.CLOSED: [],
}


def check_ticket_transition(current_status: str, new_status: str) -> None:
    if new_status not in Ticket.Status.values:
        raise BusinessRuleError(f'Invalid status value: {new_status}.')
    if new_status != current_status and new_status not in TICKET_STATUS_TRANSITIONS.get(current_status, []):
        raise BusinessRuleError(f'Invalid transition from {current_status} to {new_status}.')


def change_ticket_status(
    ticket: Ticket,
    new_status: str,
    *,
    actor: User | None,
    assigned_to: User | None = None,
) -> Ticket:
    """Change a ticket's status, optionally reassigning it.

    Starting work on a ticket (IN_PROGRESS) without naming an assignee assigns it
    to the person who started it. Resolving stamps `resolved_at` (see Ticket.save).
    """
    check_ticket_transition(ticket.status, new_status)

    ticket.status = new_status
    if assigned_to is not None:
        ticket.assigned_to = assigned_to
    elif new_status == Ticket.Status.IN_PROGRESS and actor is not None:
        ticket.assigned_to = actor
    ticket.save()
    return ticket
