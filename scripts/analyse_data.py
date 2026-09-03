from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.stats import wasserstein_distance
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
)
from sklearn.model_selection import train_test_split


def _spectrum_cols(df, drop_dc=True):
    cols = sorted(
        [c for c in df.columns if c.startswith("Wert")],
        key=lambda x: int(x.replace("Wert", "").replace("*", "")),
    )
    # Wert1 is the DC bin, constant 0 in this dataset — drop it, it only
    # distorts dB conversion (log(0)) and adds a meaningless spike at f=0.
    return cols[1:] if drop_dc and cols else cols


def _frequencies_for_cols(cols, frequency_resolution_hz):
    bin_numbers = np.array([int(c.replace("Wert", "").replace("*", "")) for c in cols])
    return (bin_numbers - 1) * frequency_resolution_hz


def _apply_max_frequency(cols, freqs, max_frequency_hz):
    if max_frequency_hz is None:
        return cols, freqs
    keep = freqs <= max_frequency_hz
    return list(np.array(cols)[keep]), freqs[keep]


def to_db(values, floor=1e-12):
    return 20 * np.log10(np.maximum(values, floor))


def _sample_rows(arr, max_samples, rng):
    if max_samples is None or len(arr) <= max_samples:
        return arr
    idx = rng.choice(len(arr), max_samples, replace=False)
    return arr[idx]


def _sensor_baseline_db(sub, cols, sensor_col="sensor", workstep_col="workstep", baseline_workstep=3):
    """Per-sensor baseline dB spectrum, taken as the mean spectrum at
    baseline_workstep (the warmup/idle step) — subtract this from a sensor's
    other spectra to remove what's always there and reveal what changes."""

    baseline_rows = sub[sub[workstep_col] == baseline_workstep]
    return {
        sensor: to_db(grp[cols].to_numpy(dtype=float)).mean(axis=0)
        for sensor, grp in baseline_rows.groupby(sensor_col)
    }


def _group_mean_spectra(sub, group_cols, cols):
    group_cols = list(group_cols)
    labels, keys, mean_spectra = [], [], []
    for key, grp in sub.groupby(group_cols):
        key = key if isinstance(key, tuple) else (key,)
        labels.append("-".join(f"{c}{v}" for c, v in zip(group_cols, key)))
        keys.append(key)
        mean_spectra.append(to_db(grp[cols].to_numpy(dtype=float)).mean(axis=0))
    return labels, keys, np.array(mean_spectra)


def compute_shape_anomaly_scores(
    df,
    group_cols=("sensor", "workstep"),
    frequency_resolution_hz=6.103515625,
    max_frequency_hz=None,
    top_pct=1.0,
    threshold_method="percentile",
    n_std=3.0,
):
    """Per-trial Wasserstein distance from its own sensor+workstep group's
    mean spectrum, used as a 'weird shape' anomaly score. Flags divergent
    trials per group with label=1 (else 0), by one of two methods:

    threshold_method="percentile" (default): top_pct percent most divergent
    trials per group (rank-based, always flags something).
    threshold_method="std": trials more than n_std standard deviations above
    the group's own mean distance (statistical outlier, per group — may flag
    nothing at all if a group's distances are tightly clustered).

    Returns a copy of the FFT rows with three added columns: shape_distance,
    shape_distance_threshold (per-group), label (int 0/1).
    """

    sub = df[df["measurement_type"] == "FFT"].copy()
    cols = _spectrum_cols(sub)
    freqs = _frequencies_for_cols(cols, frequency_resolution_hz)
    cols, freqs = _apply_max_frequency(cols, freqs, max_frequency_hz)

    sub["shape_distance"] = np.nan
    sub["shape_distance_threshold"] = np.nan
    sub["label"] = 0

    for _, group in sub.groupby(list(group_cols)):
        db = to_db(group[cols].to_numpy(dtype=float))
        mean_db = db.mean(axis=0)

        shift = min(db.min(), mean_db.min()) - 1e-6
        mean_weight = mean_db - shift

        distances = np.array(
            [wasserstein_distance(freqs, freqs, row - shift, mean_weight) for row in db]
        )

        if threshold_method == "percentile":
            threshold = np.percentile(distances, 100 - top_pct)
        elif threshold_method == "std":
            threshold = distances.mean() + n_std * distances.std()
        else:
            raise ValueError(f"Unknown threshold_method: {threshold_method!r} (use 'percentile' or 'std')")

        sub.loc[group.index, "shape_distance"] = distances
        sub.loc[group.index, "shape_distance_threshold"] = threshold
        sub.loc[group.index, "label"] = (distances >= threshold).astype(int)

    return sub


