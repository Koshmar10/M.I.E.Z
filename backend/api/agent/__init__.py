"""
MIEZ Agent module.

Provides the core agent infrastructure for the MIEZ Assistant, including:
- AgentRunner: Main orchestrator for agent interactions
- Tool system: Registry and management of agent tools
- Tool framework: Base classes for creating custom tools
"""

from .runner import AgentRunner
from .tools import (
    agent_tool,
    Tool,
    ToolRegistry,
    get_registry,
    register_tool,
    get_tool,
)
from .operations import (
    create_leave_request,
    create_ticket,
    generate_report,
    get_dashboard_summary,
    query_employees,
    query_inventory,
    query_orders,
    query_tickets,
    register_default_tools,
)

register_default_tools()

__all__ = [
    'AgentRunner',
    'agent_tool',
    'Tool',
    'ToolRegistry',
    'get_registry',
    'register_tool',
    'get_tool',
    'get_dashboard_summary',
    'query_orders',
    'query_tickets',
    'query_employees',
    'query_inventory',
    'create_ticket',
    'create_leave_request',
    'generate_report',
]
