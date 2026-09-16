"""Deliberately incorrect deliverables used to qualify professional graders."""

from copy import deepcopy

from .agents import OracleAgent


class ProfessionalNegativeControl:
    name = "professional-negative-control"

    def __init__(self, mistake):
        self.mistake = mistake
        self.mutations = 0

    def run(self, task, tools):
        owner = self

        class Proxy:
            def call(self, name, **arguments):
                arguments = deepcopy(arguments)
                if name == "create_structured_artifact":
                    content = arguments["content"]
                    kind = arguments["artifact_type"]
                    if kind == "integrated_recovery_model":
                        impact = content["financial_impact"]
                        claims = impact["insurance_bridge"]
                        finance = impact.get("finance_bridge")
                        if owner.mistake == "omit_claims_bridge":
                            impact.pop("insurance_bridge")
                        elif owner.mistake == "double_count_prior_receipt":
                            impact["reserve_amount"] -= claims["already_received_cents"] / 100
                        elif owner.mistake == "omit_exclusion_evidence":
                            claims["exclusions"] = []
                        elif owner.mistake == "cash_reduces_expense" and finance:
                            impact["reserve_amount"] -= finance["settled_cash_cents"] / 100
                        elif owner.mistake == "ignore_credit_notes" and finance:
                            credit = sum(
                                -r["recognized_cents"]
                                for r in finance["ledger"]
                                if r["recognized_cents"] < 0
                            )
                            impact["reserve_amount"] += credit / 100
                        elif owner.mistake == "wrong_cash_cutoff" and finance:
                            finance["settled_cash_cents"] += 1
                        else:
                            return tools.call(name, **arguments)
                        owner.mutations += 1
                    elif (
                        kind == "executive_decision_brief" and owner.mistake == "inconsistent_brief"
                    ):
                        content["reserve_amount"] += 1
                        owner.mutations += 1
                return tools.call(name, **arguments)

        return OracleAgent().run(task, Proxy())
