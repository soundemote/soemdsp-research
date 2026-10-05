# soemdsp-research

Research plots for [soemdsp](https://github.com/soundemote/soemdsp). This repo holds interactive fall-math graphs. It is not the sandbox instrument and it does not implement audio processing.

Each study lives under `graphs/<name>/` with the same shape: constants in `config.json`, the recursion in Python (and a matching browser copy when the page runs sample-by-sample), a Plotly figure, and an interactive page.

## Ping Envelope

`graphs/ping_envelope/` is a sample-by-sample **one-pole chase** of a ping falling toward silence. There is no attack stage, no hold, and no multipoint ADSR. The curve is one continuous recursion:

```text
env[0] = trigger_height
x      = feedback * env + offset
shape  = 0 if x <= 0 else 1 if x >= 1 else 10 ** (5 * (x - 1))
f      = shape * max_release_hz
k      = 1 - exp(-2 * pi * f / sample_rate)
env    = env + k * (0 - env)
```

`k` is 0 when `f <= 0` and 1 when `f` is at or above Nyquist. The 5-decade `shape` is the sandbox Ping Envelope release map. It is fixed. It is not a fifth control.

### Parameters

Four sliders. There is no mode axis beside them. An example overlay is only a saved set of these four numbers.

| Slider | Role in the recursion |
| --- | --- |
| Feedback amount | Scale on `env` inside `x` |
| Max release Hz | Scale on `shape`, in hertz. This is what becomes the one-pole coefficient |
| Offset | Added in `x` |
| Trigger height | `env[0]`, the state at the release edge, before the first fall sample |

Sample tuples used as overlay examples:

| Example | Feedback | Max release Hz | Offset | Trigger height |
| --- | --- | --- | --- | --- |
| A | 1 | 10 | 0 | 1 |
| B | 0.7718 | 1000 | 0.5 | 1 |
| C | 0.7718 | 1000 | 0 | 1 |

Every example uses the same recursion. **Load** copies that tuple into the sliders. Checking it draws the curve on top of the live one. The page opens with the sliders on example B.

### Floors

- **Engineering stop: 0.001 (−60 dB re amplitude 1).** The sample loop ends at the first sample at or below this level. That time is the tail length.
- **Perceptual marker: 0.01 (−40 dB),** a dashed horizontal line. It does not end the curve.
- The run can also end early if the release rate hits 0 (the fall stalls above 0.001) or at the **120 s** window cap. A cap is not the engineering floor.

Sample rate is **48 kHz**. It is fixed so tails stay comparable. It is not a slider.

### How to run

Python 3.10+ and Plotly:

```bash
pip install -r requirements.txt
python -m graphs.ping_envelope
```

That prints tail times for the three example settings, writes a self-contained Plotly snapshot to `graphs/ping_envelope/preview.html`, and copies `plotly.min.js` beside the page when the installed package has it.

Interactive graph (sliders, overlay checkboxes, both floor lines):

Open `graphs/ping_envelope/index.html` in a browser.

The page uses the local `plotly.min.js` from the command above. Without that file it loads Plotly from the CDN. The four sliders recompute the sample loop and update the Plotly traces. Example checkboxes add or remove those saved settings. Log amplitude is on by default so 0.001 and 0.01 sit on separate decades; uncheck it for a linear axis. Time window switches between the full tail, the live curve, and the first 2 seconds.

Notebook (optional Jupyter):

```bash
pip install jupyter
jupyter notebook graphs/ping_envelope/ping_envelope.ipynb
```

### Tests

From the repo root:

```bash
python -m unittest graphs.ping_envelope.test_simulate
```

The suite checks the one-pole step, that 0.001 is the stop (and 0.01 is not), and that `fall_math.js` matches the Python recursion. Node is required for that last check.

## Adding a graph

Create `graphs/<next>/` the same way:

- `config.json` for constants and example slider settings
- `simulate.py` for the recursion, with the update written out in the module docstring
- `plot.py` for a Plotly figure
- `index.html` when the study needs live controls
- a notebook if a narrated walkthrough helps

Keep extra curves as saved sets of the same parameters. Do not add a mode axis.
