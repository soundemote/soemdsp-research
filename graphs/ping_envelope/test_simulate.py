"""Checks for the Ping Envelope fall recursion and the JS twin."""

from __future__ import annotations

import json
import math
import re
import subprocess
import unittest
from pathlib import Path

from graphs.ping_envelope.plot import render_index_html
from graphs.ping_envelope.simulate import (
    PingParams,
    env_after,
    example_by_id,
    examples,
    load_config,
    release_hz,
    simulate_fall,
    step_env,
)

HERE = Path(__file__).resolve().parent


class PingFallTests(unittest.TestCase):
    def test_examples_are_four_parameter_settings(self) -> None:
        config = load_config()
        self.assertEqual(
            [item["id"] for item in config["examples"]],
            [example.id for example in examples()],
        )
        for raw in config["examples"]:
            self.assertEqual(
                set(PingParams.from_mapping(raw).__dict__),
                {"feedback", "max_release_hz", "offset", "trigger_height"},
            )
            self.assertTrue(str(raw["label"]).startswith("Example "))
        self.assertNotIn("examples", config["slider_ranges"])
        example_b = example_by_id("example_b")
        self.assertEqual(example_b.params.feedback, 0.7718)
        self.assertEqual(example_b.params.max_release_hz, 1000)
        self.assertEqual(example_b.params.offset, 0.5)
        self.assertEqual(example_b.params.trigger_height, 1.0)
        example_a = example_by_id("example_a")
        self.assertEqual(example_a.params.feedback, 1.0)
        self.assertEqual(example_a.params.max_release_hz, 10)
        self.assertEqual(example_a.params.offset, 0.0)

    def test_shipped_text_has_no_mode_names(self) -> None:
        # Whole-word names that must not ship as modes. Built without those
        # literals so this file can still describe the ban.
        banned = re.compile(r"\b(?:" + "sho" + "rt|" + "lo" + "ng" + r")\b", re.IGNORECASE)
        root = HERE.parents[1]
        paths = [root / "README.md", *root.joinpath("graphs").rglob("*")]
        offenders = []
        for path in paths:
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".js", ".html", ".md", ".ipynb", ".json"}:
                continue
            if path.name in {"plotly.min.js", "test_simulate.py"}:
                continue
            text = path.read_text(encoding="utf-8")
            if banned.search(text):
                offenders.append(str(path.relative_to(root)))
        self.assertEqual(offenders, [])

    def test_first_step_matches_the_one_pole_formula(self) -> None:
        params = example_by_id("example_b").params
        sr = load_config()["sample_rate"]
        # x = 0.7718 * 1 + 0.5 > 1, so release is the full 1000 Hz.
        rate = 1000.0
        k = 1.0 - math.exp(-2.0 * math.pi * rate / sr)
        expected = 1.0 + k * (0.0 - 1.0)
        self.assertAlmostEqual(release_hz(1.0, params), rate)
        self.assertAlmostEqual(step_env(1.0, params, sr), expected)
        self.assertAlmostEqual(env_after(params, 1), expected)

    def test_example_b_stops_at_eng_floor_not_perceptual(self) -> None:
        curve = simulate_fall(example_by_id("example_b").params)
        self.assertEqual(curve.stopped, "eng_floor")
        self.assertLessEqual(curve.end_amplitude, 0.001)
        self.assertGreater(curve.end_amplitude, 0.0)
        self.assertIsNotNone(curve.t_perceptual_s)
        self.assertIsNotNone(curve.t_eng_s)
        assert curve.t_perceptual_s is not None and curve.t_eng_s is not None
        self.assertLess(curve.t_perceptual_s, curve.t_eng_s)
        self.assertTrue(any(amp > 0.01 for amp in curve.amplitude))
        self.assertTrue(any(0.001 < amp < 0.01 for amp in curve.amplitude))
        self.assertLess(curve.t_eng_s, 1.0)

    def test_example_a_does_not_use_perceptual_as_the_stop(self) -> None:
        curve = simulate_fall(example_by_id("example_a").params, max_seconds=1.0)
        self.assertNotEqual(curve.stopped, "eng_floor")
        self.assertGreater(curve.end_amplitude, 0.01)
        self.assertIsNone(curve.t_eng_s)
        self.assertIsNone(curve.t_perceptual_s)

    def test_stall_when_release_rate_is_zero(self) -> None:
        params = PingParams(feedback=1.0, max_release_hz=1000.0, offset=-0.4, trigger_height=0.4)
        curve = simulate_fall(params, max_seconds=5.0)
        self.assertEqual(curve.stopped, "stalled")
        self.assertEqual(curve.samples, 0)
        self.assertGreater(curve.end_amplitude, 0.001)
        self.assertIsNone(curve.t_eng_s)

    def test_time_cap_is_not_the_eng_floor(self) -> None:
        params = PingParams(feedback=1.0, max_release_hz=1e-6, offset=0.0, trigger_height=1.0)
        curve = simulate_fall(params, max_seconds=0.05)
        self.assertEqual(curve.stopped, "time_cap")
        self.assertGreater(curve.end_amplitude, 0.01)
        self.assertIsNone(curve.t_eng_s)

    def test_trigger_height_changes_the_rate_not_just_the_scale(self) -> None:
        base = dict(feedback=0.7718, max_release_hz=1000.0, offset=0.0)
        high = simulate_fall(PingParams(trigger_height=1.0, **base), max_seconds=0.02)
        low = simulate_fall(PingParams(trigger_height=0.5, **base), max_seconds=0.02)
        # Same number of samples, different fraction of the starting height,
        # because release Hz depends on the current level.
        self.assertEqual(high.samples, low.samples)
        self.assertNotAlmostEqual(
            high.end_amplitude / high.params.trigger_height,
            low.end_amplitude / low.params.trigger_height,
            places=3,
        )

    def test_index_html_embeds_the_config(self) -> None:
        rendered = render_index_html()
        self.assertEqual((HERE / "index.html").read_text(encoding="utf-8"), rendered)
        start = rendered.index('<script id="ping-config" type="application/json">')
        body = rendered[start:].split(">", 1)[1].split("</script>", 1)[0]
        self.assertEqual(json.loads(body), json.loads((HERE / "config.json").read_text(encoding="utf-8")))

    def test_javascript_matches_python(self) -> None:
        script = r"""
const fs = require("fs");
const path = require("path");
const api = require("./fall_math.js");
const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, "config.json"), "utf8"));
const out = { examples: {}, probes: {} };
for (const example of cfg.examples) {
  const curve = api.simulateFall(example, cfg);
  out.examples[example.id] = {
    stopped: curve.stopped,
    samples: curve.samples,
    tEng: curve.tEng,
    tPerc: curve.tPerc,
    endAmp: curve.endAmp,
    times: curve.times,
    amps: curve.amps,
  };
}
const probe = cfg.examples.find((example) => example.id === "example_a");
out.probes.example_a_10000 = api.envAfter(probe, 10000, cfg.sample_rate, cfg.exp_decades);
console.log(JSON.stringify(out));
"""
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=HERE,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        for example in examples():
            py = simulate_fall(example.params)
            js = payload["examples"][example.id]
            self.assertEqual(js["stopped"], py.stopped, example.id)
            self.assertAlmostEqual(js["samples"], py.samples, delta=2, msg=example.id)
            self.assertAlmostEqual(js["endAmp"], py.end_amplitude, places=8, msg=example.id)
            if py.t_eng_s is None:
                self.assertIsNone(js["tEng"])
            else:
                self.assertAlmostEqual(js["tEng"], py.t_eng_s, delta=1e-4)
            if py.t_perceptual_s is None:
                self.assertIsNone(js["tPerc"])
            else:
                self.assertAlmostEqual(js["tPerc"], py.t_perceptual_s, delta=1e-4)
        example_a = example_by_id("example_a").params
        self.assertAlmostEqual(
            payload["probes"]["example_a_10000"],
            env_after(example_a, 10000),
            places=9,
        )


if __name__ == "__main__":
    unittest.main()
