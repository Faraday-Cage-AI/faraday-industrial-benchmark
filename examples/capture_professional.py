"""Capture reference-submitted artifacts, never hidden evaluator state."""

import json
from copy import deepcopy
from pathlib import Path

from faraday_industrial_benchmark.agents import OracleAgent
from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.runner import BenchmarkRunner


class CaptureAgent:
    name = "reference-artifact-capture"

    def __init__(self):
        self.artifacts = {}

    def run(self, task, tools):
        owner = self

        class Proxy:
            def call(self, name, **arguments):
                result = tools.call(name, **arguments)
                if name == "create_structured_artifact" and result.get("ok"):
                    owner.artifacts[arguments["artifact_type"]] = deepcopy(arguments)
                return result

        return OracleAgent().run(task, Proxy())


def main():
    task = load_tasks("data/professional/tasks.json")[-1]
    agent = CaptureAgent()
    episode = BenchmarkRunner().run_task(task, agent)
    assert episode.score.strict_success
    target = Path("runs/native-professional/submission.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"task_id": task.id, "artifacts": agent.artifacts}, indent=2) + "\n")
    target.with_name("episode.json").write_text(json.dumps(episode.to_dict(), indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
