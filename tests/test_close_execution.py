from copy import deepcopy
from pathlib import Path

import pytest

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.close_execution import apply_close_step, public_status
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner
from faraday_industrial_benchmark.scenarios import build_scenario
from faraday_industrial_benchmark.world import IndustrialWorld, ToolClient

TASKS = load_tasks(Path(__file__).parents[1] / "data/close-execution/tasks.json")


def test_new_actions_are_exposed_only_for_execution_tier():
    old = load_tasks(Path(__file__).parents[1] / "data/close-chain-v2/tasks.json")[0]
    for task, expected in ((TASKS[0], True), (old, False)):
        client = ToolClient(IndustrialWorld(task))
        for spec in client.tools:
            if spec["name"] in {"request_approval", "execute_action"}:
                assert (
                    "post_close_stage" in spec["input_schema"]["properties"]["action"]["enum"]
                ) == expected


def payload(state, stage):
    return {
        "stage_id": stage,
        "idempotency_key": stage,
        "journal_lines": deepcopy(state["expected"][stage]),
    }


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_reference_recovers_ack_loss_and_replays(task):
    runner = BenchmarkRunner()
    episode = runner.run_task(task, OracleAgent())
    assert episode.score.strict_success, episode.score
    assert runner.replay(task, episode.to_dict()["trace"])["exact_match"]
    trace = episode.to_dict()["trace"]
    assert sum(r["result"].get("error") == "acknowledgement_lost" for r in trace) == 1


def test_prerequisite_failure_is_atomic_and_public_status_hides_answers():
    state = build_scenario(TASKS[0]).state["close_execution"]
    receiver = state["stages"][1]["stage_id"]
    before = deepcopy(state)
    assert apply_close_step(state, "post_close_stage", payload(state, receiver)) == (
        False,
        "posting_prerequisites_incomplete",
    )
    assert state == before
    visible = public_status(state)
    assert "expected" not in visible and "hold_answer" not in visible
    assert visible["receiver_exception"] is None


def test_retry_is_idempotent_but_changed_key_or_values_cannot_repost():
    state = build_scenario(TASKS[0]).state["close_execution"]
    sender = state["stages"][0]["stage_id"]
    original = payload(state, sender)
    assert apply_close_step(state, "post_close_stage", original)[0]
    before = deepcopy(state)
    assert apply_close_step(state, "post_close_stage", original)[0]
    assert state == before
    changed = {**original, "idempotency_key": "new"}
    assert not apply_close_step(state, "post_close_stage", changed)[0]
    changed = deepcopy(original)
    changed["journal_lines"][0]["signed_debit_cents"] += 1
    assert not apply_close_step(state, "post_close_stage", changed)[0]
    assert state == before


def test_full_receipt_assumption_cannot_release_partial_receipt_hold():
    state = build_scenario(TASKS[0]).state["close_execution"]
    receiver = state["hold_stage"]
    sender = receiver.replace(":receiver", ":sender")
    assert apply_close_step(state, "post_close_stage", payload(state, sender))[0]
    assert public_status(state)["receiver_exception"]["status"] == "blocked"
    assert not apply_close_step(state, "post_close_stage", payload(state, receiver))[0]
    wrong = deepcopy(state["hold_answer"])
    wrong["received_quantity"] += wrong["in_transit_quantity"]
    wrong["in_transit_quantity"] = 0
    assert not apply_close_step(state, "release_close_hold", wrong)[0]
    assert apply_close_step(state, "release_close_hold", state["hold_answer"])[0]
    assert apply_close_step(state, "post_close_stage", payload(state, receiver))[0]
    assert not apply_close_step(state, "reconcile_close_ledger", {"posting_receipts": []})[0]


def test_skipping_execution_cannot_publish_correct_artifacts():
    class SkipClose:
        name = "skip-close"

        def run(self, task, tools):
            class Proxy:
                def call(self, name, **arguments):
                    result = tools.call(name, **arguments)
                    if name == "get_incident":
                        result = deepcopy(result)
                        result["incident"].pop("close_execution", None)
                    return result

            return OracleAgent().run(task, Proxy())

    episode = BenchmarkRunner().run_task(TASKS[0], SkipClose())
    assert not episode.score.strict_success
    assert not next(c for c in episode.score.criteria if c.id == "publication-execution").passed


def test_ack_loss_commits_once_and_fresh_approval_retry_is_safe():
    world = IndustrialWorld(TASKS[0])
    close = world.state["close_execution"]
    stage = close["ack_loss_stage"]
    posting = payload(close, stage)

    def execute(body):
        approved = world.call_tool(
            "request_approval",
            {
                "action": "post_close_stage",
                "target": world.state["incident"]["id"],
                "reason": "Post reconciled sender journal.",
                "payload": body,
            },
        )["approval"]
        return world.call_tool(
            "execute_action",
            {
                "action": "post_close_stage",
                "target": world.state["incident"]["id"],
                "approval_id": approved["id"],
            },
        )

    result = execute(posting)
    assert result["error"] == "acknowledgement_lost"
    assert len(close["postings"]) == 1
    live = world.call_tool("get_incident", {})["incident"]["close_execution"]
    assert live["postings"][stage]["idempotency_key"] == stage
    before = deepcopy(close["postings"])
    assert execute(posting)["ok"]
    assert close["postings"] == before
    assert (
        execute({**posting, "idempotency_key": "accidental-new-key"})["error"]
        == "stage_already_posted_use_original_key"
    )
    assert close["postings"] == before


def test_incorrect_journal_rejection_does_not_consume_idempotency_key():
    state = build_scenario(TASKS[0]).state["close_execution"]
    stage = state["stages"][0]["stage_id"]
    correct = payload(state, stage)
    wrong = deepcopy(correct)
    # Keep the journal balanced while corrupting its economic values.
    wrong["journal_lines"][0]["signed_debit_cents"] += 10
    wrong["journal_lines"][1]["signed_debit_cents"] -= 10
    before = deepcopy(state)
    assert apply_close_step(state, "post_close_stage", wrong) == (
        False,
        "journal_business_values_incorrect",
    )
    assert state == before
    assert apply_close_step(state, "post_close_stage", correct)[0]


def test_completed_postings_require_actual_receipts_before_reconciliation():
    state = build_scenario(TASKS[0]).state["close_execution"]
    for stage in state["stages"]:
        if stage["stage_id"] == state["hold_stage"]:
            assert apply_close_step(state, "release_close_hold", state["hold_answer"])[0]
        assert apply_close_step(state, "post_close_stage", payload(state, stage["stage_id"]))[0]
    receipts = sorted(r["receipt_id"] for r in state["postings"].values())
    for wrong in (receipts[:-1], receipts + [receipts[0]], ["invented"] * len(receipts)):
        before = deepcopy(state)
        assert not apply_close_step(state, "reconcile_close_ledger", {"posting_receipts": wrong})[0]
        assert state == before
    assert apply_close_step(state, "reconcile_close_ledger", {"posting_receipts": receipts})[0]


def test_publication_approval_cannot_be_obtained_before_close():
    world = IndustrialWorld(TASKS[0])
    _, missing = world._approval_evidence("publish_operating_review")
    assert f"executed_action:reconcile_close_ledger@{world.state['incident']['id']}" in missing
