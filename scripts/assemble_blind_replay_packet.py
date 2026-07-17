#!/usr/bin/env python3
"""Assemble the non-binding, text-redacted Phase 1 blind replay packet."""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import random
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "review/phase1/calibration-reference"
SYNTHETIC = ROOT / "review/phase1/calibration-synthetic-final/browser"
DEFAULT_OUTPUT = ROOT / "review/phase1/blind-replay-documentation"
DEFAULT_UNBLINDING_OUTPUT = ROOT / "review/phase1/blind-replay-unblinding"
SEED = "phase1-blind-replay-v1"
WINDOW_MIN_MS = 9_000
WINDOW_TARGET_MS = 10_000
WINDOW_MAX_MS = 11_000
MIN_FRAMES = 24
MAX_REAL_WINDOWS_PER_BUNDLE = 4
REGIME_QUOTAS = {
    "natural-drafting": 4,
    "revision-heavy-writing": 4,
    "copied-or-scripted-typing": 3,
    "cursor-and-selection-edits": 3,
    "short-command-like-inputs": 3,
    "pauses-and-resumptions": 3,
}


@dataclass(frozen=True)
class Trace:
    kind: str
    source_id: str
    source_path: Path
    regime: str
    frames: tuple[dict[str, Any], ...]
    sha256: str


@dataclass(frozen=True)
class Window:
    trace: Trace
    start_index: int
    end_index: int
    start_ms: float
    end_ms: float

    @property
    def duration_ms(self) -> float:
        return self.end_ms - self.start_ms

    @property
    def frame_count(self) -> int:
        return self.end_index - self.start_index + 1


def _canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _public_ms(value: float) -> int:
    return int(math.floor(value + 0.5))


def _redact_text(value: str) -> str:
    # Keep line geometry; every other UTF-16 code unit becomes one opaque cell.
    return "".join(
        character if character in "\r\n" else "█" * _utf16_length(character)
        for character in value
    )


def _load_trace(kind: str, path: Path) -> Trace:
    raw = path.read_bytes()
    data = json.loads(raw)
    frames = tuple(data["sampler_frames"])
    if not frames:
        raise ValueError(f"{path} has no sampler frames")
    times = [float(frame["relative_ms"]) for frame in frames]
    if times != sorted(times):
        raise ValueError(f"{path} sampler frames are not time ordered")
    return Trace(
        kind=kind,
        source_id=str(data["runtime_session_id"]),
        source_path=path.relative_to(ROOT),
        regime=str(data["regime"]),
        frames=frames,
        sha256=f"sha256:{_sha256(raw)}",
    )


def _reference_traces() -> list[Trace]:
    manifest = json.loads((REFERENCE / "manifest.json").read_text())
    traces = []
    for record in manifest["records"]:
        trace = _load_trace("recorded", REFERENCE / record["browser_bundle"]["path"])
        if (
            trace.regime != record["regime"]
            or trace.source_id != record["runtime_session_id"]
            or trace.sha256 != record["browser_bundle"]["sha256"]
        ):
            raise ValueError(f"recorded calibration manifest binding failed: {trace.source_path}")
        traces.append(trace)
    if Counter(trace.regime for trace in traces) != Counter({
        "natural-drafting": 1,
        "revision-heavy-writing": 1,
        "copied-or-scripted-typing": 1,
        "cursor-and-selection-edits": 2,
        "short-command-like-inputs": 1,
        "pauses-and-resumptions": 1,
    }):
        raise ValueError("recorded calibration regimes no longer match the frozen reference")
    return traces


def _synthetic_traces() -> list[Trace]:
    traces = [_load_trace("synthetic", path) for path in sorted(SYNTHETIC.glob("*.json"))]
    counts = Counter(trace.regime for trace in traces)
    if set(counts) != set(REGIME_QUOTAS) or min(counts.values()) < 20:
        raise ValueError("synthetic calibration population cannot support the blind packet")
    return traces


def _windows(trace: Trace) -> list[Window]:
    times = [float(frame["relative_ms"]) for frame in trace.frames]
    windows: list[Window] = []
    for start_index, start_ms in enumerate(times):
        low = bisect.bisect_left(times, start_ms + WINDOW_MIN_MS, start_index + MIN_FRAMES - 1)
        high = bisect.bisect_right(times, start_ms + WINDOW_MAX_MS) - 1
        if low > high:
            continue
        target = bisect.bisect_left(times, start_ms + WINDOW_TARGET_MS, low, high + 1)
        candidates = [index for index in (target - 1, target) if low <= index <= high]
        end_index = min(candidates, key=lambda index: (abs(times[index] - start_ms - WINDOW_TARGET_MS), index))
        windows.append(Window(trace, start_index, end_index, start_ms, times[end_index]))
    return windows