def detect_harmonics(freqs, mean_db, min_prominence_db=6, max_candidates=8, tolerance_frac=0.03):
    """Find peaks in a mean dB spectrum and classify them against a fitted
    fundamental f0: harmonic (matches n*f0) vs. non-harmonic/anomalous.

    Returns (f0, peaks) where peaks is a list of dicts with
    freq, amplitude_db, harmonic_order (None if non-harmonic).
    """

    bin_width = freqs[1] - freqs[0]
    peak_idx, props = find_peaks(mean_db, prominence=min_prominence_db)

    if len(peak_idx) == 0:
        return None, []

    peak_freqs = freqs[peak_idx]
    peak_heights = mean_db[peak_idx]

    candidate_order = np.argsort(peak_freqs)[:max_candidates]

    best_f0, best_score = None, -1
    for c in candidate_order:
        f0 = peak_freqs[c]
        if f0 <= 0:
            continue
        tolerance = max(2 * bin_width, tolerance_frac * f0)
        n = np.round(peak_freqs / f0)
        n = np.where(n < 1, 1, n)
        matched = np.abs(peak_freqs - n * f0) <= tolerance
        score = peak_heights[matched].clip(min=0).sum()
        if score > best_score:
            best_score, best_f0 = score, f0

    if best_f0 is None:
        return None, [
            {"freq": f, "amplitude_db": a, "harmonic_order": None}
            for f, a in zip(peak_freqs, peak_heights)
        ]

    tolerance = max(2 * bin_width, tolerance_frac * best_f0)
    peaks = []
    for f, a in zip(peak_freqs, peak_heights):
        n = max(1, round(f / best_f0))
        order = n if abs(f - n * best_f0) <= tolerance else None
        peaks.append({"freq": f, "amplitude_db": a, "harmonic_order": order})

    return best_f0, peaks


def plot_mean_spectra(
    df,
    group_cols=("sensor", "workstep"),
    error="std",
    frequency_resolution_hz=6.103515625,
    max_frequency_hz=None,
):
    """Mean dB spectrum ± std/SEM, one line per group_cols[0], faceted by group_cols[1]."""

    sub = df[df["measurement_type"] == "FFT"]
    cols = _spectrum_cols(sub)
    freqs = _frequencies_for_cols(cols, frequency_resolution_hz)
    cols, freqs = _apply_max_frequency(cols, freqs, max_frequency_hz)

    hue_col, facet_col = group_cols
    facets = sorted(sub[facet_col].unique())
    hues = sorted(sub[hue_col].unique())
    colors = plt.cm.tab10(np.linspace(0, 1, len(hues)))

    fig, axes = plt.subplots(
        1, len(facets), figsize=(5 * len(facets), 4), sharey=True, squeeze=False
    )
    axes = axes[0]

    for ax, facet_val in zip(axes, facets):
        facet_df = sub[sub[facet_col] == facet_val]
        for color, hue_val in zip(colors, hues):
            grp = facet_df[facet_df[hue_col] == hue_val]
            if grp.empty:
                continue
            db = to_db(grp[cols].to_numpy(dtype=float))
            mean = db.mean(axis=0)
            spread = db.std(axis=0)
            if error == "sem":
                spread = spread / np.sqrt(len(grp))
            ax.plot(
                freqs, mean, color=color, label=f"{hue_col}={hue_val} (n={len(grp)})"
            )
            ax.fill_between(freqs, mean - spread, mean + spread, color=color, alpha=0.2)
        ax.set_title(f"{facet_col}={facet_val}")
        ax.set_xlabel("Frequency [Hz]")

    axes[0].set_ylabel("Amplitude [dB]")
    axes[0].legend(fontsize=8)
    fig.suptitle(f"Mean spectra ± {error} by {hue_col}, faceted by {facet_col}")
    plt.tight_layout()
    plt.show()


def plot_individual_spectra(
    df,
    group_cols=("sensor", "workstep"),
    max_traces=200,
    frequency_resolution_hz=6.103515625,
    max_frequency_hz=None,
    random_state=0,
    subtract_baseline=False,
    baseline_workstep=3,
    highlight_col=None,
):
    """Grid of sensor x workstep panels, each showing a sample of individual
    dB spectra (thin, transparent) plus their mean (thick black) overlaid.

    subtract_baseline=True: subtract each sensor's own mean spectrum at
    baseline_workstep first — removes what's always there, reveals changes.

    highlight_col: name of a boolean/0-1 column in df — all rows where it's
    truthy are drawn in red on top of the sample, e.g. to visually confirm
    an anomaly label actually looks like the outliers in the pack.
    """

    sub = df[df["measurement_type"] == "FFT"]
    cols = _spectrum_cols(sub)
    freqs = _frequencies_for_cols(cols, frequency_resolution_hz)
    cols, freqs = _apply_max_frequency(cols, freqs, max_frequency_hz)

    hue_col, facet_col = group_cols
    sensors = sorted(sub[hue_col].unique())
    worksteps = sorted(sub[facet_col].unique())
    rng = np.random.default_rng(random_state)

    baselines = (
        _sensor_baseline_db(sub, cols, hue_col, facet_col, baseline_workstep)
        if subtract_baseline
        else None
    )

    fig, axes = plt.subplots(
        len(sensors),
        len(worksteps),
        figsize=(4 * len(worksteps), 3 * len(sensors)),
        sharex=True,
        sharey=True,
        squeeze=False,
        constrained_layout=True,
    )

    for row, sensor in enumerate(sensors):
        for col, ws in enumerate(worksteps):
            ax = axes[row][col]
            grp = sub[(sub[hue_col] == sensor) & (sub[facet_col] == ws)]

            if grp.empty:
                ax.set_title(f"{hue_col}={sensor}, {facet_col}={ws} — no data", fontsize=8)
                ax.axis("off")
                continue

            db = to_db(grp[cols].to_numpy(dtype=float))
            if baselines is not None:
                db = db - baselines[sensor]

            if highlight_col is None:
                sample = _sample_rows(db, max_traces, rng)
                ax.plot(freqs, sample.T, color="tab:blue", alpha=0.08, linewidth=0.5)
                title = f"{hue_col}={sensor}, {facet_col}={ws} (n={len(grp):,}, shown={len(sample):,})"
            else:
                flagged = grp[highlight_col].to_numpy().astype(bool)
                n_highlighted = int(flagged.sum())
                if n_highlighted:
                    ax.plot(freqs, db[flagged].T, color="red", alpha=0.5, linewidth=0.7)
                title = f"{hue_col}={sensor}, {facet_col}={ws} (n={len(grp):,}, flagged={n_highlighted:,})"

            ax.plot(freqs, db.mean(axis=0), color="black", linewidth=1.8)
            ax.set_title(title, fontsize=8)

            if row == len(sensors) - 1:
                ax.set_xlabel("Frequency [Hz]")
            if col == 0:
                ax.set_ylabel("Amplitude minus baseline [dB]" if baselines is not None else "Amplitude [dB]")

    title = "Individual spectra (sample) + mean, by sensor + workstep"
    if baselines is not None:
        title += f" (baseline = each sensor's workstep {baseline_workstep} mean)"
    fig.suptitle(title)
    plt.show()


