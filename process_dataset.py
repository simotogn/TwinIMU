"""
process_dataset.py - builds the processed/ folder from the raw/ folder of the TwinIMU dataset (LSM6DSO16IS + Xsens MTi-630).

It reproduces exactly the preprocessing used in the paper:
  1. LSM6DSO16IS axes rotated into the MTi-630 frame (180 deg about z: x and y change sign);
  2. MTi-630 acceleration transported to the LSM6DSO16IS position (lever arm r, rigid-body kinematics);
  3. gyroscopes converted from rad/s to deg/s;
  4. slowly varying bias of the MTi-630 rate of turn estimated in the periods at rest and subtracted;
  5. both reference signals low-pass filtered at 25 Hz (2nd-order Butterworth, zero phase);
  6. error to be learned by a calibration: e = y - x (reference minus low-cost sensor);
  7. flag of the samples excluded from the metrics in the paper (taps and strong shocks).
No calibration of the LSM6DSO16IS is applied: x is still the raw sensor output, only rotated.

Requirements: Python 3.8+, numpy, pandas, scipy.
Usage (from the dataset folder):
    python process_dataset.py                    # all recordings
    python process_dataset.py car_02 rot_02      # only some recordings
    python process_dataset.py --no-filter        # same, without the 25 Hz low-pass filter on the reference
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt

HERE = Path(__file__).resolve().parent
RAW, PROCESSED = HERE / "raw", HERE / "processed"

# ------------------------------------------------------------------------------------------------ parameters
SIGN = np.array([-1.0, -1.0, 1.0])     # LSM6DSO16IS -> MTi-630 frame (180 deg about z)
R_LEVER = np.array([0.004669878, 0.005124849, 0.062653020])  # LSM position w.r.t. MTi, MTi frame [m]
LEVER_SMOOTH = 3                       # moving average (samples) on the MTi rate before differentiating
FS = 106.47                            # measured sample rate of the LSM6DSO16IS [Hz]
REF_FC = 25.0                          # cut-off of the low-pass filter on the reference [Hz]
CALM_DPS = 1.5                         # at rest: 1 s mean of the reference rate norm below 1.5 deg/s ...
CALM_MIN_S = 5.0                       # ... for at least 5 s
BIAS_BLOCK_S = 30.0                    # one MTi gyro bias estimate every 30 s at rest
EVENT_THR = 5.0                        # jump of the acceleration norm between samples [m/s^2] = tap / shock
EVENT_PAD_S = 2.0                      # samples within 2 s of an event are excluded

AX = ["x", "y", "z"]


def skew(v):
    z = np.zeros(len(v))
    return np.stack([np.stack([z, -v[:, 2], v[:, 1]], 1),
                     np.stack([v[:, 2], z, -v[:, 0]], 1),
                     np.stack([-v[:, 1], v[:, 0], z], 1)], 1)


def lever_arm(t, w):
    """Additional acceleration at the LSM6DSO16IS position: alpha x r + w x (w x r), w in rad/s (MTi frame)."""
    ws = pd.DataFrame(w).rolling(LEVER_SMOOTH, center=True, min_periods=1).mean().to_numpy()
    alpha = np.gradient(ws, t, axis=0)
    return np.einsum("nij,j->ni", skew(alpha) + skew(w) @ skew(w), R_LEVER)


def calm_mask(w_norm_dps):
    wm = pd.Series(w_norm_dps).rolling(int(FS), center=True, min_periods=1).mean()
    return (wm < CALM_DPS).rolling(int(CALM_MIN_S * FS), center=True, min_periods=1).min().astype(bool).to_numpy()


def mti_gyro_bias(t, g, calm):
    """Bias of the MTi rate of turn: mean over 30 s blocks of the periods at rest, interpolated in time."""
    idx = np.flatnonzero(calm)
    if len(idx) == 0:
        return np.zeros_like(g)
    tc, bc = [], []
    for seg in np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1):
        trim = int(FS)                                   # 1 s removed at both ends of each rest period
        seg = seg[trim:-trim] if len(seg) > 3 * trim else seg
        nb = max(1, int(round((t[seg[-1]] - t[seg[0]]) / BIAS_BLOCK_S)))
        for blk in np.array_split(seg, nb):
            tc.append(t[blk].mean())
            bc.append(g[blk].mean(0))
    tc, bc = np.array(tc), np.array(bc)
    return np.column_stack([np.interp(t, tc, bc[:, j]) for j in range(3)])


def process(name, use_filter=True):
    d = pd.read_csv(RAW / f"{name}.csv")
    t = d["time"].to_numpy()
    acc_lsm = d[[f"lsm_acc_{a}" for a in AX]].to_numpy() * SIGN                     # m/s^2, MTi frame
    gyr_lsm = np.degrees(d[[f"lsm_gyr_{a}" for a in AX]].to_numpy() * SIGN)         # deg/s, MTi frame
    w_mti = d[[f"mti_gyr_{a}" for a in AX]].to_numpy()                              # rad/s
    acc_ref = d[[f"mti_acc_{a}" for a in AX]].to_numpy() + lever_arm(t, w_mti)      # m/s^2 at LSM position
    gyr_ref = np.degrees(w_mti)                                                     # deg/s
    if use_filter:
        b, a = butter(2, REF_FC / (FS / 2))
        gyr_ref = filtfilt(b, a, gyr_ref, axis=0)
        acc_ref = filtfilt(b, a, acc_ref, axis=0)
    gyr_ref = gyr_ref - mti_gyro_bias(t, gyr_ref, calm_mask(np.linalg.norm(gyr_ref, axis=1)))
    # samples excluded in the paper: jumps of the acceleration norm (taps, strong shocks) +- 2 s
    excl = np.zeros(len(d), bool)
    pad = int(EVENT_PAD_S * FS)
    for acc in (acc_lsm, acc_ref):
        n = np.linalg.norm(acc, axis=1)
        ev = np.abs(np.diff(n, prepend=n[0])) > EVENT_THR
        excl |= np.convolve(ev, np.ones(2 * pad + 1), mode="same") > 0
    out = pd.DataFrame({"time": t})
    for k, a in enumerate(AX):
        out[f"x_acc_{a}"] = acc_lsm[:, k]
    for k, a in enumerate(AX):
        out[f"x_gyr_{a}"] = gyr_lsm[:, k]
    for k, a in enumerate(AX):
        out[f"y_acc_{a}"] = acc_ref[:, k]
    for k, a in enumerate(AX):
        out[f"y_gyr_{a}"] = gyr_ref[:, k]
    for k, a in enumerate(AX):
        out[f"e_acc_{a}"] = acc_ref[:, k] - acc_lsm[:, k]
    for k, a in enumerate(AX):
        out[f"e_gyr_{a}"] = gyr_ref[:, k] - gyr_lsm[:, k]
    out["lsm_temp"] = d["lsm_temp"]
    out["excluded_in_paper"] = excl.astype(int)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recordings", nargs="*", help="recording names (default: all files in raw/)")
    ap.add_argument("--no-filter", action="store_true", help="do not low-pass filter the reference")
    args = ap.parse_args()
    names = args.recordings or sorted(p.stem for p in RAW.glob("*.csv"))
    PROCESSED.mkdir(exist_ok=True)
    for name in names:
        out = process(name, use_filter=not args.no_filter)
        out.to_csv(PROCESSED / f"{name}.csv", index=False, float_format="%.6f")
        ok = out.excluded_in_paper == 0
        mae_a = out.loc[ok, ["e_acc_x", "e_acc_y", "e_acc_z"]].abs().to_numpy().mean()
        mae_g = out.loc[ok, ["e_gyr_x", "e_gyr_y", "e_gyr_z"]].abs().to_numpy().mean()
        print(f"{name:10s} {len(out):7d} samples   raw MAE acc {mae_a:.4f} m/s^2   gyro {mae_g:.3f} deg/s")


if __name__ == "__main__":
    main()