def _window_key(window: Window) -> tuple[str, int, int]:
    return (window.trace.source_id, window.start_index, window.end_index)


def _overlaps(first: Window, second: Window) -> bool:
    return first.start_ms < second.end_ms and second.start_ms < first.end_ms


def _matching_duration(first: Window, second: Window) -> bool:
    return abs(first.duration_ms - second.duration_ms) / max(first.duration_ms, second.duration_ms) <= 0.05


def _choose_pairs(recorded: list[Trace], synthetic: list[Trace]) -> list[tuple[Window, Window]]:
    rng = random.Random(SEED)
    synthetic_by_regime: dict[str, list[Window]] = defaultdict(list)
    for trace in synthetic:
        synthetic_by_regime[trace.regime].extend(_windows(trace))
    for windows in synthetic_by_regime.values():
        windows.sort(key=_window_key)
        rng.shuffle(windows)

    pairs: list[tuple[Window, Window]] = []
    for regime, quota in REGIME_QUOTAS.items():
        candidates = [window for trace in recorded if trace.regime == regime for window in _windows(trace)]
        candidates.sort(key=_window_key)
        rng.shuffle(candidates)
        selected: list[Window] = []
        used_synthetic_sources: set[str] = set()
        for candidate in candidates:
            if len(selected) == quota:
                break
            bundle_windows = [window for window in selected if window.trace.source_id == candidate.trace.source_id]
            if len(bundle_windows) >= MAX_REAL_WINDOWS_PER_BUNDLE or any(
                _overlaps(candidate, existing) for existing in bundle_windows
            ):
                continue
            match = next(
                (
                    window
                    for window in synthetic_by_regime[regime]
                    if window.trace.source_id not in used_synthetic_sources
                    and _matching_duration(candidate, window)
                ),
                None,
            )
            if match is None:
                continue
            selected.append(candidate)
            used_synthetic_sources.add(match.trace.source_id)
            pairs.append((candidate, match))
        if len(selected) != quota:
            raise ValueError(f"could not select {quota} non-overlapping recorded {regime} windows")

    if len(pairs) != 20 or Counter(real.trace.regime for real, _ in pairs) != Counter(REGIME_QUOTAS):
        raise ValueError("blind packet balance is invalid")
    return pairs


def _public_window(window: Window) -> dict[str, object]:
    frames: list[dict[str, object]] = []
    for index, item in enumerate(window.trace.frames[window.start_index : window.end_index + 1], start=1):
        frame = item["frame"]
        text = frame["text"]
        if not isinstance(text, str):
            raise ValueError(f"{window.trace.source_path} has a non-string frame text")
        redacted = _redact_text(text)
        text_length = _utf16_length(text)
        start, end = int(frame["selection_start"]), int(frame["selection_end"])
        if _utf16_length(redacted) != text_length or not 0 <= start <= end <= text_length:
            raise ValueError(f"{window.trace.source_path} has invalid UTF-16 frame geometry")
        relative_ms = _public_ms(float(item["relative_ms"]) - window.start_ms)
        if frames:
            relative_ms = max(relative_ms, int(frames[-1]["relative_ms"]) + 1)
        frames.append({
            "frame_index": index,
            "relative_ms": relative_ms,
            "activity": frame["activity"],
            "input_type": frame["input_type"],
            "is_composing": frame["is_composing"],
            "selection_start": start,
            "selection_end": end,
            "text": redacted,
            "text_utf16_length": text_length,
        })
    return {
        "duration_ms": max(_public_ms(window.duration_ms), int(frames[-1]["relative_ms"])),
        "frame_count": len(frames),
        "frames": frames,
    }


def _assert_public_redaction(packet: dict[str, object]) -> None:
    def visit(value: object) -> None:
        if isinstance(value, dict):
            if "data" in value or "runtime_session_id" in value or "source_path" in value:
                raise ValueError("public packet contains a private source field")
            if "text" in value:
                text = value["text"]
                if not isinstance(text, str) or set(text) - {"█", "\r", "\n"}:
                    raise ValueError("public packet contains unredacted text")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(packet)