def plot_anomaly_scores(scored_df, group_cols=("sensor", "workstep")):
    """Grid of sensor x workstep panels: shape_distance vs. time, colored by
    label (from compute_shape_anomaly_scores), with the per-group threshold
    marked — shows *when* anomalies cluster, not just that they exist."""

    hue_col, facet_col = group_cols
    sensors = sorted(scored_df[hue_col].unique())
    worksteps = sorted(scored_df[facet_col].unique())

    fig, axes = plt.subplots(
        len(sensors),
        len(worksteps),
        figsize=(4 * len(worksteps), 3 * len(sensors)),
        sharex=True,
        sharey=True,
        squeeze=False,
        constrained_layout=True,
    )

    for row, sensor in enumerate(sensors):
        for col, ws in enumerate(worksteps):
            ax = axes[row][col]
            grp = scored_df[(scored_df[hue_col] == sensor) & (scored_df[facet_col] == ws)]

            if grp.empty:
                ax.set_title(f"{hue_col}={sensor}, {facet_col}={ws} — no data", fontsize=8)
                ax.axis("off")
                continue

            flagged = grp["label"].to_numpy().astype(bool)
            ax.scatter(
                grp["Timestamp"][~flagged], grp["shape_distance"][~flagged],
                s=4, color="tab:blue", alpha=0.3, label="label=0",
            )
            ax.scatter(
                grp["Timestamp"][flagged], grp["shape_distance"][flagged],
                s=8, color="red", label="label=1",
            )
            ax.axhline(grp["shape_distance_threshold"].iloc[0], color="black", linestyle="--", linewidth=0.8)

            ax.set_title(
                f"{hue_col}={sensor}, {facet_col}={ws} (flagged={int(flagged.sum()):,}/{len(grp):,})",
                fontsize=8,
            )

            if row == len(sensors) - 1:
                ax.set_xlabel("Time")
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax.xaxis.set_major_formatter(
                    mdates.ConciseDateFormatter(ax.xaxis.get_major_locator())
                )
            if col == 0:
                ax.set_ylabel("Shape distance [Hz]")

    fig.suptitle("Anomaly score (Wasserstein distance to own group mean) over time")
    plt.show()


def plot_band_energy(
    df,
    n_bands=8,
    band_scale="linear",
    frequency_resolution_hz=6.103515625,
    max_frequency_hz=None,
    subtract_baseline=False,
    baseline_workstep=3,
):
    """Boxplot of per-spectrum mean band-dB, grouped by workstep (x position)
    with one box per sensor (color) within each group — one panel per band.

    band_scale="linear" (default): equal-Hz-width bands, so every panel
    averages roughly the same number of bins — fairer boxplot comparison.
    band_scale="log": geometrically growing bands (finer at low frequency),
    at the cost of very few bins (sometimes just 1) in the lowest bands.

    subtract_baseline=True: subtract each sensor's own mean spectrum at
    baseline_workstep first — removes what's always there, reveals changes.
    """

    sub = df[df["measurement_type"] == "FFT"]
    cols = _spectrum_cols(sub)
    freqs = _frequencies_for_cols(cols, frequency_resolution_hz)
    cols, freqs = _apply_max_frequency(cols, freqs, max_frequency_hz)

    if band_scale == "log":
        band_edges = np.logspace(
            np.log10(freqs[freqs > 0].min()), np.log10(freqs.max()), n_bands + 1
        )
        band_edges[0] = 0
    elif band_scale == "linear":
        band_edges = np.linspace(0, freqs.max(), n_bands + 1)
    else:
        raise ValueError(f"Unknown band_scale: {band_scale!r} (use 'linear' or 'log')")

    band_idx = np.clip(np.digitize(freqs, band_edges) - 1, 0, n_bands - 1)

    db_all = to_db(sub[cols].to_numpy(dtype=float))
    sensor_arr = sub["sensor"].to_numpy()
    workstep_arr = sub["workstep"].to_numpy()
    sensors = sorted(sub["sensor"].unique())
    worksteps = sorted(sub["workstep"].unique())
    colors = plt.cm.tab10(np.linspace(0, 1, len(sensors)))

    if subtract_baseline:
        baselines = _sensor_baseline_db(sub, cols, "sensor", "workstep", baseline_workstep)
        for sensor in sensors:
            db_all[sensor_arr == sensor] -= baselines[sensor]

    n_sensors = len(sensors)
    width = 0.8 / n_sensors

    fig, axes = plt.subplots(
        1, n_bands, figsize=(4 * n_bands, 4), sharey=True, squeeze=False
    )
    axes = axes[0]

    for band, ax in enumerate(axes):
        mask = band_idx == band
        band_energy = db_all[:, mask].mean(axis=1)
        for s_i, (sensor, color) in enumerate(zip(sensors, colors)):
            positions = [
                w_i + (s_i - (n_sensors - 1) / 2) * width for w_i in range(len(worksteps))
            ]
            data = [
                band_energy[(sensor_arr == sensor) & (workstep_arr == ws)]
                for ws in worksteps
            ]
            bp = ax.boxplot(
                data,
                positions=positions,
                widths=width * 0.9,
                showfliers=False,
                patch_artist=True,
            )
            for box in bp["boxes"]:
                box.set_facecolor(color)
            if band == 0:
                bp["boxes"][0].set_label(f"sensor {sensor}")
        ax.set_xticks(range(len(worksteps)))
        ax.set_xticklabels([str(w) for w in worksteps])
        lo, hi = band_edges[band], band_edges[band + 1]
        ax.set_title(f"{lo:.0f}-{hi:.0f} Hz")
        ax.set_xlabel("workstep")

    axes[0].set_ylabel("Mean band amplitude minus baseline [dB]" if subtract_baseline else "Mean band amplitude [dB]")
    axes[0].legend(fontsize=8)
    title = "Band energy distribution by sensor + workstep"
    if subtract_baseline:
        title += f" (baseline = each sensor's workstep {baseline_workstep} mean)"
    fig.suptitle(title)
    plt.tight_layout()
    plt.show()


