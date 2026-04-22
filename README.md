# Dark Matter

This repository contains **two implementations** of the same web application:

| Directory | Stack |
|-----------|--------|
| [`python/`](python/) | Flask, Jinja2 templates, LaunchDarkly Python SDK |
| [`java/`](java/) | Spring Boot, Thymeleaf, LaunchDarkly Java SDK |

Both apps expose the same routes and product behavior: name-only login, four-corner compass navigation, optional About page, banner styling and experiments driven by **LaunchDarkly** feature flags, and browser-reported metrics for experiments (e.g. nav theme, inline About load time).

## Shared behavior

- **Login**: POST `/` with `name`; session holds the user’s display name and navigation state.
- **Pages**: `/upper-left`, `/upper-right`, `/lower-left`, `/lower-right`, `/about` (About is only reachable when the **`MAM_ABOUT`** flag is on).
- **Navigation**: GET `/nav/go/{up|down|left|right}` validates moves on a fixed grid and emits LaunchDarkly **`nav_click_*`** events with `from_page` / `to_page`.
- **APIs**: `POST /api/ui-color-mode` and `POST /api/inline-about-load` support experiments (same JSON shape in both stacks).
- **Configuration**: `LAUNCHDARKLY_SDK_KEY` enables live flags; if it is missing, flags fall back to safe defaults. Default HTTP port is **5000** (`PORT`).

Feature flag names and event keys are documented in detail in [`python/README.md`](python/README.md) (LaunchDarkly tables and metrics).

## Documentation by language

- **[`python/README.md`](python/README.md)** — Flask setup, `pip` / venv, eval script, Docker image under `python/`.
- **[`java/README.md`](java/README.md)** — SDKMAN/JDK 21, Maven Wrapper, Spring Boot run and Docker image under `java/`.

Choose one implementation to run locally; you do not need both runtimes unless you are developing or comparing stacks.