def _viewer_html() -> bytes:
    return br'''<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Phase 1 blind replay viewer</title>
<style>
body{font:16px system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#18212f}button,input,select{font:inherit}#pairs{display:flex;flex-wrap:wrap;gap:.4rem;margin:1rem 0}.selected{background:#183b5b;color:white}.controls{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;border:1px solid #bdc7d3;border-radius:.5rem}.controls input{flex:1;min-width:16rem}.sides{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.side{border:1px solid #bdc7d3;border-radius:.5rem;padding:1rem}.state{font-size:.85rem;color:#4c5a68}.text{min-height:15rem;max-height:28rem;overflow:auto;background:#17202b;color:#d6e3ef;padding:1rem;white-space:pre-wrap;overflow-wrap:anywhere;border-radius:.25rem}.selection{background:#ffd75e;color:#17202b}.caret{border-left:3px solid #ffd75e;margin-left:-1px}@media(max-width:760px){.sides{grid-template-columns:1fr}}</style>
<main>
<h1>Phase 1 blind replay viewer</h1>
<p>Non-binding documentation. Load <code>public-blinded-pairs.json</code>; each trace is text-redacted.</p>
<input id="file" type="file" accept="application/json,.json">
<div id="pairs"></div>
<fieldset id="controls" class="controls" disabled><legend>Replay</legend><button id="play" type="button">Play</button><button id="pause" type="button">Pause</button><button id="restart" type="button">Restart</button><label>Speed <select id="speed"><option value="0.5">0.5&times;</option><option value="1" selected>1&times;</option><option value="2">2&times;</option><option value="4">4&times;</option></select></label><input id="timeline" type="range" min="0" value="0" step="1" aria-label="Replay time"><output id="clock">0.000 s</output></fieldset>
<div id="content"></div>
</main>
<script>
let packet,current=0,clock=0,playing=false,lastTick=0,animation=0;
const el=id=>document.getElementById(id);
const trace=name=>packet.pairs[current][`side_${name.toLowerCase()}`];
const duration=()=>Math.max(trace("A").duration_ms,trace("B").duration_ms);
function frameAt(value,time){let index=0;while(index+1<value.frames.length&&value.frames[index+1].relative_ms<=time)index++;return value.frames[index]}
function paint(name,frame){const text=el(`text-${name}`),mark=document.createElement("span"),start=frame.selection_start,end=frame.selection_end;mark.className=start===end?"caret":"selection";mark.textContent=start===end?"\u200b":frame.text.slice(start,end);text.replaceChildren(document.createTextNode(frame.text.slice(0,start)),mark,document.createTextNode(frame.text.slice(end)));}
function draw(name){const value=trace(name),frame=frameAt(value,clock);el(`state-${name}`).textContent=`frame ${frame.frame_index}/${value.frame_count} | ${frame.relative_ms} ms | selection ${frame.selection_start}\u2013${frame.selection_end} | ${frame.input_type||"no input"} | ${frame.activity}`;paint(name,frame)}
function setClock(value){clock=Math.max(0,Math.min(Number(value),duration()));el("timeline").value=clock;el("clock").textContent=`${(clock/1000).toFixed(3)} s`;draw("A");draw("B")}
function pause(){playing=false;cancelAnimationFrame(animation);el("play").disabled=false}
function restart(){pause();setClock(0)}
function tick(now){if(!playing)return;setClock(clock+(now-lastTick)*Number(el("speed").value));lastTick=now;if(clock>=duration())pause();else animation=requestAnimationFrame(tick)}
function play(){if(playing)return;if(clock>=duration())setClock(0);playing=true;lastTick=performance.now();el("play").disabled=true;animation=requestAnimationFrame(tick)}
function side(name){return `<section class="side"><h2>Side ${name}</h2><p class="state" id="state-${name}"></p><pre class="text" id="text-${name}"></pre></section>`}
function render(){pause();const pair=packet.pairs[current];el("pairs").innerHTML=packet.pairs.map((item,index)=>`<button type="button" class="${index===current?"selected":""}" data-pair="${index}">${item.pair_id}</button>`).join("");el("content").innerHTML=`<p><strong>${pair.pair_id}</strong> \u00b7 ${pair.regime}</p><div class="sides">${side("A")}${side("B")}</div>`;el("controls").disabled=false;el("timeline").max=Math.ceil(duration());document.querySelectorAll("[data-pair]").forEach(button=>button.onclick=()=>{current=+button.dataset.pair;clock=0;render();setClock(0)});setClock(clock)}
function load(value){packet=typeof value==="string"?JSON.parse(value):value;if(!packet.blinded||!Array.isArray(packet.pairs)||!packet.pairs.length||packet.pairs.some(pair=>![pair.side_a,pair.side_b].every(side=>side&&side.frame_count===side.frames.length&&side.frames.length)))throw Error("not a blind replay packet");current=0;clock=0;render()}
el("play").onclick=play;el("pause").onclick=pause;el("restart").onclick=restart;el("timeline").oninput=event=>{pause();setClock(event.target.value)};
el("file").onchange=event=>event.target.files[0].text().then(load).catch(error=>alert(error.message));
window.__blindReplay={load,play,pause,restart,seek:setClock,state:()=>({clock,playing,current})};
</script>
</html>
'''


