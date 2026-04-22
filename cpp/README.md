# Dark Matter (C++)

This is a **C++** implementation of Dark Matter, intended for Linux (Ubuntu) development.

It mirrors the same routes as the Python/Java/JavaScript versions:

- `/` (login)
- `/upper-left`, `/upper-right`, `/lower-left`, `/lower-right`
- `/nav/go/{up|down|left|right}`
- `/about`
- `/api/ui-color-mode`, `/api/inline-about-load`

## Prerequisites (Ubuntu 24.04+)

Install build tooling and headers:

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  cmake \
  git \
  libasio-dev \
  zlib1g-dev
```

Notes:
- Crow uses **standalone Asio** on Linux; `libasio-dev` provides the headers.
- `zlib1g-dev` is optional for this app (compression is off), but is commonly present for C++ builds.

## Build

From the repository root:

```bash
cd cpp
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

The binary will be at `cpp/build/dark-matter-cpp`.

## Run

```bash
cd cpp
export PORT=5000
./build/dark-matter-cpp
```

Open `http://127.0.0.1:5000`.

## Configuration

This version uses environment variables for feature flags (to keep the build self-contained):

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `5000` | HTTP port |
| `MAM_ABOUT` | `false` | show/hide About page |
| `MAM_BG_COLOR` | `white` | banner background color |
| `MAM_TOGGLE_CASE` | `false` | show/hide case toggle button |
| `MAM_DARK_MODE` | `false` | enable nav-area dark-mode toggle |
| `MAM_INLINE_ABOUT` | `false` | show/hide inline About block |

Example:

```bash
export MAM_ABOUT=true
export MAM_BG_COLOR=lightblue
export MAM_TOGGLE_CASE=true
export MAM_DARK_MODE=true
export MAM_INLINE_ABOUT=true
./build/dark-matter-cpp
```

## Docker

From the `cpp/` directory:

```bash
docker build -t dark-matter-cpp .
docker run -p 5000:5000 dark-matter-cpp
```

## Notes

- This uses an **in-memory session store** and is not production-hardened.
- The flag names and event keys match the other implementations so LaunchDarkly wiring can be added later.
