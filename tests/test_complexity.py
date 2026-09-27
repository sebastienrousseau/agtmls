# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""complexity and check-complexity.py: the four ceilings and their ratchet.

The expected numbers are what radon (cyclomatic) and complexipy (cognitive)
report for the same code, checked when this module was written; where the
module deliberately differs (a lambda's body), the test says so.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import ClassVar

from .support import ROOT, load_script, run_main

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import complexity  # needs the scripts path first


def measured(source: str) -> dict[str, complexity.Measure]:
    return {m.name: m for m in complexity.measure_source(textwrap.dedent(source))}


class CyclomaticTests(unittest.TestCase):
    def test_every_decision_counts_as_radon_counts_it(self) -> None:
        m = measured("""
            def f(x):
                assert x
                if x and x or x:
                    pass
                elif x:
                    pass
                for i in x:
                    pass
                else:
                    pass
                while x:
                    pass
                try:
                    pass
                except E:
                    pass
                else:
                    pass
                match x:
                    case 1:
                        pass
                    case _:
                        pass
                return [i for i in x if i] if x else (lambda v: v if v else 0)
            """)
        # 1 + assert + if + 2 bool operands + elif + for + for-else + while
        # + except + try-else + 2 cases + comprehension for+if + ternary
        # + the lambda's ternary
        self.assertEqual(m["f"].cyclomatic, 17)

    def test_a_nested_function_is_measured_on_its_own(self) -> None:
        m = measured("""
            def outer(x):
                def inner(y):
                    if y:
                        return y
                class K:
                    def method(self):
                        if self:
                            return 1
                return inner
            """)
        self.assertEqual(m["outer"].cyclomatic, 1)
        self.assertEqual(m["outer.inner"].cyclomatic, 2)
        self.assertEqual(m["outer.K.method"].cyclomatic, 2)


class CognitiveTests(unittest.TestCase):
    CASES: ClassVar[dict[str, int]] = {
        "if x:\n    if x:\n        return [i for i in x if i]": 7,
        "for a in x:\n    if a:\n        while a:\n            pass": 6,
        "if x:\n    pass\nelif x:\n    pass\nelif x:\n    pass\nelse:\n    pass": 4,
        "return (x and x) or (x and x)": 3,
        "try:\n    pass\nexcept A:\n    if x:\n        pass\nelse:\n    pass\nfinally:\n    pass": 4,
        "match x:\n    case 1:\n        if x:\n            pass\n    case _:\n        pass": 3,
        "return 1 if x else (2 if x else 3)": 3,
        "for a in x:\n    pass\nelse:\n    pass": 2,
        "while x:\n    pass": 1,
        "return lambda v: v if v else 0": 2,
    }

    def test_each_structure_scores_as_complexipy_scores_it(self) -> None:
        for body, expected in self.CASES.items():
            with self.subTest(body=body):
                source = "def f(x):\n" + textwrap.indent(body, "    ") + "\n"
                self.assertEqual(measured(source)["f"].cognitive, expected)

    def test_a_nested_function_counts_toward_the_one_around_it(self) -> None:
        m = measured("""
            def outer(x):
                def inner(y):
                    if y:
                        return 1
                class K:
                    pass
                return inner
            """)
        self.assertEqual(m["outer"].cognitive, 1)


class HalsteadAndLinesTests(unittest.TestCase):
    def test_an_fstring_is_one_operand_on_every_python(self) -> None:
        plain = measured("def f(x):\n    return 'a' + x\n")["f"].halstead
        fstring = measured("def f(x):\n    return f'{x}' + x\n")["f"].halstead
        self.assertEqual(plain, fstring)
        multi = measured('def f(x):\n    return f"""a\n{x}\nb""" + x\n')["f"]
        self.assertEqual(multi.halstead, plain)

    def test_lines_leave_out_the_docstring_comments_blanks_and_nested_code(self) -> None:
        m = measured('''
            def f(x):
                """Docstring
                over two lines."""
                # a comment

                y = x
                def g():
                    return 1
                return y
            ''')
        self.assertEqual(m["f"].lines, 3)  # def, y = x, return y

    def test_untokenisable_source_measures_nothing(self) -> None:
        tree = complexity.ast.parse("def f():\n    return 1\n")
        function = tree.body[0]
        self.assertEqual(complexity.halstead_and_lines("def f(:\n    '''\n", function), (0.0, 0))

    def test_over_names_only_the_metrics_above_their_ceiling(self) -> None:
        m = complexity.Measure("f", 1, cyclomatic=11, cognitive=15, halstead=30.5, lines=60)
        self.assertEqual(m.over(), {"cyclomatic": 11, "halstead": 30.5})

    def test_files_count_their_non_blank_lines(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="agtmls-cx-"))
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        (tmp / "a.py").write_text("x = 1\n\n\ny = 2\n", encoding="utf-8")
        self.assertEqual(complexity.file_lines(tmp / "a.py"), 2)
        self.assertEqual([m.name for m in complexity.measure_file(tmp / "a.py")], [])


