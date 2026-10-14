"""Tests for api/agent/runner.py."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from model_bakery import baker

from api.agent import AgentRunner, Tool, get_registry
from api.models import Department, Report, User


@pytest.fixture
def claude():
    """The mocked Anthropic client the runner talks to."""
    with patch('api.agent.runner.Anthropic') as anthropic:
        yield anthropic.return_value


@pytest.fixture
def hr_manager():
    return baker.make(User, role=User.Role.HR, position='HR Manager')


def _text(text):
    return SimpleNamespace(type='text', text=text)


def _tool_use(tool_use_id, name, input_data):
    return SimpleNamespace(type='tool_use', id=tool_use_id, name=name, input=input_data)


def _response(stop_reason, content):
    return SimpleNamespace(stop_reason=stop_reason, content=content)


# ── Agent loop ───────────────────────────────────────────────────────────────


def test_run_end_turn_returns_text_immediately(claude, ceo_user):
    claude.messages.create.return_value = _response('end_turn', [_text('final answer')])

    result = AgentRunner(ceo_user).run('hello')

    assert result['response'] == 'final answer'
    assert result['tool_calls_made'] == []
    claude.messages.create.assert_called_once()


def test_run_tool_use_response_triggers_tool_execution_and_loops(claude, ceo_user):
    calls = []

    def summarize(module: str, user: User):
        calls.append((module, user.username))
        return {'module': module, 'role': user.role}

    claude.messages.create.side_effect = [
        _response('tool_use', [_tool_use('tool-1', 'get_dashboard_summary', {'module': 'sales'})]),
        _response('end_turn', [_text('sales summary ready')]),
    ]

    result = AgentRunner(ceo_user, tools=[Tool.from_callable(summarize, name='get_dashboard_summary')]).run(
        'summarize sales'
    )

    assert result['response'] == 'sales summary ready'
    assert calls == [('sales', ceo_user.username)]
    [tool_call] = result['tool_calls_made']
    assert tool_call['tool_name'] == 'get_dashboard_summary'
    assert tool_call['error'] is None
    assert 'module' in tool_call['result']
    assert claude.messages.create.call_count == 2
    tool_result = claude.messages.create.call_args_list[1].kwargs['messages'][-1]
    assert tool_result['role'] == 'user'
    assert tool_result['content'][0]['type'] == 'tool_result'
    assert not tool_result['content'][0]['is_error']


def test_run_multiple_sequential_tool_calls_resolved_correctly(claude, ceo_user):
    execution_order = []

    def first_tool(user: User, value: str):
        execution_order.append(('first', value))
        return f'first:{value}'

    def second_tool(user: User, value: str):
        execution_order.append(('second', value))
        return f'second:{value}'

    claude.messages.create.side_effect = [
        _response('tool_use', [_tool_use('tool-1', 'first_tool', {'value': 'one'})]),
        _response('tool_use', [_tool_use('tool-2', 'second_tool', {'value': 'two'})]),
        _response('end_turn', [_text('all done')]),
    ]
    runner = AgentRunner(
        ceo_user,
        tools=[Tool.from_callable(first_tool, name='first_tool'), Tool.from_callable(second_tool, name='second_tool')],
    )

    result = runner.run('do the sequence')

    assert result['response'] == 'all done'
    assert execution_order == [('first', 'one'), ('second', 'two')]
    assert [item['tool_name'] for item in result['tool_calls_made']] == ['first_tool', 'second_tool']
    assert claude.messages.create.call_count == 3


def test_run_max_iterations_reached_returns_fallback_message(claude, ceo_user):
    runner = AgentRunner(ceo_user, tools=[Tool.from_callable(lambda value: value, name='loop_tool')])
    runner.MAX_ITERATIONS = 2
    claude.messages.create.side_effect = [
        _response('tool_use', [_tool_use('tool-1', 'loop_tool', {'value': 'first'})]),
        _response('tool_use', [_tool_use('tool-2', 'loop_tool', {'value': 'second'})]),
    ]

    result = runner.run('keep going')

    assert 'could not complete' in result['response']
    assert len(result['tool_calls_made']) == 2
    assert claude.messages.create.call_count == 2


def test_run_tool_raises_exception_error_captured_in_tool_result(claude, ceo_user):
    def explode(user: User, value: str):
        raise RuntimeError('boom')

    claude.messages.create.side_effect = [
        _response('tool_use', [_tool_use('tool-1', 'explode_tool', {'value': 'x'})]),
        _response('end_turn', [_text('handled')]),
    ]

    result = AgentRunner(ceo_user, tools=[Tool.from_callable(explode, name='explode_tool')]).run('break it')

    assert result['response'] == 'handled'
    assert [call['error'] for call in result['tool_calls_made']] == ['boom']
    tool_result = claude.messages.create.call_args_list[1].kwargs['messages'][-1]['content'][0]
    assert tool_result['is_error']
    assert 'boom' in tool_result['content']


# ── System prompt and tool selection ─────────────────────────────────────────


def test_get_system_prompt_includes_report_catalog_for_manager(hr_manager):
    baker.make(Report, name='HR Headcount', slug='hr-headcount-runner', category='HR')

    prompt = AgentRunner(hr_manager).get_system_prompt()

    assert 'Available report slugs:' in prompt
    assert 'hr-headcount-runner (HR Headcount)' in prompt


def test_get_system_prompt_includes_user_full_name():
    user = baker.make(User, role=User.Role.HR, first_name='Ana', last_name='Mihai')
    assert 'Ana Mihai' in AgentRunner(user).get_system_prompt()


def test_get_system_prompt_falls_back_to_username_when_no_name():
    user = baker.make(User, role=User.Role.CEO, username='ceo-loop', first_name='', last_name='')
    assert 'ceo-loop' in AgentRunner(user).get_system_prompt()


def test_get_system_prompt_includes_current_page(ceo_user):
    assert '/sales/orders' in AgentRunner(ceo_user, current_page='/sales/orders').get_system_prompt()


def test_get_system_prompt_omits_page_line_when_not_provided(ceo_user):
    assert 'Current page:' not in AgentRunner(ceo_user).get_system_prompt()


def test_get_system_prompt_includes_position_when_set(hr_manager):
    assert 'HR Manager' in AgentRunner(hr_manager).get_system_prompt()


def test_get_system_prompt_includes_department_when_set():
    user = baker.make(User, role=User.Role.HR, department=baker.make(Department, name='Human Resources'))
    assert 'Human Resources' in AgentRunner(user).get_system_prompt()


def test_get_tools_for_user_includes_generate_report_for_manager(hr_manager):
    runner = AgentRunner(hr_manager, tools=get_registry().get_all())
    assert 'generate_report' in [tool.name for tool in runner.get_tools_for_user()]
