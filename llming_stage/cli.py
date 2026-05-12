"""Command line tools for no-Python llming-stage apps."""

from __future__ import annotations

import argparse
from pathlib import Path

from .stage import Stage

_VIEW_EXTENSIONS = {".vue", ".html", ".htm", ".js"}

def build_app(root: Path, *, dev: bool = True):
    title = _title_for_root(root)
    if root.is_file():
        stage = Stage(root=root.parent, title=title, dev=dev)
        stage.add_view("/", root)
        return stage.app

    views = root / "views"
    stage = Stage(root=root, title=title, dev=dev)
    if views.is_dir():
        stage.discover(views)
        return stage.app

    view_files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in _VIEW_EXTENSIONS
    )
    if len(view_files) == 1:
        stage.add_view("/", view_files[0])
    else:
        stage.discover(root)
    return stage.app


def _title_for_root(root: Path) -> str:
    raw = root.stem if root.is_file() else root.name
    text = raw.replace("_", " ").replace("-", " ").strip()
    return text[:1].upper() + text[1:] if text else "llming"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llming-stage")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="serve a no-Python stage app")
    serve.add_argument("root", nargs="?", default=".")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    build = sub.add_parser("build", help="build a static no-Python stage app")
    build.add_argument("root", nargs="?", default=".")
    build.add_argument("--out", default="dist")

    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.cmd == "serve":
        try:
            import uvicorn
        except ImportError as exc:
            raise SystemExit(
                "llming-stage serve requires uvicorn. Install it with `pip install uvicorn`."
            ) from exc
        uvicorn.run(build_app(root, dev=True), host=args.host, port=args.port)
        return 0

    app = build_app(root, dev=False)
    stage = getattr(app.state, "llming_stage_instance")
    stage.build(Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