def _readme() -> bytes:
    return b"""# Phase 1 blind replay documentation

This is a non-binding, reporting-only packet. It is not an admission record, gate, schema, or corpus artifact.

Open `viewer.html`, select `public-blinded-pairs.json`, and record judgments in `judgment-template.md`. The answer key is physically separate at `../blind-replay-unblinding/PRIVATE-unblinding.json`; keep that sibling directory private until review is complete. `SHA256SUMS` covers only this public directory's files, excluding itself.
"""


def _judgment_template() -> bytes:
    return b"""# Blind replay judgment form

This form records non-binding plausibility observations only. Do not use it as an admission or promotion decision.

For each pair:

- Pair ID:
- More plausibly recorded interaction: Side A / Side B / indistinguishable
- Confidence: low / medium / high
- Notes on timing, selection behavior, and edits:

Do not open `../blind-replay-unblinding/PRIVATE-unblinding.json` until all judgments are recorded.
"""


def _assert_blind_metadata(public_pairs: list[dict[str, object]], private_pairs: list[dict[str, object]]) -> None:
    for public, private in zip(public_pairs, private_pairs, strict=True):
        if set(public) != {"pair_id", "regime", "side_a", "side_b"}:
            raise ValueError("public pair metadata can encode origin")
        if public["pair_id"] != private["pair_id"] or public["regime"] != private["regime"]:
            raise ValueError("public/private pair binding changed")
        side_a = public["side_a"]
        side_b = public["side_b"]
        if not isinstance(side_a, dict) or not isinstance(side_b, dict):
            raise ValueError("public side is not an object")
        expected_side_keys = {"duration_ms", "frame_count", "frames"}
        if set(side_a) != expected_side_keys or set(side_b) != expected_side_keys:
            raise ValueError("public sides have asymmetric metadata")
        expected_frame_keys = {
            "activity",
            "frame_index",
            "input_type",
            "is_composing",
            "relative_ms",
            "selection_end",
            "selection_start",
            "text",
            "text_utf16_length",
        }
        for side in (side_a, side_b):
            frames = side["frames"]
            if not isinstance(frames, list) or not frames or any(
                not isinstance(frame, dict) or set(frame) != expected_frame_keys
                for frame in frames
            ):
                raise ValueError("public sides have asymmetric frame metadata")
        fractional_presence: dict[str, bool] = {}
        for label, side in (("A", side_a), ("B", side_b)):
            timing_values = [side["duration_ms"], *(frame["relative_ms"] for frame in side["frames"])]
            fractional_presence[label] = any(
                isinstance(value, float) and not value.is_integer() for value in timing_values
            )
            if any(type(value) is not int for value in timing_values):
                raise ValueError("public sides do not share integer-millisecond precision")
            frame_times = timing_values[1:]
            if (
                frame_times[0] != 0
                or side["duration_ms"] != frame_times[-1]
                or not WINDOW_MIN_MS <= side["duration_ms"] <= WINDOW_MAX_MS
                or any(current <= previous for previous, current in zip(frame_times, frame_times[1:]))
            ):
                raise ValueError("public frame timestamps are not strictly monotonic")
        if fractional_presence["A"] != fractional_presence["B"] or fractional_presence[private["recorded_side"]]:
            raise ValueError("fractional timestamp presence reveals the recorded side")