def plot_connectivity_matrix(
    df,
    group_cols=("sensor", "workstep"),
    frequency_resolution_hz=6.103515625,
    max_frequency_hz=None,
    title=None,
):
    """Connectivity matrix: mean dB spectrum per sensor+workstep group, then
    pairwise Wasserstein distance between those mean spectra (treated as mass
    distributions over frequency) — visual grouping, no clustering algorithm."""

    sub = df[df["measurement_type"] == "FFT"]
    cols = _spectrum_cols(sub)
    freqs = _frequencies_for_cols(cols, frequency_resolution_hz)
    cols, freqs = _apply_max_frequency(cols, freqs, max_frequency_hz)

    labels, _, mean_spectra = _group_mean_spectra(sub, group_cols, cols)

    # wasserstein_distance needs non-negative weights — shift dB values above zero
    weights = mean_spectra - mean_spectra.min() + 1e-6

    n = len(labels)
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = wasserstein_distance(freqs, freqs, weights[i], weights[j])
            dist[i, j] = dist[j, i] = d

    fig, ax = plt.subplots(figsize=(0.6 * n + 3, 0.6 * n + 3))
    im = ax.imshow(dist, cmap="viridis")
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=7)
    fig.colorbar(im, ax=ax, label="Wasserstein distance [Hz]")
    ax.set_title(title or "Connectivity matrix — pairwise distance between group mean spectra")
    plt.tight_layout()
    plt.show()


def plot_harmonic_peaks(
    df,
    group_cols=("sensor", "workstep"),
    frequency_resolution_hz=6.103515625,
    max_frequency_hz=None,
    min_prominence_db=6,
    subtract_baseline=False,
    baseline_workstep=3,
):
    """Mean dB spectrum per sensor+workstep group, with detected peaks marked
    as harmonic (green, order labeled) or non-harmonic/anomalous (red x).

    subtract_baseline=True: subtract each sensor's own mean spectrum at
    baseline_workstep first — removes what's always there, reveals changes.
    """

    sub = df[df["measurement_type"] == "FFT"]
    cols = _spectrum_cols(sub)
    freqs = _frequencies_for_cols(cols, frequency_resolution_hz)
    cols, freqs = _apply_max_frequency(cols, freqs, max_frequency_hz)

    hue_col, facet_col = group_cols
    sensors = sorted(sub[hue_col].unique())
    worksteps = sorted(sub[facet_col].unique())

    baselines = (
        _sensor_baseline_db(sub, cols, hue_col, facet_col, baseline_workstep)
        if subtract_baseline
        else None
    )

    fig, axes = plt.subplots(
        len(sensors),
        len(worksteps),
        figsize=(4 * len(worksteps), 3 * len(sensors)),
        sharex=True,
        sharey=True,
        squeeze=False,
    )

    for row, sensor in enumerate(sensors):
        for col, ws in enumerate(worksteps):
            ax = axes[row][col]
            grp = sub[(sub[hue_col] == sensor) & (sub[facet_col] == ws)]
            if grp.empty:
                ax.axis("off")
                continue

            mean_db = to_db(grp[cols].to_numpy(dtype=float)).mean(axis=0)
            if baselines is not None:
                mean_db = mean_db - baselines[sensor]
            f0, peaks = detect_harmonics(freqs, mean_db, min_prominence_db=min_prominence_db)

            ax.plot(freqs, mean_db, color="black", linewidth=0.8)
            for p in peaks:
                if p["harmonic_order"] is not None:
                    ax.plot(p["freq"], p["amplitude_db"], "go")
                    ax.annotate(
                        str(p["harmonic_order"]),
                        (p["freq"], p["amplitude_db"]),
                        fontsize=6,
                        xytext=(0, 4),
                        textcoords="offset points",
                    )
                else:
                    ax.plot(p["freq"], p["amplitude_db"], "rx")

            title = f"{hue_col}={sensor}, {facet_col}={ws}"
            if f0 is not None:
                title += f" (f0≈{f0:.1f} Hz)"
            ax.set_title(title, fontsize=8)

            if row == len(sensors) - 1:
                ax.set_xlabel("Frequency [Hz]")
            if col == 0:
                ax.set_ylabel("Amplitude minus baseline [dB]" if baselines is not None else "Amplitude [dB]")

    title = "Detected harmonic (green) vs. non-harmonic (red) peaks"
    if baselines is not None:
        title += f" (baseline = each sensor's workstep {baseline_workstep} mean)"
    fig.suptitle(title)
    plt.tight_layout()
    plt.show()


