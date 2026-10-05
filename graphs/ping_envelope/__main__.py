"""Run the Ping Envelope fall study from the repo root.

    python -m graphs.ping_envelope
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from graphs.ping_envelope.plot import HERE, build_figure, render_index_html, write_index
from graphs.ping_envelope.simulate import load_config, models, simulate_fall


def _format_time(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 1.0:
        return f"{seconds * 1000:.2f} ms"
    return f"{seconds:.3f} s"


def _stop_text(stopped: str, max_seconds: float) -> str:
    if stopped == "eng_floor":
        return "reached 0.001"
    if stopped == "stalled":
        return "stalled, release hit 0"
    return f"capped at {max_seconds:g} s"


def copy_plotly_js() -> Path | None:
    """Copy the installed Plotly bundle next to the page so it works offline."""
    try:
        import plotly
    except ImportError:
        return None
    source = Path(plotly.__file__).resolve().parent / "package_data" / "plotly.min.js"
    if not source.is_file():
        return None
    destination = HERE / "plotly.min.js"
    if not destination.exists() or destination.stat().st_size != source.stat().st_size:
        shutil.copyfile(source, destination)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ping Envelope fall graph")
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Skip the self-contained Plotly snapshot (preview.html).",
    )
    parser.add_argument(
        "--write-index",
        action="store_true",
        help="Rewrite index.html from the template and config.json.",
    )
    args = parser.parse_args(argv)

    config = load_config()
    rendered = render_index_html()
    index_path = HERE / "index.html"
    if args.write_index or not index_path.exists() or index_path.read_text(encoding="utf-8") != rendered:
        write_index(index_path)

    print("Ping Envelope fall")
    print(
        f"sample rate {config['sample_rate']} Hz, "
        f"eng floor {config['eng_floor']}, "
        f"window {config['max_seconds']:g} s"
    )
    print()

    named = []
    for model in models():
        print(f"Simulating {model.label}…", flush=True)
        curve = simulate_fall(model.params)
        named.append((model.label, model.color, curve))
        print(
            f"  {model.label:<18} "
            f"−40 dB {_format_time(curve.t_perceptual_s):>10}   "
            f"−60 dB {_format_time(curve.t_eng_s):>10}   "
            f"end {curve.end_amplitude:.6f}   "
            f"{_stop_text(curve.stopped, config['max_seconds'])}"
        )

    if not args.no_preview:
        preview = HERE / "preview.html"
        build_figure(named, log_y=True, title="Ping Envelope fall — model presets").write_html(
            preview, include_plotlyjs=True, full_html=True
        )
        print()
        print(f"Wrote {preview}")

    local_js = copy_plotly_js()
    print(f"Interactive page: {index_path}")
    if local_js is not None:
        print(f"Local Plotly bundle: {local_js}")
    else:
        print("plotly.min.js was not copied; the page will use the Plotly CDN.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
