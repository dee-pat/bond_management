"""Pin the concurrency contract and exercise its event-context matrix."""

import re
import unittest
from pathlib import Path


class WorkflowConcurrencyTests(unittest.TestCase):
    def test_pr_supersession_and_independent_non_pr_runs(self):
        workflow_groups = []
        for workflow, name in (("ci.yml", "CI"), ("linter.yml", "Linters")):
            source = (Path(__file__).resolve().parent.parent / ".github/workflows" / workflow).read_text()
            group = re.search(r"^  group: (.+)$", source, re.MULTILINE).group(1)
            self.assertIn("  cancel-in-progress: true", source)
            contexts = (
                ("pull_request", "refs/pull/42/merge", 42, 100),
                ("pull_request", "refs/pull/42/merge", 42, 101),
                ("pull_request", "refs/pull/43/merge", 43, 102),
                ("push", "refs/heads/main", None, 103),
                ("push", "refs/heads/main", None, 104),
                ("push", "refs/heads/version-16", None, 105),
                ("push", "refs/heads/version-16", None, 106),
                ("workflow_dispatch", "refs/heads/main", None, 107),
                ("workflow_dispatch", "refs/heads/main", None, 108),
                ("workflow_dispatch", "refs/heads/version-16", None, 109),
                ("workflow_dispatch", "refs/heads/version-16", None, 110),
            )
            groups = [
                concurrency_group(
                    group,
                    {
                        "github": {
                            "workflow": name,
                            "event_name": event,
                            "ref": ref,
                            "run_id": run_id,
                            "event": {"number": number, "pull_request": {"number": number}} if number else {},
                        }
                    },
                )
                for event, ref, number, run_id in contexts
            ]
            self.assertEqual(groups[0], groups[1])
            self.assertEqual(len(set(groups)), len(groups) - 1, workflow)
            workflow_groups.append(set(groups))
        self.assertTrue(workflow_groups[0].isdisjoint(workflow_groups[1]))


def concurrency_group(template, context):
    """Evaluate only context lookups and OR; missing event properties are empty.

    Fail on other syntax rather than pretend to implement the Actions engine.
    """

    def expression(match):
        for operand in match[1].split("||"):
            operand = operand.strip()
            if not re.fullmatch(r"github\.[A-Za-z_.]+", operand):
                raise AssertionError(f"Unsupported concurrency expression: {operand}")
            value = context
            for key in operand.split("."):
                value = value.get(key, "") if isinstance(value, dict) else ""
            if value:
                return str(value)
        return ""

    return re.sub(r"\$\{\{(.*?)\}\}", expression, template)


if __name__ == "__main__":
    unittest.main()
