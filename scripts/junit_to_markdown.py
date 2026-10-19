"""Render a pytest JUnit XML report as a markdown table (CI step summary + artifact).
Run:  python -m scripts.junit_to_markdown junit.xml > eval_results.md
"""
import sys
import xml.etree.ElementTree as ET


def main(path: str) -> None:
    root = ET.parse(path).getroot()
    rows, counts = [], {"passed": 0, "failed": 0, "skipped": 0}
    for tc in root.iter("testcase"):
        if tc.find("failure") is not None or tc.find("error") is not None:
            status = "failed"
        elif tc.find("skipped") is not None:
            status = "skipped"
        else:
            status = "passed"
        counts[status] += 1
        icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}[status]
        rows.append(f"| {icon} | `{tc.get('classname', '').split('.')[-1]}` | `{tc.get('name')}` | {float(tc.get('time', 0)):.2f}s |")
    print(f"### RefundRx test & eval results\n\n**{counts['passed']} passed · {counts['failed']} failed · "
          f"{counts['skipped']} skipped**\n")
    print("| | Module | Test | Time |\n|---|---|---|---|")
    print("\n".join(rows))


if __name__ == "__main__":
    main(sys.argv[1])
