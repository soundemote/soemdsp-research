env[0] = trigger_height
x = feedback * env + offset
shape = clip(10 ** (5 * (x - 1)), 0, 1) * max(sign(x), 0)
f = shape * max_release_hz
u = max(sign(sample_rate / 2 - f), 0)
k = u * clip(1 - exp(-2 * pi * f / sample_rate), 0, 1) + (1 - u)
env = env + k * (0 - env)
