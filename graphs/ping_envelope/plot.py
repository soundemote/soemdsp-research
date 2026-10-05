"""Plotly figures for the Ping Envelope fall."""

from __future__ import annotations

import math
from pathlib import Path

import plotly.graph_objects as go

from graphs.ping_envelope.simulate import FallCurve, load_config, models, simulate_fall

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "page_template.html"
INDEX_PATH = HERE / "index.html"
PREVIEW_PATH = HERE / "preview.html"

ENG_COLOR = "#9a3412"
PERCEPTUAL_COLOR = "#57534e"
PAPER = "#fbfaf7"
INK = "#1c1917"


def build_figure(
    curves: list[tuple[str, str, FallCurve]],
    *,
    show_perceptual: bool = True,
    log_y: bool = False,
    title: str = "Ping Envelope fall",
) -> go.Figure:
    """Time vs amplitude for named curves.

    ``curves`` items are ``(label, color, curve)``. The engineering floor
    is always drawn. The −40 dB marker is the optional dashed line at 0.01.
    """
    config = load_config()
    fig = go.Figure()
    peak = 1.0
    for label, color, curve in curves:
        fig.add_trace(
            go.Scatter(
                x=list(curve.time_s),
                y=list(curve.amplitude),
                mode="lines",
                name=label,
                line={"color": color, "width": 2},
                hovertemplate="%{x:.4f} s<br>%{y:.5f}<extra>" + label + "</extra>",
            )
        )
        if curve.amplitude:
            peak = max(peak, max(curve.amplitude))

    fig.add_hline(
        y=config["eng_floor"],
        line_dash="dot",
        line_color=ENG_COLOR,
        line_width=1.5,
        annotation_text="0.001 eng (−60 dB)",
        annotation_position="top right",
        annotation_font_size=11,
        annotation_font_color=ENG_COLOR,
    )
    if show_perceptual:
        fig.add_hline(
            y=config["perceptual_floor"],
            line_dash="dash",
            line_color=PERCEPTUAL_COLOR,
            line_width=1,
            annotation_text="0.01 (−40 dB)",
            annotation_position="top right",
            annotation_font_size=11,
            annotation_font_color=PERCEPTUAL_COLOR,
        )

    fig.update_layout(
        title={"text": title, "font": {"size": 18, "color": INK}},
        paper_bgcolor=PAPER,
        plot_bgcolor="#ffffff",
        margin={"l": 64, "r": 24, "t": 56, "b": 56},
        legend={"orientation": "h", "y": 1.12},
        hovermode="x unified",
        font={"family": "Georgia, serif", "color": INK, "size": 13},
        height=560,
    )
    fig.update_xaxes(
        title_text="Time (seconds)",
        rangemode="tozero",
        zeroline=False,
        gridcolor="#e7e5e4",
        showline=True,
        linecolor="#d6d3d1",
    )
    y_title = "Amplitude (log)" if log_y else "Amplitude"
    if log_y:
        y_range = [math.log10(config["eng_floor"] * 0.25), math.log10(max(peak, config["perceptual_floor"]) * 1.35)]
    else:
        y_range = [0, peak * 1.08]
    fig.update_yaxes(
        title_text=y_title,
        type="log" if log_y else "linear",
        rangemode="tozero",
        zeroline=False,
        gridcolor="#e7e5e4",
        showline=True,
        linecolor="#d6d3d1",
        range=y_range,
        dtick=1 if log_y else None,
    )
    return fig


def preset_curves() -> list[tuple[str, str, FallCurve]]:
    return [(model.label, model.color, simulate_fall(model.params)) for model in models()]


def write_preview(path: Path | None = None) -> Path:
    """Write a self-contained Plotly HTML snapshot of the model presets."""
    destination = Path(path) if path is not None else PREVIEW_PATH
    fig = build_figure(preset_curves(), log_y=True, title="Ping Envelope fall — model presets")
    fig.write_html(destination, include_plotlyjs=True, full_html=True)
    return destination


def render_index_html() -> str:
    """Inline ``config.json`` into the interactive page template."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    config_text = (HERE / "config.json").read_text(encoding="utf-8").strip()
    token = "__PING_CONFIG_JSON__"
    if token not in template:
        raise RuntimeError(f"{TEMPLATE_PATH.name} is missing {token}")
    return template.replace(token, config_text)


def write_index(path: Path | None = None) -> Path:
    destination = Path(path) if path is not None else INDEX_PATH
    destination.write_text(render_index_html(), encoding="utf-8")
    return destination