def plot_harmonic_amplitudes(
    df,
    group_cols=("sensor", "workstep"),
    max_harmonics=10,
    frequency_resolution_hz=6.103515625,
    max_frequency_hz=None,
    min_prominence_db=6,
):
    """Amplitude at each harmonic order (1..max_harmonics) of each group's own
    fitted f0 — parallel lines mean 'same harmonics, different loudness'."""

    sub = df[df["measurement_type"] == "FFT"]
    cols = _spectrum_cols(sub)
    freqs = _frequencies_for_cols(cols, frequency_resolution_hz)
    cols, freqs = _apply_max_frequency(cols, freqs, max_frequency_hz)

    labels, keys, mean_spectra = _group_mean_spectra(sub, group_cols, cols)
    sensors = sorted(sub[group_cols[0]].unique())
    worksteps = sorted(sub[group_cols[1]].unique())
    color_cycle = ["black", "gray", "red", "orange"]
    colors = dict(zip(sensors, [color_cycle[i % len(color_cycle)] for i in range(len(sensors))]))
    linestyles = dict(zip(worksteps, ["-", "--", "-.", ":", (0, (1, 1))]))

    fig, ax = plt.subplots(figsize=(9, 6))

    for label, key, mean_db in zip(labels, keys, mean_spectra):
        f0, _ = detect_harmonics(freqs, mean_db, min_prominence_db=min_prominence_db)
        if f0 is None:
            continue
        orders = np.arange(1, max_harmonics + 1)
        in_range = orders * f0 <= freqs.max()
        bin_idx = np.round(orders[in_range] * f0 / (freqs[1] - freqs[0])).astype(int)
        sensor, ws = key
        ax.plot(
            orders[in_range],
            mean_db[bin_idx],
            color=colors[sensor],
            linestyle=linestyles.get(ws, "-"),
            label=label,
        )

    ax.set_xlabel("Harmonic order")
    ax.set_ylabel("Amplitude [dB]")
    ax.set_title("Harmonic amplitude by sensor + workstep (own fitted f0)")
    ax.legend(fontsize=7, ncol=2)
    plt.tight_layout()
    plt.show()


def _hz_to_mel(f):
    return 2595 * np.log10(1 + f / 700)


def _mel_to_hz(m):
    return 700 * (10 ** (m / 2595) - 1)


def _mel_filterbank(freqs, n_mels):
    """Triangular mel filterbank over an existing linear frequency axis.

    Returns (filterbank[n_mels, n_freqs], mel_center_hz[n_mels]). Filters
    with no linear bin inside them (mel spacing finer than the FFT's own
    resolution, typically at the very low end) come back all-zero.
    """

    mel_points = np.linspace(_hz_to_mel(freqs.min()), _hz_to_mel(freqs.max()), n_mels + 2)
    hz_points = _mel_to_hz(mel_points)

    filterbank = np.zeros((n_mels, len(freqs)))
    for m in range(n_mels):
        left, center, right = hz_points[m], hz_points[m + 1], hz_points[m + 2]
        rising = (freqs - left) / max(center - left, 1e-12)
        falling = (right - freqs) / max(right - center, 1e-12)
        filterbank[m] = np.clip(np.minimum(rising, falling), 0, None)

    row_sums = filterbank.sum(axis=1, keepdims=True)
    filterbank = np.divide(filterbank, row_sums, out=np.zeros_like(filterbank), where=row_sums > 0)

    return filterbank, hz_points[1:-1]


