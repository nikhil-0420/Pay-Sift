# PaySift UI

Forensic-ledger frontend for the supplied PaySift webhook verification data and REST backend.

## Run

```text
npm install
npm run dev
```

Vite uses strict port 5173. Create `.env.local` from `.env.example` to configure `VITE_API_BASE` or `VITE_DATA_MODE`.

- `VITE_DATA_MODE=auto` (default): probes `GET /health` at startup and uses the live API when reachable; otherwise bundled snapshot mode.
- `VITE_DATA_MODE=live`: require the API.
- `VITE_DATA_MODE=static`: never contact the API; works offline.

Against the existing backend, from the backend repository root run `python cli.py serve`; in a second terminal, from `ui/` run `npm run dev`. The API base defaults to `http://127.0.0.1:8000`. `main.py` lists permitted CORS origins `localhost`/`127.0.0.1` on ports 5173 and 3000.

## Data maintenance

From `ui/`, `npm run sync-data -- --src ..` copies from the project root; with a backend repo whose directories are `runs/`, `contract/`, and `pilot/`, use `npm run sync-data -- --src ../..` as appropriate. Missing source files are skipped with a warning. Then run `npm run gen:types` and `npm run check:contract`.

`npm run check:contract` validates bundled real run files against the supplied JSON schema. `npm run check:api` calls the endpoints described in `main.py`, including live break and repair requests. `npm run verify` runs typecheck, offline tests, contract validation and production build. `npm run build` creates `dist/`; `npm run preview` serves it.

## Windows troubleshooting

Use a current Node.js LTS and PowerShell/Command Prompt; all project scripts are Node-based. If port 5173 is busy, stop the other process or choose the permitted 3000 origin only after updating the dev script and CORS configuration. Do not silently disable `strictPort`. If API requests fail, check `VITE_API_BASE`, start the backend on port 8000, and ensure its CORS list includes the frontend origin. Static mode does not require Python/backend. For missing fonts, reinstall npm packages; fonts are bundled locally, with no CDN dependency.
