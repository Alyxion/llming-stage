#!/usr/bin/env python3
"""Capture an animated WebP showcase for the top-level README.

The script starts selected samples one at a time, records short
Playwright frame sequences, fades between scenes, and stitches them
into a compact animated WebP suitable for GitHub and PyPI project pages.
Requires the WebP tools (`cwebp` and `webpmux`) and Playwright's
Chromium browser.

Usage:
    poetry run python scripts/capture_readme_showcase.py
"""

from __future__ import annotations

import argparse
import base64
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from playwright.sync_api import Page, sync_playwright


REPO = Path(__file__).resolve().parent.parent
SAMPLES = REPO / "samples"
VIEW_EXTENSIONS = {".vue", ".html", ".htm", ".js"}
DEFAULT_OUTPUT = REPO / "media" / "readme-showcase.webp"


@dataclass(frozen=True)
class TimedAction:
    at: float
    run: Callable[[Page], None]


@dataclass(frozen=True)
class Scene:
    name: str
    wait: float
    duration: float
    selector: str
    route: str = "/"
    actions: tuple[TimedAction, ...] = field(default_factory=tuple)


def walk_echarts_tooltip(page: Page, chart_id: str, *, interval_ms: int = 180) -> None:
    page.evaluate(
        """
        ({ chartId, intervalMs }) => {
          const chart = window.echarts?.getInstanceByDom(document.getElementById(chartId));
          if (!chart) return;
          const option = chart.getOption();
          const points = option.series?.[0]?.data?.length || 1;
          let dataIndex = 0;
          window.__showcaseTimers ??= [];
          const timer = window.setInterval(() => {
            chart.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex });
            chart.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex });
            if (dataIndex > 0) {
              chart.dispatchAction({
                type: 'downplay',
                seriesIndex: 0,
                dataIndex: dataIndex - 1,
              });
            }
            dataIndex = (dataIndex + 1) % points;
          }, intervalMs);
          window.__showcaseTimers.push(timer);
        }
        """,
        {"chartId": chart_id, "intervalMs": interval_ms},
    )


def orbit_plotly_surface(page: Page, chart_id: str, *, interval_ms: int = 80) -> None:
    page.evaluate(
        """
        ({ chartId, intervalMs }) => {
          const chart = document.getElementById(chartId);
          if (!chart || !window.Plotly) return;
          let angle = 0;
          window.__showcaseTimers ??= [];
          const timer = window.setInterval(() => {
            angle += 0.035;
            window.Plotly.relayout(chart, {
              'scene.camera.eye': {
                x: 1.6 * Math.cos(angle),
                y: 1.6 * Math.sin(angle),
                z: 0.95,
              },
            });
          }, intervalMs);
          window.__showcaseTimers.push(timer);
        }
        """,
        {"chartId": chart_id, "intervalMs": interval_ms},
    )


SCENES: dict[str, Scene] = {
    "three_scene": Scene(
        name="three_scene",
        route="/",
        wait=3.0,
        duration=3.0,
        selector="#scene-canvas",
    ),
    "analytics_dashboard": Scene(
        name="analytics_dashboard",
        route="/",
        wait=3.2,
        duration=3.0,
        selector="#chart-line canvas",
        actions=(
            TimedAction(
                0.3,
                lambda page: walk_echarts_tooltip(page, "chart-line"),
            ),
        ),
    ),
    "plotly_advanced": Scene(
        name="plotly_advanced",
        route="/",
        wait=4.5,
        duration=3.0,
        selector="#chart-surface",
        actions=(
            TimedAction(
                0.2,
                lambda page: orbit_plotly_surface(page, "chart-surface"),
            ),
        ),
    ),
    "extension_workbench": Scene(
        name="extension_workbench",
        route="/",
        wait=4.0,
        duration=2.0,
        selector="#terminal .xterm",
    ),
    "capstone_dashboard": Scene(
        name="capstone_dashboard",
        route="/metric",
        wait=2.5,
        duration=3.0,
        selector="#chart",
        actions=(
            TimedAction(
                0.4,
                lambda page: page.get_by_role("button", name="Start").click(timeout=1500),
            ),
        ),
    ),
    "markdown_render": Scene(
        name="markdown_render",
        route="/",
        wait=1.2,
        duration=1.8,
        selector="#out",
        actions=(
            TimedAction(
                0.4,
                lambda page: page.locator("#render-math").click(timeout=1500),
            ),
            TimedAction(
                1.2,
                lambda page: page.locator("#render-html").click(timeout=1500),
            ),
        ),
    ),
}