def _render_files() -> tuple[dict[str, bytes], dict[str, bytes]]:
    pairs = _choose_pairs(_reference_traces(), _synthetic_traces())
    rng = random.Random(SEED)
    rng.shuffle(pairs)
    synthetic_on_a = set(rng.sample(range(len(pairs)), 10))
    public_pairs: list[dict[str, object]] = []
    private_pairs: list[dict[str, object]] = []
    for index, (recorded, synthetic) in enumerate(pairs, start=1):
        pair_id = f"P{index:02d}"
        synthetic_side = "A" if index - 1 in synthetic_on_a else "B"
        public_pairs.append({
            "pair_id": pair_id,
            "regime": recorded.trace.regime,
            "side_a": _public_window(synthetic if synthetic_side == "A" else recorded),
            "side_b": _public_window(recorded if synthetic_side == "A" else synthetic),
        })
        private_pairs.append({
            "pair_id": pair_id,
            "regime": recorded.trace.regime,
            "recorded_side": "B" if synthetic_side == "A" else "A",
            "recorded": {
                "runtime_session_id": recorded.trace.source_id,
                "source_path": str(recorded.trace.source_path),
                "start_frame_index": recorded.start_index + 1,
                "end_frame_index": recorded.end_index + 1,
                "start_ms": round(recorded.start_ms, 3),
                "end_ms": round(recorded.end_ms, 3),
            },
            "synthetic": {
                "runtime_session_id": synthetic.trace.source_id,
                "source_path": str(synthetic.trace.source_path),
                "start_frame_index": synthetic.start_index + 1,
                "end_frame_index": synthetic.end_index + 1,
                "start_ms": round(synthetic.start_ms, 3),
                "end_ms": round(synthetic.end_ms, 3),
            },
        })
    public = {
        "format_version": "phase1-blind-replay/v1",
        "blinded": True,
        "non_binding": True,
        "pair_count": len(public_pairs),
        "pairs": public_pairs,
    }
    _assert_public_redaction(public)
    public_bytes = _canonical(public)
    private = {
        "format_version": "phase1-blind-replay-private/v1",
        "non_binding": True,
        "selection_seed": SEED,
        "public_packet_sha256": _sha256(public_bytes),
        "regime_quotas": REGIME_QUOTAS,
        "synthetic_side_counts": {
            "A": sum(pair["recorded_side"] == "B" for pair in private_pairs),
            "B": sum(pair["recorded_side"] == "A" for pair in private_pairs),
        },
        "pairs": private_pairs,
    }
    if private["synthetic_side_counts"] != {"A": 10, "B": 10}:
        raise ValueError("synthetic sides are not balanced")
    _assert_blind_metadata(public_pairs, private_pairs)
    return {
        "README.md": _readme(),
        "viewer.html": _viewer_html(),
        "judgment-template.md": _judgment_template(),
        "public-blinded-pairs.json": public_bytes,
    }, {
        "PRIVATE-unblinding.json": _canonical(private),
    }


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(f"{_sha256(data)}  {name}\n" for name, data in sorted(files.items())).encode("ascii")


def _directory_files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _verify(
    output: Path,
    public_files: dict[str, bytes],
    unblinding_output: Path,
    private_files: dict[str, bytes],
) -> None:
    public = _directory_files(output)
    private = _directory_files(unblinding_output)
    if public != {**public_files, "SHA256SUMS": _checksums(public_files)}:
        raise ValueError("public packet differs from deterministic assembly")
    if private != {**private_files, "SHA256SUMS": _checksums(private_files)}:
        raise ValueError("private mapping differs from deterministic assembly")
    mapping = json.loads(private["PRIVATE-unblinding.json"])
    if mapping["public_packet_sha256"] != _sha256(public["public-blinded-pairs.json"]):
        raise ValueError("private mapping does not bind the public packet hash")


