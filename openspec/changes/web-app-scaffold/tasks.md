## 1. api/ — the OpenAPI schema as an artifact

- [ ] 1.1 Add `auto_reel_ng/api/openapi.py`: a function that builds an app from throwaway settings and
      returns `app.openapi()`, plus a `__main__` entry point writing it to stdout. No database is
      contacted (the engine is lazy) and no service is started.
- [ ] 1.2 Test in `tests/test_api_openapi.py` that the schema generates with no database reachable and
      describes the current endpoints and their response models.
- [ ] 1.3 Generate `web/openapi.json` and commit it; add the drift test asserting the committed file
      equals the freshly generated schema, failing with a message that names the disagreement.

## 2. api/ — serve the built client when present

- [ ] 2.1 Add the module-level resolver returning the checkout's `web/dist` path, and mount it in
      `create_app` **after** every router is included, only when the directory exists.
- [ ] 2.2 Test that the service starts and every endpoint works when no build is present, and that `/`
      is simply not served.
- [ ] 2.3 Test, against a monkeypatched resolver pointing at a fixture directory, that `/` returns the
      entry document, that `GET /api/v1/events`, `/healthz` and the jobs WebSocket still reach their
      handlers, and that a traversing path does not return a file from outside that directory.

## 3. web/ — the client and its toolchain

- [ ] 3.1 Scaffold `web/` — `package.json` (react, react-dom, vite, @vitejs/plugin-react, typescript,
      openapi-typescript as a dev dependency, and nothing else), `tsconfig.json`, `vite.config.ts` with
      the `/api` and WebSocket proxy to the service, `index.html`, and the entry module.
- [ ] 3.2 Add `web/node_modules/` and `web/dist/` to `.gitignore`.
- [ ] 3.3 Generate `web/src/api/schema.d.ts` from `web/openapi.json` with `openapi-typescript` and commit
      it; document the one command that regenerates both files.
- [ ] 3.4 Write the wiring-check page: fetch `GET /api/v1/events` through the generated response type and
      render the event count. No list, no styling beyond what makes it legible.
- [ ] 3.5 Verify the loop end to end against a scratch copy with symlinked clips (never
      `auto-reel-media/` itself): dev server proxying to a running `auto-reel serve`, then a built
      `web/dist` served by the service itself, with the same page working in both.

## 4. Documentation

- [ ] 4.1 Document the containerized Node commands (install, dev, build, regenerate) in `web/README.md`
      or the repo README — whichever matches where setup already lives.
- [ ] 4.2 Fold into `docs/high-level-design.md` §4.10: the schema → committed JSON → generated types →
      two checks pipeline, and that `tsc --noEmit` is the GUI v1 frontend gate with no test runner or
      browser automation.

## 5. Validation gates

- [ ] 5.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
- [ ] 5.2 `.venv/bin/python -m mypy auto_reel_ng`
- [ ] 5.3 `.venv/bin/python -m pylint auto_reel_ng`
- [ ] 5.4 `.venv/bin/python -m pytest` (podman required for `requires_db`; if unavailable, run
      `-m "not requires_db"` and say so rather than skipping silently)
- [ ] 5.5 `tsc --noEmit` in the container — the frontend gate