def _plot_time_frequency_grid(sub, group_cols, y_values, compute_Z, y_label, suptitle, use_db=True):
    """Shared grid-of-spectrograms renderer: rows=group_cols[0], cols=group_cols[1],
    one pcolormesh per non-empty combination, shared color scale and colorbar."""

    hue_col, facet_col = group_cols
    sensors = sorted(sub[hue_col].unique())
    worksteps = sorted(sub[facet_col].unique())

    panels = {}
    for sensor in sensors:
        for ws in worksteps:
            grp = sub[(sub[hue_col] == sensor) & (sub[facet_col] == ws)].sort_values("Timestamp")
            if grp.empty:
                continue
            panels[(sensor, ws)] = (grp["Timestamp"], compute_Z(grp))

    if not panels:
        raise ValueError("No data to plot.")

    all_values = np.concatenate([Z.ravel() for _, Z in panels.values()])
    vmin, vmax = np.nanpercentile(all_values, 1), np.nanpercentile(all_values, 99)

    fig, axes = plt.subplots(
        len(sensors),
        len(worksteps),
        figsize=(4 * len(worksteps), max(3.5 * len(sensors), 4.5)),
        sharex=True,
        sharey=True,
        squeeze=False,
        constrained_layout=True,
    )

    mesh = None

    for row, sensor in enumerate(sensors):
        for col, ws in enumerate(worksteps):
            ax = axes[row][col]
            key = (sensor, ws)

            if key not in panels:
                ax.set_title(f"{hue_col}={sensor}, {facet_col}={ws} — no data", fontsize=8)
                ax.axis("off")
                continue

            times, Z = panels[key]
            mesh = ax.pcolormesh(times, y_values, Z.T, shading="auto", vmin=vmin, vmax=vmax)
            ax.set_title(f"{hue_col}={sensor}, {facet_col}={ws} (n={len(Z):,})", fontsize=8)

            if row == len(sensors) - 1:
                ax.set_xlabel("Time")
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax.xaxis.set_major_formatter(
                    mdates.ConciseDateFormatter(ax.xaxis.get_major_locator())
                )
            if col == 0:
                ax.set_ylabel(y_label)

    if mesh is not None:
        fig.colorbar(
            mesh,
            ax=axes.ravel().tolist(),
            label="Amplitude [dB]" if use_db else "Amplitude [mG]",
        )

    fig.suptitle(suptitle, fontsize=16)
    plt.show()


def plot_spectrograms_by_group(
    df,
    alarmlevel=0,
    group_cols=("sensor", "workstep"),
    frequency_resolution_hz=6.103515625,
    max_frequency_hz=None,
    use_db=True,
):
    """Time-frequency heatmaps at a fixed Alarmlevel, faceted by sensor (rows)
    x workstep (cols) — empty panels mean no data was recorded at that
    Alarmlevel for that sensor+workstep (e.g. sensors without a configured
    alarm reference never report Alarmlevel 0)."""

    sub_all = df[df["measurement_type"] == "FFT"]
    cols = _spectrum_cols(sub_all)
    freqs = _frequencies_for_cols(cols, frequency_resolution_hz)
    cols, freqs = _apply_max_frequency(cols, freqs, max_frequency_hz)

    sub = sub_all[sub_all["Alarmlevel"] == alarmlevel]
    if sub.empty:
        raise ValueError(f"No data found at Alarmlevel={alarmlevel}.")

    def compute_Z(grp):
        Z = grp[cols].to_numpy(dtype=float)
        return to_db(Z) if use_db else Z

    _plot_time_frequency_grid(
        sub,
        group_cols,
        freqs,
        compute_Z,
        "Frequency [Hz]",
        f"Time-frequency behavior at Alarmlevel {alarmlevel}",
        use_db=use_db,
    )


def plot_spectrograms_by_group_mel(
    df,
    alarmlevel=0,
    group_cols=("sensor", "workstep"),
    n_mels=32,
    frequency_resolution_hz=6.103515625,
    max_frequency_hz=None,
):
    """Same content as plot_spectrograms_by_group, but the frequency axis is
    warped onto a Mel scale (triangular filterbank on the power spectrum,
    log energy) — expands low-frequency resolution, compresses high."""

    sub_all = df[df["measurement_type"] == "FFT"]
    cols = _spectrum_cols(sub_all)
    freqs = _frequencies_for_cols(cols, frequency_resolution_hz)
    cols, freqs = _apply_max_frequency(cols, freqs, max_frequency_hz)

    sub = sub_all[sub_all["Alarmlevel"] == alarmlevel]
    if sub.empty:
        raise ValueError(f"No data found at Alarmlevel={alarmlevel}.")

    filterbank, mel_center_hz = _mel_filterbank(freqs, n_mels)

    def compute_Z(grp):
        power = grp[cols].to_numpy(dtype=float) ** 2
        mel_energy = power @ filterbank.T
        return 10 * np.log10(np.maximum(mel_energy, 1e-12))

    _plot_time_frequency_grid(
        sub,
        group_cols,
        mel_center_hz,
        compute_Z,
        "Frequency [Hz] (Mel-scale)",
        f"Time-frequency behavior at Alarmlevel {alarmlevel} (Mel-scale, n_mels={n_mels})",
        use_db=True,
    )


def _causal_split_index(df, group_cols, test_size):
    """Time-ordered split per group: earliest (1-test_size) rows of each
    group go to train, latest test_size rows go to test — no group's future
    leaks into another group's past, and every group appears on both sides."""

    train_idx, test_idx = [], []
    for _, grp in df.groupby(list(group_cols)):
        grp_sorted = grp.sort_values("Timestamp")
        cut = int(len(grp_sorted) * (1 - test_size))
        train_idx.extend(grp_sorted.index[:cut])
        test_idx.extend(grp_sorted.index[cut:])
    return train_idx, test_idx


def _average_classification_reports(reports):
    avg = {}
    for key in reports[0]:
        if key == "accuracy":
            avg[key] = float(np.mean([r[key] for r in reports]))
        else:
            avg[key] = {
                metric: float(np.mean([r[key][metric] for r in reports]))
                for metric in reports[0][key]
            }
    return avg


def _print_classification_report(report, label_names=("label=0", "label=1")):
    print(f"{'':12s} {'precision':>10s} {'recall':>10s} {'f1-score':>10s} {'support':>10s}")
    for name in [*label_names, "macro avg", "weighted avg"]:
        m = report[name]
        print(f"{name:12s} {m['precision']:10.2f} {m['recall']:10.2f} {m['f1-score']:10.2f} {m['support']:10.1f}")
    print(f"\n{'accuracy':12s} {'':>10s} {'':>10s} {report['accuracy']:10.3f}")