class CheckTests(unittest.TestCase):
    BIG = "def big(x):\n" + "".join(f"    if x == {i}:\n        return {i}\n" for i in range(12))

    def setUp(self) -> None:
        self.mod = load_script("check-complexity.py")
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-cxc-")).resolve()
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        (self.tmp / "scripts").mkdir()
        (self.tmp / "scripts" / "__pycache__").mkdir()
        (self.tmp / "scripts" / "__pycache__" / "x.py").write_text(self.BIG, encoding="utf-8")
        self.code = self.tmp / "scripts" / "m.py"
        self.code.write_text(self.BIG, encoding="utf-8")
        self.mod.ROOT = self.tmp
        self.mod.BASELINE = self.tmp / "complexity-baseline.json"

    def run_check(self, *args: str) -> tuple[int, str]:
        return run_main(self.mod, *args)

    def test_a_missing_baseline_is_a_failure(self) -> None:
        code, output = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: no complexity-baseline.json; run check-complexity.py --write", output)

    def test_recorded_offenders_pass_and_a_new_one_fails(self) -> None:
        self.assertEqual(self.run_check("--write")[0], 0)
        baseline = json.loads(self.mod.BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(baseline["functions"]["scripts/m.py::big"], {"cyclomatic": 13})
        code, output = self.run_check()
        self.assertEqual(code, 0, output)
        self.assertIn("1 function(s) and 0 file(s) remain over a ceiling", output)
        (self.tmp / "scripts" / "n.py").write_text(self.BIG, encoding="utf-8")
        code, output = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: scripts/n.py::big: cyclomatic 13 is over its ceiling and not in the baseline", output)

    def test_a_worse_offender_fails_and_a_better_one_must_be_recorded(self) -> None:
        self.run_check("--write")
        self.code.write_text(self.BIG + "    if x == 99:\n        return 99\n", encoding="utf-8")
        code, output = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: scripts/m.py::big: cyclomatic rose from 13 to 14", output)
        self.code.write_text(self.BIG.replace("    if x == 11:\n        return 11\n", ""), encoding="utf-8")
        code, output = self.run_check()
        self.assertIn("FAIL: scripts/m.py::big: cyclomatic fell from 13 to 12; record it with check-complexity.py --write", output)
        self.code.write_text("def big(x):\n    return x\n", encoding="utf-8")
        code, output = self.run_check()
        self.assertIn("cyclomatic (13) is now within its ceiling or gone", output)
        self.assertIn("FAIL: 0 regression(s), 1 unrecorded improvement(s)", output)

    def test_another_repository_is_measured_against_its_own_baseline(self) -> None:
        other = self.tmp / "other"
        (other / "conformance").mkdir(parents=True)
        (other / "conformance" / "run.py").write_text(self.BIG, encoding="utf-8")
        baseline = other / "complexity-baseline.json"
        args = ("--root", str(other), "--paths", "conformance", "--baseline", str(baseline))
        code, output = self.run_check(*args)
        self.assertEqual(code, 1)
        self.assertIn("FAIL: no complexity-baseline.json", output)
        self.assertEqual(self.run_check(*args, "--write")[0], 0)
        self.assertIn("conformance/run.py::big", json.loads(baseline.read_text(encoding="utf-8"))["functions"])
        self.assertEqual(self.run_check(*args)[0], 0)
        self.assertFalse(self.mod.BASELINE.exists(), "this repository's baseline was written")

    def test_a_long_file_and_a_repeated_name_are_recorded_once(self) -> None:
        body = "\n".join(f"v{i} = {i}" for i in range(501)) + "\n" + self.BIG + self.BIG.replace("12", "13")
        self.code.write_text(body, encoding="utf-8")
        self.run_check("--write")
        baseline = json.loads(self.mod.BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(baseline["files"]["scripts/m.py"], {"lines": complexity.file_lines(self.code)})
        self.assertEqual(baseline["functions"]["scripts/m.py::big"], {"cyclomatic": 13})


if __name__ == "__main__":
    unittest.main()
