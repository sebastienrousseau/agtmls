"""Differential property test TEMPLATE (Python `hypothesis`).

Assert the PORT agrees with the SOURCE (used as an oracle) over generated
inputs. The source is shelled out to; swap in a direct import if it is
importable. Copy next to an example, adjust SOURCE_CMD / PORT_CMD and the
`@given` strategy to your function's input domain, then:

    pip install hypothesis pytest && pytest hypothesis_diff.py
"""

import subprocess

from hypothesis import given
from hypothesis import strategies as st

SOURCE_CMD = ["python3", "reference.py"]  # the reference oracle
PORT_CMD = ["./port"]  # compiled target path, or an interpreter command


def run(cmd: list[str], stdin: str) -> str:
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True).stdout


# Shape the alphabet/size to your function's real input domain — the tighter
# it is, the more of the generated inputs exercise interesting branches.
@given(st.text(alphabet="0123456789ABCDEFGabcdefg #/:", min_size=0, max_size=40))
def test_port_matches_source(line: str) -> None:
    stdin = line + "\n"
    assert run(PORT_CMD, stdin) == run(SOURCE_CMD, stdin), f"divergence on {line!r}"
