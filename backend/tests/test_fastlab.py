"""Fast mode spec: derived from lab.yaml, same tools/gates, only prompts (and an optional model) differ.
Run: python tests/test_fastlab.py
"""
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import yaml  # noqa: E402

from sparklab import fastlab  # noqa: E402

AGENTS = ("scout", "skeptic", "experimenter")


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"  ok  {msg}")


def without_prompts(spec):
    d = yaml.safe_load(yaml.safe_dump(spec))
    d.pop("description"), d.pop("prompt"), d["executor"].pop("model", None)
    for n in AGENTS:
        d["tools"][n].pop("prompt"), d["tools"][n]["executor"].pop("model", None)
    return d


def main():
    base = yaml.safe_load((BACKEND / "lab.yaml").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        out = fastlab.write_fast_spec(Path(tmp) / "lab.yaml", model="some-model")
        fast = yaml.safe_load(out.read_text())
    check(fast["name"] == base["name"] == "spark_lab", "agent keeps the name spark_lab (API/UI session matching)")
    check(without_prompts(fast) == without_prompts(base), "tools, policies and executors identical to lab.yaml")
    check(fast["prompt"].startswith(base["prompt"].rstrip()) and "FAST MODE" in fast["prompt"], "supervisor prompt = lab.yaml + fast note")
    for n in AGENTS:
        check(fast["tools"][n]["prompt"].startswith(base["tools"][n]["prompt"].rstrip()) and "FAST MODE" in fast["tools"][n]["prompt"],
              f"{n} prompt = lab.yaml + fast note")
        check(not any(k in fast["tools"][n]["tools"] for k in ("approve", "unseal")), f"{n} has no approve/unseal tool")
    check("EVERY board expectation" in fast["tools"]["skeptic"]["prompt"].split("FAST MODE")[1],
          "fast skeptic still checks every board expectation (seeded control)")
    check(fast["executor"]["model"] == "some-model" and all(fast["tools"][n]["executor"]["model"] == "some-model" for n in AGENTS),
          "--model pins every executor")
    check("model" not in fastlab.fast_spec()["executor"], "no model pinned by default")
    os.environ.pop("SPARK_LAB_MODE", None)
    check(fastlab.mode() == "full", "mode is full unless SPARK_LAB_MODE=fast")
    os.environ["SPARK_LAB_MODE"] = "fast"
    check(fastlab.mode() == "fast", "SPARK_LAB_MODE=fast selects fast mode")
    try:
        from sparklab import api
    except ImportError:
        print("  --  api extras not installed; bundle check skipped")
    else:
        import io
        import tarfile
        with tarfile.open(fileobj=io.BytesIO(api.build_agent_bundle()), mode="r:gz") as tf:
            text = tf.extractfile(tf.getmembers()[0]).read().decode()
        check("FAST MODE" in text, "API bundle uses the fast spec when SPARK_LAB_MODE=fast")
    print("OK")


if __name__ == "__main__":
    main()
