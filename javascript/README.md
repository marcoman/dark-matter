# Dark Matter (JavaScript / Node.js)

This is the **Express** implementation of Dark Matter: same routes, sessions, server-rendered HTML (EJS), and LaunchDarkly behavior as the Python and Java apps.

## Prerequisites

- **Node.js 18+** (LTS 20 or 22 recommended). Check with `node -v`.
- **npm** (bundled with Node) for installing dependencies.
- Optional: **Docker** for container runs.
- Optional: **LaunchDarkly** SDK key for live feature flags.

## Configuration

| Variable | Purpose |
|----------|---------|
| `LAUNCHDARKLY_SDK_KEY` | LaunchDarkly server-side SDK key. If unset, the app uses default flag values. |
| `PORT` | HTTP port (default **5000**). |
| `SESSION_SECRET` or `SECRET_KEY` | Secret used to sign the session cookie (`express-session`). Defaults to a dev string; set in production. |

## Install dependencies

From the `javascript/` directory:

```bash
npm install
```

## Run (local)

```bash
npm start
```

Or with file watching during development (Node 18+):

```bash
npm run dev
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

Example with env vars:

```bash
export LAUNCHDARKLY_SDK_KEY=...
export PORT=5000
npm start
```

## Build / run (Docker)

From the `javascript/` directory:

```bash
docker build -t dark-matter-js .
docker run -p 5000:5000 -e LAUNCHDARKLY_SDK_KEY=... dark-matter-js
```

The image runs `node src/server.js` with `NODE_ENV=production`.

## Summary

| Step | Command |
|------|---------|
| Install | `npm install` |
| Run | `npm start` |
| Container | `docker build -t dark-matter-js .` then `docker run -p 5000:5000 … dark-matter-js` |

Shared product behavior and LaunchDarkly flag names are described in the [repository root README](../README.md) and in detail in [`python/README.md`](../python/README.md).
