#!/usr/bin/env python3
"""Studio-quality procedural upbeat comedy-explainer background music & cartoon SFX generator
for AKILALMAZ Shorts (matches the bouncy, warm, playful marimba/Rhodes/bass/drums groove of v1-v20).
"""
from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Iterable

import numpy as np

SR = 44100


def midi_to_hz(note: float) -> float:
    return 440.0 * (2.0 ** ((note - 69.0) / 12.0))


def _mix_into(buf: np.ndarray, sig: np.ndarray, start_idx: int, pan: float = 0.0, gain: float = 1.0) -> None:
    """Mix mono or stereo signal into stereo buffer [N, 2] with constant-power pan (-1..+1)."""
    if start_idx >= len(buf) or len(sig) == 0:
        return
    end_idx = min(len(buf), start_idx + len(sig))
    n = end_idx - start_idx
    if n <= 0:
        return
    if sig.ndim == 1:
        angle = (pan + 1.0) * 0.25 * math.pi
        gl = math.cos(angle) * gain
        gr = math.sin(angle) * gain
        buf[start_idx:end_idx, 0] += sig[:n] * gl
        buf[start_idx:end_idx, 1] += sig[:n] * gr
    else:
        buf[start_idx:end_idx, 0] += sig[:n, 0] * gain
        buf[start_idx:end_idx, 1] += sig[:n, 1] * gain


def synth_marimba(midi_note: float, dur: float = 0.32, vel: float = 0.8) -> np.ndarray:
    """Warm woody marimba / kalimba pluck with soft mallet transient."""
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    f0 = midi_to_hz(midi_note)

    # Fundamental + woody 4th-harmonic (marimba bar mode ~3.98x) + soft 2nd
    env1 = np.exp(-t * 9.5) * (1.0 - np.exp(-t * 280.0))
    env2 = np.exp(-t * 28.0) * (1.0 - np.exp(-t * 400.0))
    env3 = np.exp(-t * 65.0)

    sig = (
        0.72 * np.sin(2 * np.pi * f0 * t) * env1
        + 0.16 * np.sin(2 * np.pi * (f0 * 2.0) * t) * env2
        + 0.18 * np.sin(2 * np.pi * (f0 * 3.98) * t) * env3
    )
    # Subtle mallet knock
    knock_n = min(n, int(SR * 0.012))
    rng = np.random.default_rng(int(midi_note * 100))
    knock = rng.standard_normal(knock_n) * np.exp(-np.arange(knock_n) / (SR * 0.0025))
    sig[:knock_n] += 0.05 * knock
    return (sig * vel).astype(np.float64)


def synth_rhodes_chord(midi_notes: Iterable[float], dur: float = 0.45, vel: float = 0.35) -> np.ndarray:
    """Warm vintage Rhodes electric piano stab with gentle bell tine."""
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    out = np.zeros(n, dtype=np.float64)
    env_body = np.exp(-t * 4.2) * (1.0 - np.exp(-t * 140.0))
    env_tine = np.exp(-t * 22.0) * (1.0 - np.exp(-t * 300.0))
    trem = 1.0 + 0.06 * np.sin(2 * np.pi * 5.2 * t)
    notes = list(midi_notes)
    for m in notes:
        f = midi_to_hz(m)
        out += (
            0.70 * np.sin(2 * np.pi * f * t) * env_body
            + 0.18 * np.sin(2 * np.pi * 2.0 * f * t) * env_body * np.exp(-t * 3.0)
            + 0.10 * np.sin(2 * np.pi * 7.0 * f * t) * env_tine
        )
    out *= trem * (vel / max(1, len(notes)))
    return out


def synth_bass(midi_note: float, dur: float = 0.34, vel: float = 0.72) -> np.ndarray:
    """Punchy, warm plucked pop-funk bass."""
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    f = midi_to_hz(midi_note)
    env = np.exp(-t * 6.0) * (1.0 - np.exp(-t * 190.0))
    env_hi = np.exp(-t * 20.0) * (1.0 - np.exp(-t * 240.0))
    sig = (
        0.74 * np.sin(2 * np.pi * f * t) * env
        + 0.24 * np.sin(2 * np.pi * 2.0 * f * t) * env_hi
        + 0.09 * np.sin(2 * np.pi * 3.0 * f * t) * np.exp(-t * 32.0)
    )
    # Soft warm saturation
    sig = np.tanh(sig * 1.25) * 0.85
    return sig * vel


