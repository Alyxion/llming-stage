# 09 — Lazy KaTeX + DOMPurify

Two libraries, two buttons, two separate lazy loads. Neither library
is in the critical path. Clicking a button triggers a single
`__stage.load()` for that library — the second click is instant.

## What to notice

- The first "Render math" click fetches `katex.min.js` + `katex.min.css`.
  Subsequent clicks resolve the load promise immediately.
- "Sanitise & render" fetches DOMPurify the same way.
- The default input contains a `<script>` injection attempt; DOMPurify
  strips it.
- Pure client-side sample. No WebSocket, no session — runs from a
  static deploy just as happily.

## Run

```bash
poetry run python samples/09_markdown_render/main.py
open http://localhost:8765
```
