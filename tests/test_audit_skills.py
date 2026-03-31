from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = REPO_ROOT / "skill" / "skill-auditor" / "scripts" / "audit_skills.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures"


class AuditSkillsTests(unittest.TestCase):
    def run_audit(self, fixture_name: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(AUDIT_SCRIPT),
                "--root",
                str(FIXTURES / fixture_name),
                "--format",
                "json",
                *extra_args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_clean_fixture_has_no_findings(self) -> None:
        result = self.run_audit("clean-skill")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["total_findings"], 0)

    def test_poisoned_fixture_detects_marketing_and_directive_signals(self) -> None:
        result = self.run_audit("poisoned-repo", "--fail-on", "medium")
        self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(payload["summary"]["total_findings"], 3)
        categories = {item["category"] for item in payload["findings"]}
        self.assertIn("marketing_cta", categories)
        self.assertIn("directive", categories)
        self.assertIn("suspicious_skill_name", categories)

    def test_ignores_own_internal_detection_files_when_auditing_skill_auditor(self) -> None:
        result = self.run_audit("self-rules")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["total_findings"], 0)


if __name__ == "__main__":
    unittest.main()
