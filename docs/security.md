# Security

Path traversal is the main attack surface for any static-asset server.
`llming-stage` applies the same hardening to every route it mounts.

## Enforced invariants

1. **Whitelist-only routing.** Every route maps to one fixed root
   directory or one opened zip archive. There is no catch-all static
   mount and no user-controlled root.

2. **Textual pre-filter.** Before any filesystem or archive access, the
   requested path is rejected if it:
   - is empty, starts with `/`, or contains `\\`
   - contains a null byte (`\x00`), any ASCII control character
     (`< 0x20` or `0x7F`), or a backslash
   - contains any `..` substring
   - has any empty, `.`, or `..` path segment

3. **Extension whitelist.** Only these extensions are ever served:
   `.js`, `.mjs`, `.css`, `.woff2`, `.svg`, `.json`. A request for any
   other extension returns 404 immediately.

4. **Path canonicalization.** The request path is resolved against the
   route's root with `Path.resolve()`. The resolved path is verified to
   be a descendant of the root:

   ```python
   resolved = (root / rel).resolve()
   resolved.relative_to(root.resolve())   # raises ValueError if outside
   ```

5. **Symlink rejection.** For each path component, if any component is a
   symlink and its target resolves outside the route root, the request
   is rejected.

6. **Directory requests return 404.** Only regular files are served. No
   directory listing is ever produced.

7. **Zip entry validation.** When a zip archive is opened, its entries
   are filtered through the same textual checks and extension whitelist.
   An entry whose name fails validation is *silently dropped* from the
   whitelist — it cannot be requested even with a crafted URL.

8. **Archive reads stay in memory.** Zip entries are served via
   `ZipFile.read(name)` directly into an HTTP response body.
   `ZipFile.extract()` is never called.

9. **Single failure mode.** Every rejection returns 404 — never 403.
   This avoids disclosing whether a path exists, is forbidden, or is
   malformed.

## What this does not protect against

- **Egress attacks.** Vendor JavaScript is not re-reviewed for each
  release; `THIRD_PARTY.md` lists sources so operators can audit them.
- **Cache poisoning via upstream compromise.** Assets are served with
  `Cache-Control: public, max-age=31536000, immutable`, so a bad wheel
  release persists in browsers until a version bump. Rotate the wheel
  version if any bundled asset has to be urgently replaced.
- **Content Security Policy.** `llming-stage` does not set a CSP header.
  The host app is responsible for setting a CSP appropriate to its
  deployment.

## Reporting vulnerabilities

Please report suspected vulnerabilities via a private security advisory
on GitHub (<https://github.com/Alyxion/llming-stage/security/advisories>).
Do **not** open a public GitHub issue for unpatched vulnerabilities.
