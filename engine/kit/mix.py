#!/usr/bin/env python3
"""
engine/kit/mix.py — Procedural Upbeat Cartoon BGM + Scene/Badge SFX Mixer
Matches AKILALMAZ v9–v20 lively marimba/plucked synth + crisp rhythm groove:
  - Music level: --music-db -12.0 (default)
  - SFX level:   --sfx-db   -6.4  (default)
  - Output:      work/mix_raw.wav (48kHz stereo 16-bit PCM, ready for finish_tr.sh loudnorm)
"""

import argparse
import json
import math
import subprocess
import wave
from pathlib import Path
import numpy as np

SR = 48000


def db_to_gain(db: float) -> float:
    return 10.0 ** (db / 20.0)


def decode_voice_wav(voice_mp3: Path, out_wav: Path) -> np.ndarray:
    subprocess.check_call(
        [
            "ffmpeg", "-v", "error", "-y",
            "-i", str(voice_mp3),
            "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
            str(out_wav),
        ]
    )
    with wave.open(str(out_wav), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return arr.reshape(-1, 2)


def synth_bgm(duration: float, bpm: float = 122.0, seed: int = 21) -> np.ndarray:
    """
    Generates an upbeat, playful, non-fatiguing cartoon marimba/pluck + bass + light percussion loop
    inspired directly by AKILALMAZ v1–v20 background tracks.
    """
    n = int(math.ceil(duration * SR))
    L = np.zeros(n, dtype=np.float32)
    R = np.zeros(n, dtype=np.float32)

    beat = 60.0 / bpm
    step = beat / 2.0  # eighth notes
    total_steps = int(math.ceil(duration / step)) + 2

    # Bright playful C-major / A-minor storytelling progression (I - V - vi - IV)
    # Frequencies in Hz
    chords = [
        [261.63, 329.63, 392.00, 523.25],  # C
        [196.00, 246.94, 293.66, 392.00],  # G
        [220.00, 261.63, 329.63, 440.00],  # Am
        [174.61, 220.00, 261.63, 349.23],  # F
    ]
    bass_roots = [130.81, 98.00, 110.00, 87.31]
    arp_pattern = [0, 2, 1, 3, 2, 1, 3, 2]
    rng = np.random.default_rng(seed)

    def add_tone(start_s: float, dur_s: float, freq: float, amp: float, pan: float = 0.0, kind: str = "marimba"):
        i0 = int(start_s * SR)
        ln = int(dur_s * SR)
        if i0 >= n or ln <= 0:
            return
        ln = min(ln, n - i0)
        t = np.arange(ln, dtype=np.float32) / SR
        if kind == "marimba":
            env = np.exp(-t * 10.5) * np.minimum(1.0, t / 0.004)
            sig = (
                0.78 * np.sin(2 * np.pi * freq * t)
                + 0.16 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t * 16.0)
                + 0.06 * np.sin(2 * np.pi * freq * 4.0 * t) * np.exp(-t * 28.0)
            ) * env * amp
        elif kind == "bass":
            env = np.exp(-t * 5.2) * np.minimum(1.0, t / 0.006)
            sig = (
                0.82 * np.sin(2 * np.pi * freq * t)
                + 0.18 * np.sin(2 * np.pi * freq * 2.0 * t)
            ) * env * amp
        elif kind == "pad":
            env = np.minimum(1.0, t / 0.06) * np.exp(-t * 1.4)
            sig = (
                0.65 * np.sin(2 * np.pi * freq * t)
                + 0.35 * np.sin(2 * np.pi * freq * 1.5 * t)
            ) * env * amp
        else:
            sig = np.zeros(ln, dtype=np.float32)

        gL = math.sqrt(0.5 * (1.0 - pan))
        gR = math.sqrt(0.5 * (1.0 + pan))
        L[i0:i0 + ln] += sig * gL
        R[i0:i0 + ln] += sig * gR

    def add_kick(start_s: float, amp: float = 0.38):
        i0 = int(start_s * SR)
        ln = min(int(0.14 * SR), n - i0)
        if i0 >= n or ln <= 0:
            return
        t = np.arange(ln, dtype=np.float32) / SR
        freq = 120.0 * np.exp(-t * 28.0) + 46.0
        phase = np.cumsum(2 * np.pi * freq / SR)
        sig = np.sin(phase) * np.exp(-t * 19.0) * amp
        L[i0:i0 + ln] += sig
        R[i0:i0 + ln] += sig

    def add_hat(start_s: float, amp: float = 0.09, open_hat: bool = False):
        i0 = int(start_s * SR)
        dur = 0.09 if open_hat else 0.032
        ln = min(int(dur * SR), n - i0)
        if i0 >= n or ln <= 0:
            return
        t = np.arange(ln, dtype=np.float32) / SR
        noise = rng.standard_normal(ln).astype(np.float32)
        # Simple high-pass difference filter for crisp shaker/hat
        hp = np.diff(noise, prepend=0.0)
        sig = hp * np.exp(-t * (26.0 if open_hat else 85.0)) * amp
        L[i0:i0 + ln] += sig * 0.9
        R[i0:i0 + ln] += sig * 1.1

    def add_clap(start_s: float, amp: float = 0.14):
        i0 = int(start_s * SR)
        ln = min(int(0.08 * SR), n - i0)
        if i0 >= n or ln <= 0:
            return
        t = np.arange(ln, dtype=np.float32) / SR
        noise = rng.standard_normal(ln).astype(np.float32)
        env = np.exp(-t * 42.0) * (1.0 + 0.4 * np.sin(2 * np.pi * 140 * t))
        sig = noise * env * amp
        L[i0:i0 + ln] += sig
        R[i0:i0 + ln] += sig

    for s in range(total_steps):
        ts = s * step
        bar = (s // 8) % 4
        pos = s % 8
        chord = chords[bar]

        # Marimba/pizzicato bouncy arpeggio
        note = chord[arp_pattern[pos]]
        if pos in (0, 2, 3, 5, 6, 7):
            pan = -0.25 if pos % 2 == 0 else 0.25
            add_tone(ts, step * 1.4, note, 0.24 if pos % 2 == 0 else 0.18, pan=pan, kind="marimba")

        # Gentle chord swell on beat 1
        if pos == 0:
            add_tone(ts, beat * 3.6, chord[1], 0.065, pan=-0.18, kind="pad")
            add_tone(ts, beat * 3.6, chord[2], 0.055, pan=0.18, kind="pad")

        # Bouncy bass
        if pos in (0, 3, 4, 6):
            bf = bass_roots[bar] * (1.5 if pos == 6 else 1.0)
            add_tone(ts, step * 1.6, bf, 0.30, pan=0.0, kind="bass")

        # Crisp light groove
        if pos in (0, 4):
            add_kick(ts, 0.34)
        if pos in (2, 6):
            add_clap(ts, 0.12)
        if pos % 2 == 1:
            add_hat(ts, 0.075, open_hat=(pos == 7))

    # Smooth 0.3s fade-out at the very end for seamless loop feel
    fade = min(int(0.25 * SR), n)
    if fade > 0:
        ramp = np.linspace(1.0, 0.0, fade, dtype=np.float32)
        L[-fade:] *= ramp
        R[-fade:] *= ramp

    stereo = np.stack([L, R], axis=1)
    peak = float(np.max(np.abs(stereo))) + 1e-6
    return stereo / peak * 0.78


def synth_sfx(duration: float, events: list[dict]) -> np.ndarray:
    """
    Synthesizes crisp cartoon SFX:
      - whoosh: soft filtered noise sweep on scene flash cuts
      - pop:    bouncy pitch-up bubble pop on badge / year / "?" card appearance
      - ding:   bright bell sparkle on finale record badge
      - alarm:  short comedic cartoon tension boing/alert
    """
    n = int(math.ceil(duration * SR))
    out = np.zeros((n, 2), dtype=np.float32)
    rng = np.random.default_rng(99)

    for ev in events:
        t0 = float(ev.get("t", 0.0))
        kind = ev.get("kind", "whoosh")
        i0 = int(t0 * SR)
        if i0 < 0 or i0 >= n:
            continue

        if kind == "whoosh":
            ln = min(int(0.22 * SR), n - i0)
            t = np.arange(ln, dtype=np.float32) / SR
            env = np.sin(np.pi * t / (ln / SR)) ** 1.4
            noise = rng.standard_normal(ln).astype(np.float32)
            # Soft low-pass smoothing
            kernel = np.ones(11, dtype=np.float32) / 11.0
            smooth = np.convolve(noise, kernel, mode="same")
            sweep = np.sin(2 * np.pi * (240 + 520 * (t / 0.22)) * t) * 0.16
            sig = (smooth * 0.55 + sweep) * env * 0.52
        elif kind == "pop":
            ln = min(int(0.14 * SR), n - i0)
            t = np.arange(ln, dtype=np.float32) / SR
            f = 340.0 + 780.0 * (1.0 - np.exp(-t * 24.0))
            phase = np.cumsum(2 * np.pi * f / SR)
            sig = np.sin(phase) * np.exp(-t * 28.0) * 0.65
        elif kind == "ding":
            ln = min(int(0.55 * SR), n - i0)
            t = np.arange(ln, dtype=np.float32) / SR
            sig = (
                0.55 * np.sin(2 * np.pi * 1046.5 * t)
                + 0.32 * np.sin(2 * np.pi * 1567.98 * t)
                + 0.18 * np.sin(2 * np.pi * 2093.0 * t)
            ) * np.exp(-t * 6.5) * 0.52
        elif kind == "boing":
            ln = min(int(0.28 * SR), n - i0)
            t = np.arange(ln, dtype=np.float32) / SR
            f = 220.0 + 180.0 * np.sin(2 * np.pi * 11 * t) * np.exp(-t * 5.0)
            phase = np.cumsum(2 * np.pi * f / SR)
            sig = np.sin(phase) * np.exp(-t * 9.5) * 0.55
        else:
            continue

        out[i0:i0 + ln, 0] += sig
        out[i0:i0 + ln, 1] += sig

    return out


def main():
    ap = argparse.ArgumentParser(description="Mix voice + procedural BGM + SFX to mix_raw.wav")
    ap.add_argument("--work", required=True, help="Work directory containing voice.mp3")
    ap.add_argument("--events", default="", help="Optional JSON file with SFX events list [{t, kind}]")
    ap.add_argument("--music-db", type=float, default=-12.0)
    ap.add_argument("--sfx-db", type=float, default=-6.4)
    ap.add_argument("--bpm", type=float, default=122.0)
    ap.add_argument("--seed", type=int, default=21)
    args = ap.parse_args()

    work = Path(args.work)
    voice_mp3 = work / "voice.mp3"
    voice_wav = work / "_voice_tmp.wav"
    voice = decode_voice_wav(voice_mp3, voice_wav)
    voice_wav.unlink(missing_ok=True)

    # Pad 0.25s tail so end of speech never clips
    pad = np.zeros((int(0.25 * SR), 2), dtype=np.float32)
    voice = np.concatenate([voice, pad], axis=0)
    duration = len(voice) / SR

    bgm = synth_bgm(duration, bpm=args.bpm, seed=args.seed)[: len(voice)]
    events = []
    if args.events and Path(args.events).exists():
        events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    sfx = synth_sfx(duration, events)[: len(voice)]

    # Normalize voice RMS to ~0.22 so --music-db -12.0 sits at the exact v9–v20 sweet spot
    v_rms = float(np.sqrt(np.mean(voice ** 2))) + 1e-6
    voice_norm = voice * (0.22 / v_rms)

    # Light sidechain ducking when voice is active
    env_win = int(0.08 * SR)
    v_abs = np.mean(np.abs(voice_norm), axis=1)
    kernel = np.ones(env_win, dtype=np.float32) / env_win
    v_env = np.convolve(v_abs, kernel, mode="same")
    duck = np.clip(1.0 - v_env * 1.15, 0.68, 1.0)[:, None]

    mix = (
        voice_norm
        + bgm * db_to_gain(args.music_db) * duck
        + sfx * db_to_gain(args.sfx_db)
    )

    # Soft peak limiter before loudnorm
    peak = float(np.max(np.abs(mix)))
    if peak > 0.94:
        mix = np.tanh(mix / peak * 1.05) * 0.92

    pcm = np.clip(mix * 32767.0, -32768, 32767).astype(np.int16)
    out_wav = work / "mix_raw.wav"
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())

    print(
        f"[mix] Wrote {out_wav.name} ({duration:.2f}s, music={args.music_db}dB, "
        f"sfx={args.sfx_db}dB, {len(events)} SFX cues)"
    )


if __name__ == "__main__":
    main()
