"""Tests for api/agent/tools.py."""

from django.test import TestCase

from api.agent import agent_tool


class AgentToolDecoratorTests(TestCase):
    def test_agent_tool_decorator_attaches_name_description_schema(self):
        @agent_tool(name='custom_tool', description='Custom tool description')
        def sample_tool(title: str, count: int = 1):
            return f'{title}:{count}'

        metadata = sample_tool.agent_tool

        self.assertEqual(metadata['name'], 'custom_tool')
        self.assertEqual(metadata['description'], 'Custom tool description')
        self.assertEqual(metadata['schema']['type'], 'object')
        self.assertEqual(metadata['schema']['properties']['title']['type'], 'string')
        self.assertEqual(metadata['schema']['properties']['count']['type'], 'integer')
        self.assertEqual(metadata['schema']['required'], ['title'])
