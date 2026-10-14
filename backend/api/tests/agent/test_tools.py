"""Tests for api/agent/tools.py."""

from api.agent import agent_tool


def test_agent_tool_decorator_attaches_name_description_schema():
    @agent_tool(name='custom_tool', description='Custom tool description')
    def sample_tool(title: str, count: int = 1):
        return f'{title}:{count}'

    metadata = sample_tool.agent_tool

    assert metadata['name'] == 'custom_tool'
    assert metadata['description'] == 'Custom tool description'
    assert metadata['schema']['type'] == 'object'
    assert metadata['schema']['properties']['title']['type'] == 'string'
    assert metadata['schema']['properties']['count']['type'] == 'integer'
    assert metadata['schema']['required'] == ['title']
