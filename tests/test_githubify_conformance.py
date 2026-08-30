# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Fabio Campolim
"""Vendored githubify conformance checker — wiring test.

``tests/conformance.py`` is a byte-identical vendored copy of the canonical
checker in the owner's private tooling. The private rules file (the scrub
pattern) is intentionally NOT vendored; point the ``GITHUBIFY_RULES``
environment variable at it — or put its path in a gitignored
``.githubify-rules`` file at the repo root — to enable the scrub checks
locally. Without it, structural checks still run and scrub checks skip.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VENDORED = os.path.join(HERE, "conformance.py")


def rules_path():
    p = os.environ.get("GITHUBIFY_RULES")
    if p and os.path.isfile(p):
        return p
    ptr = os.path.join(ROOT, ".githubify-rules")
    if os.path.isfile(ptr):
        with open(ptr, encoding="utf-8") as f:
            p = f.read().strip()
        if p and os.path.isfile(p):
            return p
    return None


class VendoredConformance(unittest.TestCase):
    def test_vendored_is_byte_identical_to_canonical(self):
        rp = rules_path()
        if not rp:
            self.skipTest("private rules file not available on this machine")
        canonical = os.path.join(os.path.dirname(rp), "conformance.py")
        if not os.path.isfile(canonical):
            self.skipTest("canonical checker not found next to the rules file")
        with open(VENDORED, "rb") as a, open(canonical, "rb") as b:
            self.assertEqual(a.read(), b.read(),
                             "vendored copy drifted from the canonical checker "
                             "- re-copy it (single source of truth rule)")

    def test_checker_runs_and_reports(self):
        rp = rules_path()
        with tempfile.TemporaryDirectory() as tmp:
            jout = os.path.join(tmp, "conformance.json")
            cmd = [sys.executable, VENDORED, "--repo", ROOT,
                   "--json", jout, "--quiet"]
            if rp:
                cmd += ["--rules", rp]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=600)
            self.assertIn(proc.returncode, (0, 1), proc.stderr)
            with open(jout, encoding="utf-8") as f:
                payload = json.load(f)
            self.assertIn("counts", payload)
            self.assertTrue(payload["results"], "checker produced no results")


if __name__ == "__main__":
    unittest.main()