def _best_f1_threshold(y_true, probs):
    """Probability cutoff maximizing F1 on (y_true, probs), via the
    precision-recall curve. Falls back to 0.5 if the curve is degenerate."""

    precision, recall, thresholds = precision_recall_curve(y_true, probs)
    if len(thresholds) == 0:
        return 0.5
    denom = precision + recall
    f1 = np.divide(2 * precision * recall, denom, out=np.zeros_like(denom), where=denom > 0)
    return float(thresholds[np.argmax(f1[:-1])])


def train_lda_classifier(
    scored_df,
    group_cols=("sensor", "workstep"),
    frequency_resolution_hz=6.103515625,
    max_frequency_hz=None,
    test_size=0.3,
    val_size=0.15,
    random_state=0,
    causal_split=True,
    balance_classes=False,
    n_repeats=5,
    tune_threshold=False,
):
    """Shrinkage LinearDiscriminantAnalysis (solver="lsqr", shrinkage="auto") predicting `label` (from
    compute_shape_anomaly_scores) from the raw dB spectrum plus one-hot
    sensor/workstep — group context the plain spectrum-only version lacked
    (it can't otherwise tell "normal for group A" from "abnormal for group B").

    causal_split=True (default): time-ordered split per group (train on each
    group's earlier trials, test on its later ones) — a real test of
    predicting *future* anomalies from *past* patterns, not just interpolating
    within a shuffled, autocorrelated sample. causal_split=False falls back
    to a plain stratified random split (the original, leakage-prone baseline).

    balance_classes=True: the training set is ~99:1 imbalanced (see
    compute_shape_anomaly_scores' top_pct), which starves the minority class.
    Instead of a single fit, repeat n_repeats times: randomly undersample the
    majority class down to the minority class's count (training set only —
    the test set stays untouched/imbalanced, so evaluation stays honest),
    fit fresh each time, and report metrics averaged across the repeats —
    reduces the luck-of-the-draw variance from any single undersample.

    tune_threshold=True: classifying at sklearn's default P>0.5 cutoff only
    makes sense when balance_classes made training ~50:50 — it doesn't match
    the real ~99:1 rate. Instead: carve off a combined holdout of size
    (val_size+test_size) the same way as always (causal or random), then
    stratified-split *that holdout* into val and test — both share the
    holdout's natural ~99:1 distribution, and neither is a slice of train's
    own time range. Pick the F1-maximizing threshold from val's
    predict_proba, apply that fixed threshold to test for the final metrics.
    tune_threshold=False (default): single train/test split (holdout
    fraction = test_size, no val), classify at the default 0.5 cutoff.
    """

    cols = _spectrum_cols(scored_df)
    freqs = _frequencies_for_cols(cols, frequency_resolution_hz)
    cols, freqs = _apply_max_frequency(cols, freqs, max_frequency_hz)

    X_spectrum = to_db(scored_df[cols].to_numpy(dtype=float))
    group_dummies = pd.get_dummies(
        scored_df[list(group_cols)].astype(str), prefix=list(group_cols)
    )
    X = np.hstack([X_spectrum, group_dummies.to_numpy(dtype=float)])
    y = scored_df["label"].to_numpy()

    holdout_size = (val_size + test_size) if tune_threshold else test_size

    if causal_split:
        train_idx, holdout_idx = _causal_split_index(scored_df, group_cols, holdout_size)
        train_pos = scored_df.index.get_indexer(train_idx)
        holdout_pos = scored_df.index.get_indexer(holdout_idx)
        X_train, X_holdout = X[train_pos], X[holdout_pos]
        y_train, y_holdout = y[train_pos], y[holdout_pos]
    else:
        X_train, X_holdout, y_train, y_holdout = train_test_split(
            X, y, test_size=holdout_size, random_state=random_state, stratify=y
        )

    if tune_threshold:
        X_val, X_test, y_val, y_test = train_test_split(
            X_holdout,
            y_holdout,
            test_size=test_size / (test_size + val_size),
            random_state=random_state,
            stratify=y_holdout,
        )
    else:
        X_test, y_test = X_holdout, y_holdout

    n_features = X.shape[1]
    split_desc = "causal (time-ordered per group)" if causal_split else "random (stratified)"

    def fit_and_evaluate(X_fit, y_fit):
        clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
        clf.fit(X_fit, y_fit)
        if tune_threshold:
            threshold = _best_f1_threshold(y_val, clf.predict_proba(X_val)[:, 1])
            y_pred = (clf.predict_proba(X_test)[:, 1] >= threshold).astype(int)
        else:
            threshold = 0.5
            y_pred = clf.predict(X_test)
        return clf, y_pred, threshold

    if not balance_classes:
        clf, y_pred, threshold = fit_and_evaluate(X_train, y_train)

        threshold_desc = f", threshold tuned on val: {threshold:.3f}" if tune_threshold else ""
        print(
            f"\nShrinkage-LDA classifier — {len(cols)} raw dB bins + {n_features - len(cols)} "
            f"sensor/workstep dummies, {split_desc} split{threshold_desc}, "
            f"label positive rate: {y.mean():.3%} (test set: {y_test.mean():.3%})"
        )
        print(classification_report(y_test, y_pred, target_names=["label=0", "label=1"]))

        ConfusionMatrixDisplay.from_predictions(
            y_test, y_pred, display_labels=["0", "1"], normalize="true", values_format=".1%"
        )
        plt.title(f"LDA confusion matrix (test set, {split_desc} split)")
        plt.show()

        return clf

    rng = np.random.default_rng(random_state)
    class_counts = np.bincount(y_train)
    minority_class = int(np.argmin(class_counts))
    minority_idx = np.where(y_train == minority_class)[0]
    majority_idx = np.where(y_train != minority_class)[0]
    n_minority = len(minority_idx)

    reports, confusion_sum, classifiers, thresholds = [], np.zeros((2, 2)), [], []
    for _ in range(n_repeats):
        sampled_majority = rng.choice(majority_idx, size=n_minority, replace=False)
        balanced_idx = np.concatenate([minority_idx, sampled_majority])

        clf, y_pred, threshold = fit_and_evaluate(X_train[balanced_idx], y_train[balanced_idx])

        reports.append(
            classification_report(
                y_test, y_pred, target_names=["label=0", "label=1"], output_dict=True, zero_division=0
            )
        )
        confusion_sum += confusion_matrix(y_test, y_pred, labels=[0, 1])
        classifiers.append(clf)
        thresholds.append(threshold)

    avg_report = _average_classification_reports(reports)

    threshold_desc = f", mean threshold tuned on val: {np.mean(thresholds):.3f}" if tune_threshold else ""
    print(
        f"\nShrinkage-LDA classifier — {len(cols)} raw dB bins + {n_features - len(cols)} "
        f"sensor/workstep dummies, {split_desc} split, class-balanced training "
        f"({n_minority} x 2 per repeat, averaged over {n_repeats} repeats){threshold_desc}, "
        f"label positive rate: {y.mean():.3%} (test set: {y_test.mean():.3%})"
    )
    _print_classification_report(avg_report)

    cm_avg = confusion_sum / n_repeats
    cm_norm = cm_avg / cm_avg.sum(axis=1, keepdims=True)
    ConfusionMatrixDisplay(confusion_matrix=cm_norm, display_labels=["0", "1"]).plot(values_format=".1%")
    plt.title(f"LDA confusion matrix (avg of {n_repeats} balanced-training repeats, {split_desc} split)")
    plt.show()

    return classifiers