def synth_kick(vel: float = 0.78) -> np.ndarray:
    """Tight, warm punchy pop kick."""
    dur = 0.19
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    freq = 48.0 + 115.0 * np.exp(-t * 36.0)
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * 17.5) * (1.0 - np.exp(-t * 900.0))
    click = np.exp(-t * 220.0) * np.sin(2 * np.pi * 1600.0 * t) * 0.15
    sig = np.tanh((np.sin(phase) * env + click) * 1.15)
    return sig * vel


def synth_snare_rim(vel: float = 0.55, seed: int = 1) -> np.ndarray:
    """Crisp pop-funk snare / rimshot clap."""
    dur = 0.14
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n)
    # Simple 1-pole high-pass / band-pass feel via difference + smoothing
    hp = np.diff(noise, prepend=0.0)
    body = np.sin(2 * np.pi * 195.0 * t) * np.exp(-t * 34.0)
    rim = np.sin(2 * np.pi * 880.0 * t) * np.exp(-t * 70.0) * 0.32
    snap = hp * np.exp(-t * 32.0) * 0.42
    sig = np.tanh((body * 0.55 + rim + snap) * 1.2)
    return sig * vel


def synth_hihat(vel: float = 0.22, open_hat: bool = False, seed: int = 7) -> np.ndarray:
    """Crisp closed or subtly open hi-hat."""
    dur = 0.12 if open_hat else 0.045
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n)
    # Double difference -> crisp high-frequency shimmer
    hp = np.diff(np.diff(noise, prepend=0.0), prepend=0.0)
    decay = 24.0 if open_hat else 95.0
    env = np.exp(-t * decay) * (1.0 - np.exp(-t * 1200.0))
    return hp * env * vel * 0.45


def _add_subtle_stereo_reverb(buf: np.ndarray) -> np.ndarray:
    """Warm, light studio room ambience (comb delays L/R)."""
    out = buf.copy()
    delays = [
        (int(SR * 0.023), 0.14, 0.08),
        (int(SR * 0.037), 0.07, 0.13),
        (int(SR * 0.059), 0.09, 0.06),
        (int(SR * 0.083), 0.05, 0.08),
    ]
    for d, gl, gr in delays:
        if d < len(buf):
            out[d:, 0] += buf[:-d, 1] * gl
            out[d:, 1] += buf[:-d, 0] * gr
    return out


