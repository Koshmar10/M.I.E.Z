"""Business rules shared by the API views, the AI assistant's tools and workflows.

Any code that changes the state of a business object (an order's status, a
ticket's status, a leave decision, …) must go through these functions, so every
entry point enforces the same rules.
"""


class BusinessRuleError(ValueError):
    """The requested action breaks a business rule. Views turn it into HTTP 400."""
