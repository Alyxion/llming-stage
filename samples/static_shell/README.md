# Static shell

The absolute minimum. One FastAPI app, one shell, one view.
No llming-com import, no session, no WebSocket. The Python server
exists only to serve files.

## Run

```bash
poetry run python samples/static_shell/main.py
open http://localhost:8765
```