def generate_bgm(duration_sec: float, bpm: float = 118.0) -> np.ndarray:
    """Generates a lively, catchy, playful 118 BPM comedy-explainer stereo track [N, 2]."""
    n_samples = int(math.ceil(duration_sec * SR))
    buf = np.zeros((n_samples, 2), dtype=np.float64)

    beat_sec = 60.0 / bpm
    step_sec = beat_sec / 4.0  # 16th-note grid

    # 8-bar progression (A section: Am7 - Fmaj7 - Cmaj7 - G6 | B section: Dm7 - Am7 - Fmaj7 - E7/G)
    chords = [
        # Bar 0: Am7
        {"bass": 45, "chord": [57, 60, 64, 67], "mel": [(0, 72), (3, 76), (6, 79), (8, 76), (10, 74), (12, 72), (14, 69)]},
        # Bar 1: Fmaj7
        {"bass": 41, "chord": [53, 57, 60, 64], "mel": [(0, 69), (2, 72), (6, 76), (8, 74), (11, 72), (14, 69)]},
        # Bar 2: Cmaj7
        {"bass": 48, "chord": [55, 60, 64, 67], "mel": [(0, 76), (3, 79), (6, 81), (8, 79), (10, 76), (12, 74), (14, 72)]},
        # Bar 3: G6
        {"bass": 43, "chord": [55, 59, 62, 64], "mel": [(0, 74), (2, 76), (4, 79), (8, 74), (11, 71), (14, 74)]},
        # Bar 4: Dm7
        {"bass": 50, "chord": [57, 60, 62, 65], "mel": [(0, 77), (3, 76), (6, 74), (8, 72), (10, 74), (12, 77), (14, 76)]},
        # Bar 5: Am7
        {"bass": 45, "chord": [57, 60, 64, 67], "mel": [(0, 76), (2, 72), (6, 74), (8, 72), (11, 69), (14, 72)]},
        # Bar 6: Fmaj7
        {"bass": 41, "chord": [53, 57, 60, 64], "mel": [(0, 72), (3, 74), (6, 76), (8, 79), (11, 76), (14, 74)]},
        # Bar 7: G6 -> turnaround
        {"bass": 43, "chord": [55, 59, 62, 67], "mel": [(0, 74), (2, 71), (4, 74), (6, 76), (8, 79), (12, 76), (14, 74)]},
    ]

    kick_snd = synth_kick(0.72)
    total_bars = int(math.ceil(duration_sec / (16 * step_sec))) + 1

    for bar in range(total_bars):
        bar_t0 = bar * 16 * step_sec
        if bar_t0 >= duration_sec:
            break
        pat = chords[bar % len(chords)]
        bass_root = pat["bass"]
        chord_notes = pat["chord"]

        # 1. Drums (tight bouncy pop-funk groove with slight 16th swing)
        for step in range(16):
            swing = 0.014 if (step % 2 == 1) else 0.0
            t = bar_t0 + step * step_sec + swing
            if t >= duration_sec:
                break
            idx = int(t * SR)

            # Kick pattern: 0, 6, 10 (bouncy syncopated)
            if step in (0, 6, 10) or (bar % 2 == 1 and step == 14):
                _mix_into(buf, kick_snd, idx, pan=0.0, gain=0.72 if step == 0 else 0.56)

            # Crisp snare/rim on beats 2 & 4 (steps 4, 12) + subtle ghost note on 15 every 4th bar
            if step in (4, 12):
                _mix_into(buf, synth_snare_rim(0.50, seed=bar * 17 + step), idx, pan=0.06, gain=0.65)
            elif bar % 4 == 3 and step == 15:
                _mix_into(buf, synth_snare_rim(0.28, seed=bar * 31 + step), idx, pan=-0.06, gain=0.55)

            # Crisp hi-hat on 8ths + gentle 16th ghost ticks
            if step % 2 == 0:
                is_open = (step == 14 and bar % 2 == 1)
                _mix_into(buf, synth_hihat(0.26 if step % 4 == 2 else 0.18, open_hat=is_open, seed=bar * 19 + step), idx, pan=0.22, gain=0.80)
            else:
                _mix_into(buf, synth_hihat(0.09, open_hat=False, seed=bar * 23 + step), idx, pan=0.26, gain=0.65)

        # 2. Funky Plucked Bassline (root, octave pop, fifth)
        bass_steps = [
            (0, bass_root, 0.36, 0.78),
            (3, bass_root + 12, 0.18, 0.45),
            (6, bass_root, 0.28, 0.68),
            (10, bass_root + 7, 0.24, 0.58),
            (12, bass_root + 5 if bar % 2 == 1 else bass_root + 12, 0.22, 0.52),
            (14, bass_root + 7, 0.18, 0.46),
        ]
        for step, note, dur, vel in bass_steps:
            t = bar_t0 + step * step_sec + (0.012 if step % 2 == 1 else 0.0)
            if t < duration_sec:
                _mix_into(buf, synth_bass(note, dur=dur, vel=vel), int(t * SR), pan=-0.05, gain=0.72)

        # 3. Warm Rhodes offbeat chord stabs (steps 2, 6, 10, 14)
        for step, dur, vel in [(0, 0.35, 0.28), (6, 0.28, 0.32), (10, 0.26, 0.26), (14, 0.22, 0.24)]:
            t = bar_t0 + step * step_sec
            if t < duration_sec:
                _mix_into(buf, synth_rhodes_chord(chord_notes, dur=dur, vel=vel), int(t * SR), pan=-0.28, gain=0.75)

        # 4. Playful Marimba / Kalimba melody lead (slightly varied every 2nd loop for freshness)
        for step, note in pat["mel"]:
            t = bar_t0 + step * step_sec + (0.012 if step % 2 == 1 else 0.0)
            if t < duration_sec:
                # Subtle octave/harmony sparkle on second pass
                m_note = note + (12 if (bar >= 8 and bar % 4 == 2 and step in (6, 8)) else 0)
                vel = 0.56 if step in (0, 6, 12) else 0.44
                pan = 0.22 if (step % 4 < 2) else -0.15
                _mix_into(buf, synth_marimba(m_note, dur=0.28, vel=vel), int(t * SR), pan=pan, gain=0.72)

    buf = _add_subtle_stereo_reverb(buf)

    # Gentle fade-in (0.35s) and fade-out (0.8s)
    fin = min(n_samples, int(SR * 0.35))
    fout = min(n_samples, int(SR * 0.80))
    buf[:fin] *= np.linspace(0.0, 1.0, fin)[:, None]
    buf[-fout:] *= np.linspace(1.0, 0.0, fout)[:, None]

    # Normalize BGM cleanly to -14 dBFS RMS so --music-db controls exact balance
    rms = float(np.sqrt(np.mean(buf ** 2)) + 1e-9)
    target_rms = 10.0 ** (-14.0 / 20.0)
    buf = np.tanh(buf * (target_rms / rms) * 0.9) * 0.95
    return buf


