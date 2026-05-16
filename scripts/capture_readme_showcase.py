#!/usr/bin/env python3
"""Capture an animated WebP showcase for the top-level README.

The script starts selected samples one at a time, records short
Playwright frame sequences, and stitches them into a compact animated
WebP suitable for GitHub and PyPI project pages. Requires the WebP
tools (`img2webp`) and Playwright's Chromium browser.

Usage:
    poetry run python scripts/capture_readme_showcase.py
"""

from __future__ import annotations

import argparse
import os
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


SCENES: dict[str, Scene] = {
    "three_scene": Scene(
        name="three_scene",
        route="/",
        wait=3.0,
        duration=2.0,
        selector="#scene-canvas",
        actions=(
            TimedAction(
                0.8,
                lambda page: page.mouse.wheel(0, -280),
            ),
        ),
    ),
    "analytics_dashboard": Scene(
        name="analytics_dashboard",
        route="/",
        wait=3.2,
        duration=1.8,
        selector="#chart-line canvas",
        actions=(
            TimedAction(
                0.7,
                lambda page: page.get_by_text("Compare YoY").click(timeout=1500),
            ),
            TimedAction(
                1.5,
                lambda page: page.get_by_text("Refresh").click(timeout=1500),
            ),
        ),
    ),
    "plotly_advanced": Scene(
        name="plotly_advanced",
        route="/",
        wait=4.0,
        duration=1.6,
        selector="#chart-surface",
    ),
    "extension_workbench": Scene(
        name="extension_workbench",
        route="/",
        wait=4.0,
        duration=1.5,
        selector="#terminal .xterm",
    ),
    "capstone_dashboard": Scene(
        name="capstone_dashboard",
        route="/metric",
        wait=2.5,
        duration=1.8,
        selector="#chart",
        actions=(
            TimedAction(
                0.2,
                lambda page: page.get_by_role("button", name="Start").click(timeout=1500),
            ),
        ),
    ),
    "markdown_render": Scene(
        name="markdown_render",
        route="/",
        wait=1.2,
        duration=1.4,
        selector="#out",
        actions=(
            TimedAction(
                0.1,
                lambda page: page.locator("#render-math").click(timeout=1500),
            ),
            TimedAction(
                0.8,
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


def save_webp(
    frame_dir: Path,
    frame_count: int,
    output: Path,
    fps: int,
    quality: int,
) -> None:
    if frame_count <= 0:
        raise RuntimeError("no frames captured")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "-loop",
        "0",
        "-kmax",
        str(max(1, fps)),
        "-mixed",
    ]
    duration = int(1000 / fps)
    for i in range(frame_count):
        command.extend(
            [
                "-d",
                str(duration),
                "-lossy",
                "-q",
                str(quality),
                "-m",
                "6",
                str(frame_dir / f"frame_{i:04d}.png"),
            ]
        )
    command.extend(["-o", str(output)])
    subprocess.run(
        ["img2webp", *command],
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
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--quality", type=int, default=74)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    names = [name.strip() for name in args.samples.split(",") if name.strip()]
    unknown = [name for name in names if name not in SCENES]
    if unknown:
        known = ", ".join(sorted(SCENES))
        raise SystemExit(f"unknown sample(s): {', '.join(unknown)}; known: {known}")

    with tempfile.TemporaryDirectory(prefix="llming-stage-showcase-") as tmp:
        frame_dir = Path(tmp)
        frame_count = 0
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(
                viewport={"width": args.width, "height": args.height},
                device_scale_factor=1,
            )
            try:
                for name in names:
                    scene = SCENES[name]
                    port = pick_free_port()
                    print(f"capturing {scene.name} on :{port}")
                    proc = start_sample(scene, port)
                    try:
                        scene_frames = capture_scene(
                            page,
                            scene,
                            base_url=f"http://127.0.0.1:{port}",
                            fps=args.fps,
                            frame_dir=frame_dir,
                            start_index=frame_count,
                        )
                        frame_count += scene_frames
                        print(f"  {scene_frames} frames")
                    finally:
                        stop_process(proc)
            finally:
                browser.close()

        save_webp(frame_dir, frame_count, args.output, args.fps, args.quality)
    size_mb = args.output.stat().st_size / (1024 * 1024)
    print(f"saved {args.output} ({frame_count} frames, {size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
