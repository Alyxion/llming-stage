"""Command line tools for no-Python llming-stage apps."""

from __future__ import annotations

import argparse
from pathlib import Path

from starlette.applications import Starlette

from .stage import Stage


def build_app(root: Path, *, dev: bool = True) -> Starlette:
    app = Starlette()
    views = root / "views"
    stage = Stage(app, root=root, dev=dev)
    stage.discover(views if views.is_dir() else root)
    return app


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