# ---------------------------------------------------------------------------
# Crisp Cartoon Sound Effects (SFX)
# ---------------------------------------------------------------------------
def sfx_whoosh(dur: float = 0.22) -> np.ndarray:
    """Snappy scene-cut air whoosh."""
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    rng = np.random.default_rng(42)
    noise = rng.standard_normal(n)
    # Moving bell envelope + gentle filtered sweep
    env = np.sin(np.pi * t / dur) ** 1.6
    tone = np.sin(2 * np.pi * (240.0 + 620.0 * (t / dur)) * t) * 0.14
    # Smooth noise gently
    k = 11
    sm = np.convolve(noise, np.ones(k) / k, mode="same")
    hp = noise - sm
    return ((hp * 0.35 + sm * 0.25) * env + tone * env) * 0.55


def sfx_pop(pitch: float = 520.0) -> np.ndarray:
    """Cute cartoon bubble pop for icon/badge appearances."""
    dur = 0.095
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    f = pitch * (0.65 + 1.35 * (t / dur))
    phase = 2.0 * np.pi * np.cumsum(f) / SR
    env = np.exp(-t * 38.0) * (1.0 - np.exp(-t * 500.0))
    return np.sin(phase) * env * 0.65


def sfx_ding(freq: float = 1046.5) -> np.ndarray:
    """Bright warm bell ding for reveals / punchlines."""
    dur = 0.45
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    sig = (
        0.65 * np.sin(2 * np.pi * freq * t) * np.exp(-t * 7.5)
        + 0.25 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t * 14.0)
        + 0.12 * np.sin(2 * np.pi * freq * 3.0 * t) * np.exp(-t * 22.0)
    )
    return sig * (1.0 - np.exp(-t * 600.0)) * 0.55


def sfx_axe_clang() -> np.ndarray:
    """Dramatic metallic axe swish + crisp steel ring."""
    dur = 0.36
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    swish = sfx_whoosh(0.14)
    out = np.zeros(n, dtype=np.float64)
    out[: len(swish)] += swish * 0.7
    t2 = np.maximum(0.0, t - 0.09)
    mask = t >= 0.09
    ring = (
        0.55 * np.sin(2 * np.pi * 840.0 * t2) * np.exp(-t2 * 13.0)
        + 0.35 * np.sin(2 * np.pi * 1310.0 * t2) * np.exp(-t2 * 18.0)
        + 0.25 * np.sin(2 * np.pi * 2140.0 * t2) * np.exp(-t2 * 25.0)
    ) * mask
    out += ring * 0.52
    return out