def _check_viewer(output: Path) -> None:
    script = r'''
const fs=require("node:fs"),assert=require("node:assert/strict"),{JSDOM}=require("jsdom");
(async()=>{
  const [htmlPath,packetPath]=process.argv.slice(1),packet=JSON.parse(fs.readFileSync(packetPath,"utf8"));
  const dom=new JSDOM(fs.readFileSync(htmlPath,"utf8"),{runScripts:"dangerously",pretendToBeVisual:true});
  const app=dom.window.__blindReplay;
  assert.ok(app,"viewer API loaded");
  app.load(packet);
  assert.equal(dom.window.document.querySelectorAll(".side").length,2,"both sides rendered");
  assert.match(dom.window.document.getElementById("state-A").textContent,new RegExp(`/\\s*${packet.pairs[0].side_a.frame_count}\\s*\\|`),"trace frame_count rendered");
  assert.ok(dom.window.document.getElementById("text-A").querySelector(".selection,.caret"),"selection geometry rendered");
  let selectionCase;
  packet.pairs.some((pair,pairIndex)=>["A","B"].some(side=>{const frame=pair[`side_${side.toLowerCase()}`].frames.find(item=>item.selection_start<item.selection_end);if(frame){selectionCase={pairIndex,side,frame};return true}return false}));
  assert.ok(selectionCase,"packet contains a ranged selection");
  dom.window.document.querySelector(`[data-pair="${selectionCase.pairIndex}"]`).click();
  app.seek(selectionCase.frame.relative_ms);
  assert.equal(dom.window.document.getElementById(`text-${selectionCase.side}`).querySelector(".selection").textContent.length,selectionCase.frame.selection_end-selectionCase.frame.selection_start,"ranged selection highlighted");
  dom.window.document.querySelector('[data-pair="0"]').click();
  const second=packet.pairs[0].side_a.frames[1];
  app.seek(second.relative_ms);
  assert.match(dom.window.document.getElementById("state-A").textContent,new RegExp(`frame\\s+${second.frame_index}/`),"timestamp seek advanced frame");
  const before=app.state().clock;
  app.play();
  await new Promise(resolve=>dom.window.setTimeout(resolve,60));
  assert.ok(app.state().clock>before,"play advanced timestamp clock");
  app.pause();
  assert.equal(app.state().playing,false,"pause stopped replay");
  app.restart();
  assert.equal(app.state().clock,0,"restart reset replay");
  dom.window.close();
  console.log("viewer-contract-ok");
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    result = subprocess.run(
        ["node", "-e", script, str(output / "viewer.html"), str(output / "public-blinded-pairs.json")],
        cwd=ROOT / "client",
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ValueError(f"viewer contract check failed:\n{result.stderr}")
    print(result.stdout.strip())


def _write_outputs(
    output: Path,
    public_files: dict[str, bytes],
    unblinding_output: Path,
    private_files: dict[str, bytes],
    replace: bool,
) -> None:
    output, unblinding_output = _resolve_output_pair(output, unblinding_output)
    destinations = ((output, public_files, "public"), (unblinding_output, private_files, "private"))
    existing = [path for path, _, _ in destinations if path.exists()]
    if existing and not replace:
        raise FileExistsError(f"output already exists; use --replace or --check: {existing[0]}")
    if any(path.is_symlink() or not path.is_dir() for path in existing):
        raise ValueError("refusing to replace a symlink or non-directory output")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".blind-replay-", dir=output.parent) as temporary:
        root = Path(temporary)
        for _, files, name in destinations:
            stage = root / name
            stage.mkdir()
            for filename, data in files.items():
                (stage / filename).write_bytes(data)
            (stage / "SHA256SUMS").write_bytes(_checksums(files))
        for path in existing:
            shutil.rmtree(path)
        for path, _, name in destinations:
            (root / name).replace(path)


def _resolve_output_pair(output: Path, unblinding_output: Path) -> tuple[Path, Path]:
    if output.is_symlink() or unblinding_output.is_symlink():
        raise ValueError("public/private output paths must not be symlinks")
    output = output.resolve()
    unblinding_output = unblinding_output.resolve()
    if output.parent != unblinding_output.parent or output == unblinding_output:
        raise ValueError("public packet and private mapping must be distinct sibling directories")
    return output, unblinding_output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--unblinding-output", type=Path)
    parser.add_argument("--replace", action="store_true", help="replace the two owned output directories")
    parser.add_argument("--check", action="store_true", help="validate the existing deterministic packet")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.unblinding_output is None:
        unblinding_output = (
            DEFAULT_UNBLINDING_OUTPUT
            if output.resolve() == DEFAULT_OUTPUT.resolve()
            else output.with_name(f"{output.name}-unblinding")
        )
    else:
        unblinding_output = (
            args.unblinding_output
            if args.unblinding_output.is_absolute()
            else ROOT / args.unblinding_output
        )
    output, unblinding_output = _resolve_output_pair(output, unblinding_output)
    public_files, private_files = _render_files()
    if args.check:
        _verify(output, public_files, unblinding_output, private_files)
        _check_viewer(output)
        print(f"verified {output} and {unblinding_output}")
        return
    _write_outputs(output, public_files, unblinding_output, private_files, args.replace)
    print(f"wrote {output} and {unblinding_output}")


if __name__ == "__main__":
    main()
