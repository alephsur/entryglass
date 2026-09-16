# Entryglass Web

Vue 3, TypeScript, and Vite development shell. It displays product intent, planned
steps, and a real local-API health check. It does not display wallet results.

From the repository root after setup:

```bash
npm --prefix frontend run dev
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

The browser uses a relative `/api` path. Vite proxies to the local API or to the
Docker `api` service. Never open `index.html` with `file://`; use the Vite server.
Never expose a Nansen API key through client code or Vite environment variables.

`src/features/` contains only reserved feature notes. Frontend API-client tests use
the built-in Node test runner and mock fetch; they do not verify Vue compilation,
component rendering, browser accessibility, or end-to-end behavior.

No package lockfile was fabricated. Run the initial `npm install` through setup,
verify, and commit the generated lockfile before using `npm ci`.
