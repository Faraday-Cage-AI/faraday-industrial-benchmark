import json

from jsonschema import validate

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.cli import DEFAULT_TASKS
from faraday_industrial_benchmark.models import PUBLIC_NOTIFICATION_ROLES, load_tasks
from faraday_industrial_benchmark.platform_harness import (
    build_platform_harness_contract,
    save_platform_harness_contract,
)
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.scenarios import build_scenario
from faraday_industrial_benchmark.tool_specs import (
    PROTECTED_ACTIONS,
    TOOL_SPECS,
    tool_specs_for_family,
)


def test_protected_action_contract_is_public_and_consistent():
    for name in ("request_approval", "execute_action"):
        tool = next(spec for spec in TOOL_SPECS if spec["name"] == name)
        action = tool["input_schema"]["properties"]["action"]
        assert action["enum"] == list(PROTECTED_ACTIONS)
        assert "capitalize_asset(target=asset_id" in action["description"]
        assert "publish_engineering_review(target=review_id" in action["description"]


def test_exact_plan_vocabulary_is_published_on_every_applicable_task():
    for task in load_tasks(DEFAULT_TASKS):
        criteria = [
            criterion
            for criterion in build_scenario(task).criteria
            if criterion.get("check") == "proposal_actions"
        ]
        expected = tuple(criteria[0]["actions"]) if criteria else ()
        assert task.controlled_plan_actions == expected


def test_notification_role_vocabulary_is_public_and_matches_the_grader():
    for task in load_tasks(DEFAULT_TASKS):
        roles = []
        for criterion in build_scenario(task).criteria:
            if criterion.get("check") == "notification_roles":
                roles.extend(criterion["roles"])
        assert tuple(roles) == PUBLIC_NOTIFICATION_ROLES[task.family]
        assert task.public_dict()["required_notification_roles"] == roles


def test_every_reference_workflow_is_solvable_through_its_public_tool_scope():
    runner = BenchmarkRunner()
    oracle = OracleAgent()
    for task in load_tasks(DEFAULT_TASKS):
        available = {spec["name"] for spec in tool_specs_for_family(task.family)}
        used = {call.tool for call in runner.run_task(task, oracle).trace}
        assert used <= available, f"{task.family} hides required tools: {used - available}"


def test_platform_contract_is_complete_but_seed_and_grader_free(tmp_path):
    tasks = load_tasks(DEFAULT_TASKS)
    contract = build_platform_harness_contract(tasks)
    serialized = json.dumps(contract, sort_keys=True)

    assert contract["schema_version"] == "faraday-platform-harness/1"
    assert contract["suite"]["task_count"] == 66
    assert contract["suite"]["family_count"] == 32
    assert contract["suite"]["tool_count"] == 67
    assert len(contract["cases"]) == 66
    assert len(contract["suite"]["public_contract_sha256"]) == 64
    assert len(contract["suite"]["public_tool_contract_sha256"]) == 64
    assert '"seed"' not in serialized
    assert '"criteria"' not in serialized
    assert "unmitigated_cost" not in serialized
    assert "engineering_review_truth" not in serialized

    output = save_platform_harness_contract(contract, tmp_path / "harness.json")
    assert json.loads(output.read_text(encoding="utf-8")) == contract

    schema = json.loads(
        (DEFAULT_TASKS.parents[1] / "schemas" / "platform-harness.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validate(contract, schema)


def test_platform_contract_digest_is_deterministic_and_selection_sensitive():
    tasks = load_tasks(DEFAULT_TASKS)
    first = build_platform_harness_contract(tasks)
    second = build_platform_harness_contract(tasks)
    partial = build_platform_harness_contract(tasks[:2])

    assert first == second
    assert (
        first["suite"]["public_contract_sha256"]
        != partial["suite"]["public_contract_sha256"]
    )