def sfx_geiger_burst(dur: float = 1.6) -> np.ndarray:
    """Authentic playful Geiger counter clicks speeding up!"""
    n = int(SR * dur)
    out = np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(1942)
    t_cur = 0.05
    while t_cur < dur - 0.05:
        idx = int(t_cur * SR)
        click_n = int(SR * 0.004)
        tt = np.arange(click_n) / SR
        click = (np.sin(2 * np.pi * 2400.0 * tt) + 0.5 * rng.standard_normal(click_n)) * np.exp(-tt * 900.0)
        end = min(n, idx + click_n)
        out[idx:end] += click[: end - idx] * 0.42
        # Speed up over time
        progress = t_cur / dur
        dt = rng.uniform(0.05, 0.14) * (1.15 - 0.65 * progress)
        t_cur += max(0.035, dt)
    return out


def sfx_boing() -> np.ndarray:
    """Comedic cartoon spring/splash boing for the cadmium bucket squad."""
    dur = 0.34
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float64) / SR
    f = 220.0 + 180.0 * (t / dur) + 42.0 * np.sin(2 * np.pi * 22.0 * t)
    phase = 2.0 * np.pi * np.cumsum(f) / SR
    env = np.exp(-t * 7.5) * (1.0 - np.exp(-t * 300.0))
    return np.sin(phase) * env * 0.55


def sfx_sparkle_chime() -> np.ndarray:
    """Triumphant ascending 4-note sparkle arpeggio for the nuclear success finale."""
    dur = 0.72
    n = int(SR * dur)
    out = np.zeros(n, dtype=np.float64)
    for i, note in enumerate([72, 76, 79, 84]):
        st = int(i * 0.075 * SR)
        bell = sfx_ding(midi_to_hz(note))
        end = min(n, st + len(bell))
        out[st:end] += bell[: end - st] * 0.48
    return out


def build_music_and_sfx_wav(
    out_wav: Path,
    duration_sec: float,
    sfx_events: list[tuple[float, str]],
    bgm_gain_db: float = 0.0,
) -> None:
    """Synthesizes complete stereo BGM + synced cartoon SFX track and saves as 16-bit WAV."""
    buf = generate_bgm(duration_sec, bpm=118.0)
    bgm_lin = 10.0 ** (bgm_gain_db / 20.0)
    buf *= bgm_lin

    sfx_gain = 10.0 ** ((bgm_gain_db + 2.5) / 20.0)
    for t_sec, kind in sfx_events:
        idx = int(max(0.0, t_sec) * SR)
        if kind == "whoosh":
            _mix_into(buf, sfx_whoosh(), idx, pan=0.0, gain=sfx_gain * 0.80)
        elif kind == "pop":
            _mix_into(buf, sfx_pop(540.0), idx, pan=0.12, gain=sfx_gain * 0.85)
        elif kind == "pop_hi":
            _mix_into(buf, sfx_pop(720.0), idx, pan=-0.12, gain=sfx_gain * 0.85)
        elif kind == "ding":
            _mix_into(buf, sfx_ding(1046.5), idx, pan=0.0, gain=sfx_gain * 0.80)
        elif kind == "axe":
            _mix_into(buf, sfx_axe_clang(), idx, pan=0.18, gain=sfx_gain * 0.95)
        elif kind == "geiger":
            _mix_into(buf, sfx_geiger_burst(1.8), idx, pan=-0.15, gain=sfx_gain * 0.90)
        elif kind == "boing":
            _mix_into(buf, sfx_boing(), idx, pan=0.0, gain=sfx_gain * 0.85)
        elif kind == "sparkle":
            _mix_into(buf, sfx_sparkle_chime(), idx, pan=0.0, gain=sfx_gain * 0.90)

    # Soft limiter & 16-bit PCM write
    buf = np.clip(buf, -0.98, 0.98)
    pcm = (buf * 32767.0).astype(np.int16)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/test_bgm_sfx.wav")
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else 14.0
    events = [
        (0.6, "pop"),
        (3.0, "whoosh"),
        (4.0, "geiger"),
        (6.5, "whoosh"),
        (7.0, "axe"),
        (9.5, "whoosh"),
        (10.0, "boing"),
        (12.2, "sparkle"),
    ]
    build_music_and_sfx_wav(out, dur, events)
    print(f"Wrote {out} ({dur}s)")
