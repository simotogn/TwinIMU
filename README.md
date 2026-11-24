# TwinIMU: a synchronized low-cost and high-grade IMU dataset for MEMS calibration

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24505924.svg)](https://doi.org/10.5281/zenodo.24505924)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

> **Where are the data?** The CSV files are archived on **Zenodo** (DOI above), not in this repository. This
> repository contains the documentation, the metadata and the processing script.

## Download

1. Download from Zenodo (https://doi.org/10.5281/zenodo.24505924) one or both archives:
   - `TwinIMU_v1.0_raw.zip` (70 MB): synchronized raw outputs of the two IMUs (`raw/`);
   - `TwinIMU_v1.0_processed.zip` (114 MB): data prepared as in the paper (`processed/`).
2. Unzip them. Each archive also contains this README, the license, the metadata and `process_dataset.py`.
3. To rebuild `processed/` from `raw/`, or to change the processing (for example without the low-pass filter):

   ```
   pip install numpy pandas scipy
   python process_dataset.py
   ```

   Run it from the `TwinIMU/` folder created by the archive, or copy `process_dataset.py` next to the `raw/` folder.

This repository mirrors the documentation of the archives: `README.md` (this file), `process_dataset.py`,
`metadata/recordings.csv`, `docs/box_cutaway.png`, `LICENSE` and `CITATION.cff`.

---

**TwinIMU** contains accelerometer, gyroscope and temperature data of a **low-cost MEMS IMU (STMicroelectronics LSM6DSO16IS)** recorded
together with a **high-grade reference IMU (Xsens MTi-630)**. Both devices are rigidly mounted in the same box, and
their samples are synchronized one by one. The name refers to this pairing: every recording of the low-cost
sensor comes with the "twin" recording of a high-grade reference that underwent exactly the same motion.

- 16 recordings, **262 min**, **1 673 862 synchronized samples** at about 106.5 Hz
- static, quasi-static and dynamic scenarios: cold starts, rest, multi-position, hand rotations, car driving,
  walking, stair climbing and a mixed sequence
- two versions of the same data:
  - **`raw/`**: the outputs of the two devices, synchronized in time and nothing else (no calibration, no offset, no
    filtering, no alignment);
  - **`processed/`**: the same samples, aligned and prepared exactly as in the paper, ready to be used as input and
    target of a calibration model (for example a neural network);
- **`process_dataset.py`**: the script that produces `processed/` from `raw/`, so every step is transparent and can be
  changed.

The dataset was collected for, and is described in, the paper listed under [How to cite](#how-to-cite). It is meant for
research on IMU calibration (offline, online or in-sensor), error modelling, sensor fusion and time-series learning.

---

## 1. Contents of the archive

```
TwinIMU/
├── README.md                  this file
├── LICENSE                    CC BY 4.0
├── CITATION.cff               citation metadata (used by GitHub and Zenodo)
├── process_dataset.py         builds processed/ from raw/ (Python, numpy + pandas + scipy)
├── raw/                       16 CSV files, one per recording: synchronized device outputs
│   ├── cold_01.csv
│   ├── ...
│   └── mixed_01.csv
├── processed/                 16 CSV files, same names: aligned input x, reference y and error e = y - x
│   ├── cold_01.csv
│   ├── ...
│   └── mixed_01.csv
├── metadata/
│   └── recordings.csv         one row per recording: scenario, duration, temperatures, synchronization quality
└── docs/
    └── box_cutaway.png        drawing of the acquisition box with sensor positions and axes
```

Both `raw/` and `processed/` files have exactly the same rows (one per LSM6DSO16IS sample) in the same order, so they
can be joined row by row.

All files are comma-separated text with a header row. Decimal separator: point. Missing values: none.

---

## 2. Raw data (`raw/*.csv`)

| Column | Unit | Description |
|---|---|---|
| `time` | s | Time of the LSM6DSO16IS sample, measured by the host board timer (1 MHz), starting from 0 at the first sample of the file |
| `lsm_acc_x`, `lsm_acc_y`, `lsm_acc_z` | m/s² | LSM6DSO16IS accelerometer, **in the LSM6DSO16IS frame** |
| `lsm_gyr_x`, `lsm_gyr_y`, `lsm_gyr_z` | rad/s | LSM6DSO16IS gyroscope, **in the LSM6DSO16IS frame** |
| `lsm_temp` | °C | LSM6DSO16IS internal temperature sensor |
| `mti_acc_x`, `mti_acc_y`, `mti_acc_z` | m/s² | MTi-630 acceleration, **in the MTi-630 frame**, at the MTi-630 position |
| `mti_gyr_x`, `mti_gyr_y`, `mti_gyr_z` | rad/s | MTi-630 rate of turn, **in the MTi-630 frame** |
| `mti_temp` | °C | MTi-630 internal temperature |
| `excluded_in_paper` | 0/1 | 1 if the sample was excluded from all metrics in the paper (see Section 7) |

**Sign convention:** both devices report specific force, so a device at rest with its z axis pointing up reads about
+9.81 m/s² on z.

### How the LSM6DSO16IS values were obtained

The sensor runs a minimal program on its Intelligent Sensor Processing Unit (ISPU). At every sample this program
multiplies the raw 16-bit output by the **nominal** sensitivity from the datasheet. No other correction is applied.

| Setting | Value |
|---|---|
| Output data rate | 104 Hz nominal (106.47 Hz measured with the host timer) |
| Accelerometer | ±8 g, high-performance mode, 0.244 mg/LSB → `acc [m/s²] = LSB × 0.0023928226` |
| Gyroscope | ±2000 dps, high-performance mode, 70 mdps/LSB → `gyr [rad/s] = LSB × 0.0012217305` |
| Temperature | `T [°C] = 25 + LSB / 256` |

The original integer outputs can therefore be recovered by dividing by the sensitivities above, apart from the
rounding to 6 decimals.

### How the MTi-630 values were obtained

The MTi-630 was recorded at 400 Hz with the Xsens MT Manager software. Its outputs are the calibrated acceleration and
rate of turn produced by the device itself, which is factory calibrated over temperature by the manufacturer. The
onboard filter profile was the magnetometer-aided one in `cold_01`, `pose_01` and `static_01`, and the VRU (vertical
reference unit) profile in all the other recordings. This changes only the internal attitude filter: the acceleration
and rate of turn stored here are the device outputs in both cases.

---

## 3. Synchronization (the only processing in `raw/`)

The two devices have independent clocks and different sampling rates. The MTi-630 signals were brought onto the time
base of the LSM6DSO16IS as follows.

1. **Hardware pulse.** The host board generates a pulse every second. It timestamps the pulse with the same timer it
   uses for the LSM6DSO16IS samples, and the pulse also enters the external synchronization input of the MTi-630, which
   marks it in its data stream.
2. **Clock model.** The paired pulses are fitted with an affine model `t_MTi = a · t_host + b`, which accounts for
   clock drift and offset. Over all recordings the drift is 6.9–8.4 ppm and the fit residual is about 0.72 ms rms,
   which is the quantization of the 400 Hz MTi grid. The values for each recording are in `metadata/recordings.csv`.
3. **Resampling.** The MTi-630 channels are linearly interpolated at the time of each LSM6DSO16IS sample. There is no
   extrapolation, and no interpolation across gaps longer than 20 ms.
4. **Latency.** The internal filters of the two devices delay their outputs differently. To compensate, the MTi-630
   accelerometer is evaluated 5.5 ms earlier and the MTi-630 gyroscope by the per-recording value `latency_gyr_ms`
   (about 9.7 ms, estimated by cross-correlation; 10 ms by default where there is too little rotation).

In `raw/`, both devices are left in their own frames and at their own positions.

---

## 4. Geometry: frames and lever arm

The two sensors are fixed in a 3D-printed box (see `docs/box_cutaway.png`); their relative pose never changes.

- **Rotation:** the LSM6DSO16IS is rotated by 180° about the vertical z axis with respect to the MTi-630. To express
  the LSM6DSO16IS data in the MTi-630 frame:

  ```
  x_MTi = -x_LSM      y_MTi = -y_LSM      z_MTi = z_LSM
  ```

  A small residual misalignment of about 1.5° remains. It is part of the error that a calibration must learn.

- **Lever arm:** the LSM6DSO16IS is at **r = (4.67, 5.12, 62.65) mm** from the MTi-630, in the MTi-630 frame. This
  is the value used in the paper, rounded there to (4.7, 5.1, 62.7) mm. When the box rotates, the LSM6DSO16IS measures
  the additional acceleration

  ```
  Δa = α × r + ω × (ω × r)
  ```

  where ω is the angular rate (rad/s) and α = dω/dt. The rate of turn is the same at every point of a rigid body and
  needs no correction.

---

## 5. Processed data (`processed/*.csv`)

These files contain, for every sample, the **input** of a calibration model (the low-cost sensor), its **target** (the
reference), and their **difference** (the error to be learned). They are exactly the data used in the paper.

| Column | Unit | Description |
|---|---|---|
| `time` | s | Same as in `raw/` |
| `x_acc_x`, `x_acc_y`, `x_acc_z` | m/s² | LSM6DSO16IS accelerometer, raw, rotated into the MTi-630 frame |
| `x_gyr_x`, `x_gyr_y`, `x_gyr_z` | °/s | LSM6DSO16IS gyroscope, raw, rotated into the MTi-630 frame |
| `y_acc_x`, `y_acc_y`, `y_acc_z` | m/s² | Reference acceleration at the LSM6DSO16IS position (MTi-630 + lever arm), low-pass filtered |
| `y_gyr_x`, `y_gyr_y`, `y_gyr_z` | °/s | Reference rate of turn (MTi-630), low-pass filtered, MTi bias removed |
| `e_acc_x`, `e_acc_y`, `e_acc_z` | m/s² | Accelerometer error, `e = y - x` |
| `e_gyr_x`, `e_gyr_y`, `e_gyr_z` | °/s | Gyroscope error, `e = y - x` |
| `lsm_temp` | °C | LSM6DSO16IS internal temperature (as in `raw/`) |
| `excluded_in_paper` | 0/1 | Same flag as in `raw/`, recomputed by the script |

A calibration model takes `x` (and optionally `lsm_temp`) and predicts `e`; the corrected output is
`x + e_predicted`, and it should match `y`. **`x` is not calibrated in any way.** It is the raw sensor output with
only the axes changed. The **gyroscopes are in °/s** in `processed/`, while they are in rad/s in `raw/`.

### Processing steps (`process_dataset.py`)

1. **Rotation.** The x and y axes of the LSM6DSO16IS change sign (180° about z), so that `x` is in the MTi-630
   frame.
2. **Lever arm.** `Δa = α × r + ω × (ω × r)` is added to the MTi-630 acceleration, with r from Section 4. ω is the
   MTi-630 rate, and α is its time derivative after a 3-sample centered moving average.
3. **Units.** Both gyroscopes are converted from rad/s to °/s.
4. **Low-pass filter on the reference.** A 25 Hz, 2nd-order Butterworth filter is applied forward and backward (zero
   phase) to both reference signals, with a sample rate of 106.47 Hz. At rest the MTi-630 rate of turn has a white
   noise of 0.1–0.3 °/s rms, much higher than that of the LSM6DSO16IS; without filtering, the error metrics would
   mostly measure the noise of the reference. The low-cost sensor is not filtered.
5. **Bias of the reference gyroscope.** The MTi-630 rate of turn has a slowly varying bias of 0.1–0.7 °/s. It is
   estimated as follows and subtracted:
   - the periods at rest are detected: the 1 s mean of the reference rate norm stays below 1.5 °/s for at least 5 s;
   - the reference rate is averaged over blocks of about 30 s within each period at rest, dropping 1 s at both ends;
   - the block averages are interpolated linearly in time.
6. **Error.** `e = y - x` for both sensors.
7. **Excluded samples.** A sample is flagged if it is within 2 s of a jump of the acceleration norm larger than
   5 m/s² between consecutive samples, in either the low-cost or the reference accelerometer.

The constants are at the top of the script and can be changed. To regenerate the folder:

```
python process_dataset.py                  # all recordings
python process_dataset.py car_02 rot_02    # only some recordings
python process_dataset.py --no-filter      # same steps, without the low-pass filter on the reference
```

The script was checked against the code used for the paper. It selects exactly the same samples, and the error
signals differ by at most 2.5·10⁻⁴ m/s² and 5·10⁻⁷ °/s. These are rounding differences from the 6 decimals of the raw
files, about ten times smaller than one LSB of the accelerometer.

---

## 6. Recordings (`metadata/recordings.csv`)

Every recording starts and ends with at least 60 s at rest. Before the cold-start recordings the LSM6DSO16IS was
unpowered for at least one hour, while the MTi-630 was already at thermal steady state.

| Recording | Scenario | Set in paper | Date | Duration [s] | Samples | LSM temp. [°C] | Gyro latency [ms] |
|---|---|---|---|---|---|---|---|
| cold_01 | cold start | tuning | 2026-11-06 | 1560 | 166104 | 20.5–23.5 | 10.00 |
| static_01 | static | tuning | 2026-11-06 | 958 | 101955 | 24.7–25.1 | 10.00 |
| pose_01 | multi-position | tuning | 2026-11-06 | 401 | 42747 | 24.5–24.9 | 9.87 |
| rot_01 | rotations | tuning | 2026-11-09 | 360 | 38326 | 26.2–26.6 | 9.65 |
| car_01 | car | tuning | 2026-11-09 | 1500 | 159722 | 19.5–24.4 | 10.00 |
| walk_01 | walking | tuning | 2026-11-09 | 720 | 76651 | 26.6–26.8 | 9.68 |
| cold_02 | cold start | test | 2026-11-06 | 1560 | 166099 | 21.7–24.2 | 10.00 |
| cold_03 | cold start | test | 2026-11-09 | 1560 | 166092 | 23.1–26.0 | 10.00 |
| pose_02 | multi-position | test | 2026-11-06 | 426 | 45325 | 24.7–25.1 | 10.00 |
| pose_03 | multi-position | test | 2026-11-09 | 600 | 63879 | 25.8–26.4 | 8.24 |
| rot_02 | rotations | test | 2026-11-09 | 390 | 41524 | 23.0–24.5 | 9.67 |
| car_02 | car | test | 2026-11-09 | 1421 | 151349 | 18.8–19.9 | 10.00 |
| walk_02 | walking | test | 2026-11-09 | 720 | 76653 | 26.8–27.0 | 9.71 |
| stairs_01 | stairs | test | 2026-11-12 | 660 | 70269 | 22.9–25.0 | 9.81 |
| stairs_02 | stairs | test | 2026-11-12 | 956 | 101783 | 21.8–24.9 | 9.75 |
| mixed_01 | mixed | test | 2026-11-13 | 1929 | 205384 | 24.2–26.1 | 9.71 |

Scenarios:

- **cold start:** box at rest with z up, from power-on of the LSM6DSO16IS; it captures the warm-up.
- **static:** box at rest at thermal steady state.
- **multi-position:** box placed on five of its faces for 60–100 s each, with slow rotations between them.
- **rotations:** rotations by hand about each axis, then free rotations (up to about 580 °/s in `rot_02`).
- **car:** urban and extra-urban driving with the box fixed in the car.
- **walking:** normal and fast walking with the box held in different ways.
- **stairs:** repeated ascents and descents of an indoor flight and of a five-floor building.
- **mixed:** a 32 min sequence alternating rest, rotations and walking.

The *Set in paper* column gives the split used in the paper: hyperparameters and offline models were selected and
trained on the `tuning` recordings, and results were reported on the `test` recordings.

Other columns of `metadata/recordings.csv`:

- `mean_rate_hz`
- `mti_temp_available`
- `excluded_in_paper_samples`
- `clock_drift_ppm`
- `sync_residual_rms_ms`
- `sync_pulses_matched`
- `latency_acc_ms`
- `latency_gyr_ms`

---

## 7. Things to know before using the data

- **Excluded samples.** Some recordings start or end with a few short taps on the box, used as visual markers. In the
  paper, every sample within 2 s of a jump of the acceleration norm larger than 5 m/s² between consecutive samples was
  excluded from the metrics. This removes the taps and, in car driving and walking, also a few strong shocks. These
  samples are flagged by `excluded_in_paper = 1`, but they are kept in all files.
- **The reference defines the achievable accuracy.** After the processing of Section 5, what remains between `x` and
  `y` also includes the residual noise, bias and dynamic mismatch of the reference itself. At rest the residual
  gyroscope error is about 0.12 °/s, which is the noise level of the filtered MTi-630 rate.
- **Raw errors of the LSM6DSO16IS (processed data, samples not excluded).**
  - Gyroscope: the error is dominated by a stable bias of a few °/s. The mean absolute error is about 2.5–2.9 °/s.
  - Accelerometer: offsets, scale-factor errors and cross-axis terms; the measured gravity norm changes with the pose
    by about 4%. The mean absolute error is about 0.10–0.17 m/s².
- **Temperatures.** `lsm_temp` is the internal temperature of the low-cost sensor (18.8–27.0 °C over the dataset).
  `mti_temp` is the internal temperature of the MTi-630 (about 30–38 °C).
- **Saturation.** No channel saturates. The largest values are about 55 m/s² (stairs, foot impact) and 580 °/s (fast
  rotations).
- **Recording boundaries.** Samples are contiguous within a file. Do not concatenate different recordings as if they
  were one time series: the sensor was power-cycled and moved between them.

---

## 8. Minimal example (Python)

```python
import numpy as np
import pandas as pd

d = pd.read_csv("processed/rot_02.csv")
d = d[d.excluded_in_paper == 0]                       # same samples as the paper

X = d[["x_gyr_x", "x_gyr_y", "x_gyr_z"]].to_numpy()  # input: raw gyroscope, deg/s
E = d[["e_gyr_x", "e_gyr_y", "e_gyr_z"]].to_numpy()  # target: error to be learned, deg/s
T = d["lsm_temp"].to_numpy()                         # optional input: temperature

print("raw MAE gyro [deg/s]:", np.abs(E).mean())      # error of the uncalibrated sensor

# a simple baseline: static offset, i.e. the mean error of the first 60 s (at rest), applied to the rest
fit = d.time < 60
offset = E[fit].mean(0)
print("MAE with static offset [deg/s]:", np.abs(E[~fit] - offset).mean())
```

Note that the first 60 s of each recording are at rest. A full affine model (scale factors and cross-axis terms)
cannot be estimated from them, because a single static pose does not excite all the axes. This is the problem
addressed by the online models of the paper.

---

## 9. Hardware

| Item | Details |
|---|---|
| Device under test | STMicroelectronics LSM6DSO16IS (3-axis accelerometer, 3-axis gyroscope, ISPU) on a STEVAL-MKI229A adapter, plugged into an X-NUCLEO expansion board on an STM32 Nucleo-F401RE |
| Host | STM32 Nucleo-F401RE: reads the ISPU outputs over I²C at 400 kHz on every ISPU interrupt, timestamps them with a 32-bit 1 MHz timer, generates the 1 Hz synchronization pulse, streams over UART to a PC |
| Reference | Xsens MTi-630 on its development kit, 400 Hz, external synchronization input connected to the host pulse |
| Mounting | 3D-printed box. The MTi-630 is on the base, and the Nucleo stack is on a shelf 32 mm above it. Boards are glued and cables fixed |

---

## How to cite

If you use TwinIMU, please cite the dataset and the paper:

> S. Tognocchi, D. P. Pau, M. Marcon, "TwinIMU: a synchronized low-cost and high-grade IMU dataset for MEMS
> calibration", Zenodo, 2026, doi: 10.5281/zenodo.24505924 (all versions; version 1.0.0: 10.5281/zenodo.24505925).

> S. Tognocchi, D. P. Pau, M. Marcon, "Learning to Match a Reference: Online In-Sensor Calibration of Low-Cost
> MEMS-IMUs on the ISPU", *Electronics* (MDPI), submitted, 2026.

The paper citation will be updated with volume, pages and DOI after publication.

## License

This dataset is released under the Creative Commons Attribution 4.0 International license (CC BY 4.0). You may use,
share and adapt it for any purpose, provided that you cite the dataset and the paper above.
See the `LICENSE` file.
