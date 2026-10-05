"""Sample-by-sample Ping Envelope fall.

The curve is one continuous one-pole chase toward silence. There is no
attack stage, no hold, and no multipoint ADSR.

    env[0] = trigger_height
    x      = feedback * env + offset
    shape  = 0 if x <= 0 else 1 if x >= 1 else 10 ** (5 * (x - 1))
    f      = shape * max_release_hz
    k      = 1 - exp(-2 * pi * f / sample_rate)
    env    = env + k * (0 - env)

k is 0 when f <= 0 and 1 when f is at or above Nyquist.

Sample rate is 48 kHz (``config.json``). It is not a slider.

Max release Hz enters only as the scale on the 5-decade shape. Feedback
and offset enter only through x. Trigger height is the envelope state at
the release edge, before the first fall sample.

The 5-decade shape is the sandbox Ping Envelope release map. Short and
Long use that same map; in this graph they are presets of the four
parameters, not an extra axis. Offset absorbs the module Decay knob:

    Short offset = 0.5 - decay     Short feedback = 1       Short max = 10 Hz
    Long offset  = 1 - decay       Long feedback  = 0.7718  Long max  = 1000 Hz

Recording stops at amplitude 0.001 (−60 dB re 1), the engineering tail.
A time cap, or a stall where the release rate hits 0 above that floor,
can end the run sooner. The perceptual level 0.01 (−40 dB) is a marker
only. It is not a stop.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.json")

_CONFIG: dict | None = None


def load_config() -> dict:
    """Return the shared graph constants and model presets."""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return _CONFIG


@dataclass(frozen=True)
class PingParams:
    """The four sweepable fall parameters. A model is only a named bundle of these."""

    feedback: float
    max_release_hz: float
    offset: float
    trigger_height: float

    @classmethod
    def from_mapping(cls, raw: dict) -> PingParams:
        return cls(
            feedback=float(raw["feedback"]),
            max_release_hz=float(raw["max_release_hz"]),
            offset=float(raw["offset"]),
            trigger_height=float(raw["trigger_height"]),
        )


@dataclass(frozen=True)
class Model:
    id: str
    label: str
    color: str
    visible_by_default: bool
    note: str
    params: PingParams


@dataclass(frozen=True)
class FallCurve:
    """Decimated fall. ``samples`` is the number of one-pole updates applied."""

    time_s: tuple[float, ...]
    amplitude: tuple[float, ...]
    sample_rate: float
    samples: int
    stopped: str
    t_eng_s: float | None
    t_perceptual_s: float | None
    end_amplitude: float
    params: PingParams


def models() -> tuple[Model, ...]:
    config = load_config()
    out = []
    for raw in config["models"]:
        out.append(
            Model(
                id=str(raw["id"]),
                label=str(raw["label"]),
                color=str(raw["color"]),
                visible_by_default=bool(raw["visible_by_default"]),
                note=str(raw["note"]),
                params=PingParams.from_mapping(raw),
            )
        )
    return tuple(out)


def model_by_id(model_id: str) -> Model:
    for model in models():
        if model.id == model_id:
            return model
    raise KeyError(model_id)


def release_hz(env: float, params: PingParams, decades: float = 5.0) -> float:
    """Level-dependent release rate in Hz.

    ``x = feedback * env + offset`` is pushed through the fixed 5-decade
    Ping Envelope curve and then scaled by max release Hz. That curve is
    not a fifth control.
    """
    x = params.feedback * env + params.offset
    if x <= 0.0:
        shape = 0.0
    elif x >= 1.0:
        shape = 1.0
    else:
        shape = 10.0 ** (decades * (x - 1.0))
    rate = shape * params.max_release_hz
    if rate <= 0.0:
        return 0.0
    return rate


def one_pole_coeff(rate_hz: float, sample_rate: float) -> float:
    """One-pole chase coefficient from a cutoff in Hz.

    ``k = 1 - exp(-2π f / sample_rate)`` so that
    ``env <- env + k * (target - env)`` tracks a one-pole lowpass.
    On this graph the fall target is always 0.
    """
    if rate_hz <= 0.0 or sample_rate <= 0.0:
        return 0.0
    if rate_hz >= sample_rate * 0.5:
        return 1.0
    k = 1.0 - math.exp((-2.0 * math.pi * rate_hz) / sample_rate)
    if k < 0.0:
        return 0.0
    if k > 1.0:
        return 1.0
    return k


def step_env(env: float, params: PingParams, sample_rate: float, decades: float = 5.0) -> float:
    """Apply one sample of the fall recursion."""
    rate = release_hz(env, params, decades)
    k = one_pole_coeff(rate, sample_rate)
    return env + k * (0.0 - env)


def env_after(
    params: PingParams,
    steps: int,
    *,
    sample_rate: float | None = None,
    decades: float | None = None,
) -> float:
    """Run the recursion exactly ``steps`` times and return the state."""
    config = load_config()
    sr = float(config["sample_rate"] if sample_rate is None else sample_rate)
    span = float(config["exp_decades"] if decades is None else decades)
    env = float(params.trigger_height)
    for _ in range(steps):
        env = step_env(env, params, sr, span)
    return env


def simulate_fall(
    params: PingParams,
    *,
    sample_rate: float | None = None,
    max_seconds: float | None = None,
    eng_floor: float | None = None,
    perceptual_floor: float | None = None,
    record_relative_drop: float | None = None,
) -> FallCurve:
    """Chase silence sample by sample until the engineering floor, a stall, or the time cap.

    Plot points are kept when amplitude has fallen 0.5% from the last stored
    point (see ``record_relative_drop``), plus the exact stop sample. The
    stop itself is still decided on every sample.
    """
    config = load_config()
    sr = float(config["sample_rate"] if sample_rate is None else sample_rate)
    if sr <= 0.0:
        raise ValueError("sample_rate must be positive")
    window = float(config["max_seconds"] if max_seconds is None else max_seconds)
    eng = float(config["eng_floor"] if eng_floor is None else eng_floor)
    perceptual = float(config["perceptual_floor"] if perceptual_floor is None else perceptual_floor)
    drop = float(
        config["record_relative_drop"] if record_relative_drop is None else record_relative_drop
    )
    decades = float(config["exp_decades"])
    nmax = int(math.floor(window * sr))

    env = float(params.trigger_height)
    times = [0.0]
    amps = [env]
    last_stored = env
    t_perceptual: float | None = None

    def finish(samples: int, stopped: str, t_eng: float | None, env_end: float) -> FallCurve:
        t = samples / sr
        if times[-1] != t:
            times.append(t)
            amps.append(env_end)
        return FallCurve(
            time_s=tuple(times),
            amplitude=tuple(amps),
            sample_rate=sr,
            samples=samples,
            stopped=stopped,
            t_eng_s=t_eng,
            t_perceptual_s=t_perceptual,
            end_amplitude=env_end,
            params=params,
        )

    if env <= eng:
        return finish(0, "eng_floor", 0.0, env)
    if release_hz(env, params, decades) <= 0.0:
        return finish(0, "stalled", None, env)

    fb = params.feedback
    offset = params.offset
    fmax = params.max_release_hz
    nyquist = sr * 0.5
    exp = math.exp
    two_pi = 2.0 * math.pi

    for n in range(1, nmax + 1):
        x = fb * env + offset
        if x <= 0.0:
            shape = 0.0
        elif x >= 1.0:
            shape = 1.0
        else:
            shape = 10.0 ** (decades * (x - 1.0))
        rate = shape * fmax
        if rate <= 0.0:
            return finish(n - 1, "stalled", None, env)
        if rate >= nyquist:
            k = 1.0
        else:
            k = 1.0 - exp((-two_pi * rate) / sr)
            if k < 0.0:
                k = 0.0
            elif k > 1.0:
                k = 1.0
        env = env + k * (0.0 - env)
        if t_perceptual is None and env <= perceptual:
            t_perceptual = n / sr
        hit_eng = env <= eng
        if last_stored > 0.0:
            store = ((last_stored - env) / last_stored) >= drop
        else:
            store = False
        if store or hit_eng:
            times.append(n / sr)
            amps.append(env)
            last_stored = env
        if hit_eng:
            return finish(n, "eng_floor", n / sr, env)

    return finish(nmax, "time_cap", None, env)
