"""Mutate saved OOXML in disposable files to test the native verifier."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from faraday_industrial_benchmark.models import load_tasks
from faraday_industrial_benchmark.native_review import NS, verify_native


def main():
    source = Path("outputs/01a0a219-professional")
    task = load_tasks("data/professional/tasks.json")[-1]
    report = source / "executive-report.html"
    workbook = source / "operating-review.xlsx"
    positive = verify_native(task, workbook, report)
    assert positive["strict_success"]
    with ZipFile(workbook) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    checks = []
    mutations = [
        ("hardcoded_reserve", "B15", "remove_formula"),
        ("stale_reserve_cache", "B15", "wrong_value"),
        ("wrong_disposal", "B6", "wrong_value"),
        ("wrong_cash", "B17", "wrong_value"),
        ("constant_formula", "B15", "constant_formula"),
        ("cash_netted_into_reserve", "B15", "net_cash"),
    ]
    with TemporaryDirectory(prefix="faraday-native-verifier-") as directory:
        for name, address, operation in mutations:
            changed = dict(members)
            root = ET.fromstring(changed["xl/worksheets/sheet1.xml"])
            cell = root.find(f".//s:c[@r='{address}']", NS)
            assert cell is not None
            if operation == "remove_formula":
                cell.remove(cell.find("s:f", NS))
            elif operation == "wrong_value":
                cell.find("s:v", NS).text = "1"
            elif operation == "constant_formula":
                cell.find("s:f", NS).text = cell.find("s:v", NS).text
            else:
                cell.find("s:f", NS).text = "SUM(B6:B13)-B17"
            changed["xl/worksheets/sheet1.xml"] = ET.tostring(root)
            target = Path(directory) / f"{name}.xlsx"
            with ZipFile(target, "w") as archive:
                for key, value in changed.items():
                    archive.writestr(key, value)
            result = verify_native(task, target, report)
            assert not result["strict_success"], name
            checks.append(
                {
                    "mutation": name,
                    "rejected": True,
                    "failed_checks": [c["id"] for c in result["checks"] if not c["passed"]],
                }
            )
        bad_report = Path(directory) / "wrong-report.html"
        bad_report.write_text("<h1>Operating review</h1><h2>Reserve: USD 0.00</h2>")
        result = verify_native(task, workbook, bad_report)
        assert not result["strict_success"]
        checks.append(
            {
                "mutation": "wrong_executive_report",
                "rejected": True,
                "failed_checks": [c["id"] for c in result["checks"] if not c["passed"]],
            }
        )
    result = {
        "kind": "native_file_qualification_not_model_result",
        "task": task.id,
        "positive_checks": len(positive["checks"]),
        "corruptions_rejected": len(checks),
        "results": checks,
    }
    Path("reports/native-review-qualification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}))


if __name__ == "__main__":
    main()