RESULTS_DIR = Path("data/results")


def _save_current_figure(name):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(RESULTS_DIR / f"{name}.png", dpi=150, bbox_inches="tight")
    plt.close("all")


def main():

    data = pd.read_parquet("data/processed/combined_measurements.parquet")

    plot_spectrograms_by_group(data, alarmlevel=0, max_frequency_hz=500)
    _save_current_figure("01_spectrograms_alarm0_linear")
    plot_spectrograms_by_group_mel(data, alarmlevel=0, max_frequency_hz=500)
    _save_current_figure("02_spectrograms_alarm0_mel")

    plot_mean_spectra(data, error="std", max_frequency_hz=500)
    _save_current_figure("03_mean_spectra")
    plot_individual_spectra(data, max_frequency_hz=500)
    _save_current_figure("04_individual_spectra")
    plot_individual_spectra(data, max_frequency_hz=500, subtract_baseline=True)
    _save_current_figure("05_individual_spectra_baseline_subtracted")

    plot_band_energy(data, n_bands=8, max_frequency_hz=500)
    _save_current_figure("06_band_energy")
    plot_band_energy(data, n_bands=8, max_frequency_hz=500, subtract_baseline=True)
    _save_current_figure("07_band_energy_baseline_subtracted")

    plot_connectivity_matrix(data, max_frequency_hz=500)
    _save_current_figure("08_connectivity_matrix_full")
    plot_connectivity_matrix(
        data[data["workstep"] != 3],
        max_frequency_hz=500,
        title="Connectivity matrix (excl. workstep 3) — pairwise distance between group mean spectra",
    )
    _save_current_figure("09_connectivity_matrix_excl_workstep3")

    plot_harmonic_peaks(data, max_frequency_hz=500)
    _save_current_figure("10_harmonic_peaks")
    plot_harmonic_peaks(data, max_frequency_hz=500, subtract_baseline=True)
    _save_current_figure("11_harmonic_peaks_baseline_subtracted")
    plot_harmonic_amplitudes(data, max_frequency_hz=500)
    _save_current_figure("12_harmonic_amplitudes")

    scored = compute_shape_anomaly_scores(data, max_frequency_hz=500, top_pct=1.0)
    plot_anomaly_scores(scored)
    _save_current_figure("13_anomaly_scores_top1pct")
    plot_individual_spectra(scored, max_frequency_hz=500, highlight_col="label")
    _save_current_figure("14_individual_spectra_flagged_top1pct")

    train_lda_classifier(scored, max_frequency_hz=500, causal_split=True)
    _save_current_figure("15_lda_confusion_causal")
    train_lda_classifier(scored, max_frequency_hz=500, causal_split=False)
    _save_current_figure("16_lda_confusion_random")
    train_lda_classifier(
        scored, max_frequency_hz=500, causal_split=True,
        balance_classes=True, n_repeats=5, tune_threshold=True,
    )
    _save_current_figure("17_lda_confusion_balanced_tuned")


if __name__ == "__main__":
    matplotlib.use("Agg")  # headless (no display in WSL) — importers keep their own backend
    main()
    print("yolo!")
