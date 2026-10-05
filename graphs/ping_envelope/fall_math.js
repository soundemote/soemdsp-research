// Sample-by-sample Ping Envelope fall.
// Keep this recursion identical to simulate.py.
//
//   env[0] = trigger_height
//   x = feedback * env + offset
//   shape = clip(10 ** (5 * (x - 1)), 0, 1) * max(sign(x), 0)
//   f = shape * max_release_hz
//   u = max(sign(sample_rate / 2 - f), 0)
//   k = u * clip(1 - exp(-2 * pi * f / sample_rate), 0, 1) + (1 - u)
//   env = env + k * (0 - env)
//
//   clip(v, 0, 1) = min(max(v, 0), 1), sign(0) = 0.
//
// Stop at eng_floor (0.001). Do not stop at the 0.01 perceptual marker.
// Also stop on stall (release rate hits 0) or at max_seconds.

(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.pingFall = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function releaseHz(env, params, decades) {
    const x = params.feedback * env + params.offset;
    let shape;
    if (x <= 0) shape = 0;
    else if (x >= 1) shape = 1;
    else shape = 10 ** (decades * (x - 1));
    const rate = shape * params.max_release_hz;
    return rate > 0 ? rate : 0;
  }

  function onePoleCoeff(rateHz, sampleRate) {
    if (rateHz <= 0 || sampleRate <= 0) return 0;
    if (rateHz >= sampleRate * 0.5) return 1;
    let k = 1 - Math.exp((-2 * Math.PI * rateHz) / sampleRate);
    if (k < 0) return 0;
    if (k > 1) return 1;
    return k;
  }

  function stepEnv(env, params, sampleRate, decades) {
    const rate = releaseHz(env, params, decades);
    const k = onePoleCoeff(rate, sampleRate);
    return env + k * (0 - env);
  }

  function envAfter(params, steps, sampleRate, decades) {
    let env = params.trigger_height;
    for (let i = 0; i < steps; i += 1) {
      env = stepEnv(env, params, sampleRate, decades);
    }
    return env;
  }

  function createSimulation(params, cfg) {
    const sr = cfg.sample_rate;
    return {
      params,
      decades: cfg.exp_decades,
      sr,
      eng: cfg.eng_floor,
      perceptual: cfg.perceptual_floor,
      drop: cfg.record_relative_drop,
      nmax: Math.floor(cfg.max_seconds * sr),
      env: params.trigger_height,
      n: 0,
      started: false,
      times: [0],
      amps: [params.trigger_height],
      lastStored: params.trigger_height,
      tPerceptual: null,
      done: false,
      result: null,
      fb: params.feedback,
      offset: params.offset,
      fmax: params.max_release_hz,
      nyquist: sr * 0.5,
    };
  }

  function finish(state, samples, stopped, tEng, envEnd) {
    const t = samples / state.sr;
    if (state.times[state.times.length - 1] !== t) {
      state.times.push(t);
      state.amps.push(envEnd);
    }
    state.done = true;
    state.result = {
      times: state.times,
      amps: state.amps,
      sampleRate: state.sr,
      samples,
      stopped,
      tEng,
      tPerc: state.tPerceptual,
      endAmp: envEnd,
    };
    return state.result;
  }

  // Run up to `budget` one-pole updates. Returns the curve when finished, else null.
  function advanceSimulation(state, budget) {
    if (state.done) return state.result;
    if (!state.started) {
      state.started = true;
      if (state.env <= state.eng) return finish(state, 0, "eng_floor", 0, state.env);
      if (releaseHz(state.env, state.params, state.decades) <= 0) {
        return finish(state, 0, "stalled", null, state.env);
      }
    }
    const limit = Math.min(state.nmax, state.n + budget);
    const twoPi = 2 * Math.PI;
    while (state.n < limit) {
      const n = state.n + 1;
      const x = state.fb * state.env + state.offset;
      let shape;
      if (x <= 0) shape = 0;
      else if (x >= 1) shape = 1;
      else shape = 10 ** (state.decades * (x - 1));
      const rate = shape * state.fmax;
      if (!(rate > 0)) return finish(state, state.n, "stalled", null, state.env);
      let k;
      if (rate >= state.nyquist) k = 1;
      else {
        k = 1 - Math.exp((-twoPi * rate) / state.sr);
        if (k < 0) k = 0;
        else if (k > 1) k = 1;
      }
      state.env = state.env + k * (0 - state.env);
      state.n = n;
      if (state.tPerceptual === null && state.env <= state.perceptual) {
        state.tPerceptual = n / state.sr;
      }
      const hitEng = state.env <= state.eng;
      const store = state.lastStored > 0
        ? (state.lastStored - state.env) / state.lastStored >= state.drop
        : false;
      if (store || hitEng) {
        state.times.push(n / state.sr);
        state.amps.push(state.env);
        state.lastStored = state.env;
      }
      if (hitEng) return finish(state, n, "eng_floor", n / state.sr, state.env);
    }
    if (state.n >= state.nmax) return finish(state, state.nmax, "time_cap", null, state.env);
    return null;
  }

  function simulateFall(params, cfg) {
    const state = createSimulation(params, cfg);
    let result = null;
    while (!result) {
      result = advanceSimulation(state, state.nmax + 1);
    }
    return result;
  }

  return {
    releaseHz,
    onePoleCoeff,
    stepEnv,
    envAfter,
    createSimulation,
    advanceSimulation,
    simulateFall,
  };
});
