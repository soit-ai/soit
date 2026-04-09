from app.modules.agent.runtime.planner import PlanResult


def test_plan_result_exposes_only_tool_calls_payload():
    assert not hasattr(PlanResult, "tool_ref")
    assert not hasattr(PlanResult, "parameters")