def pick_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def wait_port(port: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_open(port):
            return
        time.sleep(0.15)
    raise RuntimeError(f"server never accepted connections on :{port}")


def sample_command(sample_dir: Path, port: int) -> list[str]:
    main_py = sample_dir / "main.py"
    if main_py.is_file():
        return [sys.executable, str(main_py)]
    if any(p.suffix.lower() in VIEW_EXTENSIONS for p in sample_dir.iterdir() if p.is_file()):
        return [
            sys.executable,
            "-m",
            "llming_stage.cli",
            "serve",
            str(sample_dir),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
    raise FileNotFoundError(f"{sample_dir} is not a runnable sample")


def start_sample(scene: Scene, port: int) -> subprocess.Popen:
    sample_dir = SAMPLES / scene.name
    env = {
        **os.environ,
        "PORT": str(port),
        "STAGE_RELOAD": "0",
        "LLMING_STAGE_DEBUG": "1",
    }
    proc = subprocess.Popen(
        sample_command(sample_dir, port),
        cwd=str(REPO),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    try:
        wait_port(port)
    except Exception:
        proc.terminate()
        out = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
        raise RuntimeError(f"{scene.name} failed to start:\n{out}")
    return proc


def stop_process(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def capture_scene(
    page: Page,
    scene: Scene,
    *,
    base_url: str,
    fps: int,
    frame_dir: Path,
    start_index: int,
) -> int:
    route = scene.route if scene.route.startswith("/") else "/" + scene.route
    separator = "&" if "?" in route else "?"
    page.goto(f"{base_url}{route}{separator}stage_dark=1", wait_until="domcontentloaded")
    page.wait_for_selector(scene.selector, timeout=30_000)
    page.wait_for_timeout(int(scene.wait * 1000))

    frame_count = max(1, int(scene.duration * fps))
    frame_delay = 1.0 / fps
    pending_actions = list(scene.actions)
    start = time.monotonic()

    for i in range(frame_count):
        elapsed = time.monotonic() - start
        while pending_actions and elapsed >= pending_actions[0].at:
            action = pending_actions.pop(0)
            try:
                action.run(page)
            except Exception as exc:
                print(f"  action skipped for {scene.name}: {exc}")
        page.screenshot(
            path=str(frame_dir / f"frame_{start_index + i:04d}.png"),
            type="png",
            full_page=False,
        )
        spent = time.monotonic() - start - elapsed
        time.sleep(max(0.0, frame_delay - spent))

    return frame_count


def append_scene_frames(
    source_dir: Path,
    source_count: int,
    output_dir: Path,
    start_index: int,
) -> int:
    for i in range(source_count):
        shutil.copyfile(
            source_dir / f"frame_{i:04d}.png",
            output_dir / f"frame_{start_index + i:04d}.png",
        )
    return source_count


def append_transition_frames(
    page: Page,
    *,
    from_frame: Path,
    to_frame: Path,
    output_dir: Path,
    start_index: int,
    fps: int,
    duration: float,
) -> int:
    frame_count = max(0, int(duration * fps))
    if frame_count <= 0:
        return 0

    from_src = base64.b64encode(from_frame.read_bytes()).decode("ascii")
    to_src = base64.b64encode(to_frame.read_bytes()).decode("ascii")
    page.set_content(
        f"""
        <!doctype html>
        <html>
          <head>
            <style>
              html, body {{
                margin: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                background: #0b1020;
              }}
              img {{
                position: fixed;
                inset: 0;
                width: 100vw;
                height: 100vh;
                object-fit: cover;
              }}
            </style>
          </head>
          <body>
            <img id="from" src="data:image/png;base64,{from_src}" alt="">
            <img id="to" src="data:image/png;base64,{to_src}" alt="">
          </body>
        </html>
        """,
        wait_until="load",
    )
    page.wait_for_function(
        """
        () => [...document.images].every(
          (img) => img.complete && img.naturalWidth > 0
        )
        """
    )
    for i in range(frame_count):
        progress = (i + 1) / (frame_count + 1)
        # Smoothstep keeps scene changes from looking like a dropped frame.
        alpha = progress * progress * (3 - 2 * progress)
        page.evaluate(
            """
            (alpha) => {
              document.getElementById('from').style.opacity = String(1 - alpha);
              document.getElementById('to').style.opacity = String(alpha);
            }
            """,
            alpha,
        )
        page.screenshot(
            path=str(output_dir / f"frame_{start_index + i:04d}.png"),
            type="png",
            full_page=False,
        )
    return frame_count


def save_webp(
    frame_dir: Path,
    frame_count: int,
    output: Path,
    fps: int,
    quality: int,
    width: int,
    height: int,
) -> None:
    if frame_count <= 0:
        raise RuntimeError("no frames captured")
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = int(1000 / fps)
    webp_dir = frame_dir / "encoded-webp"
    webp_dir.mkdir()
    for i in range(frame_count):
        png_frame = frame_dir / f"frame_{i:04d}.png"
        webp_frame = webp_dir / f"frame_{i:04d}.webp"
        subprocess.run(
            [
                "cwebp",
                "-quiet",
                "-q",
                str(quality),
                "-m",
                "6",
                "-exact",
                "-resize",
                str(width),
                str(height),
                str(png_frame),
                "-o",
                str(webp_frame),
            ],
            check=True,
            cwd=str(REPO),
        )

    command: list[str] = []
    for i in range(frame_count):
        webp_frame = webp_dir / f"frame_{i:04d}.webp"
        # Use full-canvas frames with no WebP animation blending. This keeps
        # crossfades intentional and prevents stale pixels from prior scenes.
        command.extend(["-frame", str(webp_frame), f"+{duration}+0+0+1-b"])
    command.extend(["-loop", "0", "-bgcolor", "255,11,16,32", "-o", str(output)])
    subprocess.run(
        ["webpmux", *command],
        check=True,
        cwd=str(REPO),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--samples",
        default=(
            "three_scene,analytics_dashboard,plotly_advanced,"
            "extension_workbench,capstone_dashboard,markdown_render"
        ),
        help="Comma-separated sample names to capture.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument(
        "--capture-scale",
        type=float,
        default=2.0,
        help="Browser viewport multiplier before downsampling to width/height.",
    )
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--quality", type=int, default=70)
    parser.add_argument("--transition-duration", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    names = [name.strip() for name in args.samples.split(",") if name.strip()]
    unknown = [name for name in names if name not in SCENES]
    if unknown:
        known = ", ".join(sorted(SCENES))
        raise SystemExit(f"unknown sample(s): {', '.join(unknown)}; known: {known}")
    if args.fps <= 0:
        raise SystemExit("--fps must be greater than zero")
    if args.width <= 0 or args.height <= 0:
        raise SystemExit("--width and --height must be greater than zero")
    if args.capture_scale < 1:
        raise SystemExit("--capture-scale must be at least 1")
    if args.transition_duration < 0:
        raise SystemExit("--transition-duration must not be negative")
    capture_width = int(round(args.width * args.capture_scale))
    capture_height = int(round(args.height * args.capture_scale))

    with tempfile.TemporaryDirectory(prefix="llming-stage-showcase-") as tmp:
        tmp_dir = Path(tmp)
        frame_dir = tmp_dir / "frames"
        frame_dir.mkdir()
        frame_count = 0
        previous_last_frame: Path | None = None
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(
                viewport={"width": capture_width, "height": capture_height},
                device_scale_factor=1,
            )
            try:
                for name in names:
                    scene = SCENES[name]
                    port = pick_free_port()
                    print(f"capturing {scene.name} on :{port}")
                    scene_dir = tmp_dir / f"scene-{scene.name}"
                    scene_dir.mkdir()
                    proc = start_sample(scene, port)
                    try:
                        scene_frames = capture_scene(
                            page,
                            scene,
                            base_url=f"http://127.0.0.1:{port}",
                            fps=args.fps,
                            frame_dir=scene_dir,
                            start_index=0,
                        )
                    finally:
                        stop_process(proc)

                    if scene_frames <= 0:
                        print("  no frames")
                        continue

                    first_scene_frame = scene_dir / "frame_0000.png"
                    if previous_last_frame is not None:
                        transition_frames = append_transition_frames(
                            page,
                            from_frame=previous_last_frame,
                            to_frame=first_scene_frame,
                            output_dir=frame_dir,
                            start_index=frame_count,
                            fps=args.fps,
                            duration=args.transition_duration,
                        )
                        frame_count += transition_frames
                        print(f"  {transition_frames} transition frames")

                    appended_frames = append_scene_frames(
                        scene_dir,
                        scene_frames,
                        frame_dir,
                        frame_count,
                    )
                    frame_count += appended_frames
                    previous_last_frame = frame_dir / f"frame_{frame_count - 1:04d}.png"
                    print(f"  {scene_frames} scene frames")
            finally:
                browser.close()

        save_webp(
            frame_dir,
            frame_count,
            args.output,
            args.fps,
            args.quality,
            args.width,
            args.height,
        )
    size_mb = args.output.stat().st_size / (1024 * 1024)
    print(f"saved {args.output} ({frame_count} frames, {size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
