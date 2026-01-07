from smoothing import ExponentialMovingAverage

ear_ema = ExponentialMovingAverage(alpha=0.3)

ear_values = [0.32, 0.31, 0.30, 0.15, 0.14, 0.29]

for ear in ear_values:
    smooth_ear = ear_ema.update(ear)
    print(f"EAR raw: {ear:.2f} | EAR EMA: {smooth_ear:.2f}")
