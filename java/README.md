# Dark Matter (Java)

This is the **Spring Boot** implementation of Dark Matter: same URLs, session behavior, Thymeleaf UI, and LaunchDarkly integration as the Python app.

## Prerequisites

- **JDK 21** (OpenJDK distribution). This repo includes a [SDKMAN](https://sdkman.io/) [`.sdkmanrc`](.sdkmanrc) that pins **Eclipse Temurin 21** (`21.0.5-tem`), a widely used OpenJDK build.
- **Maven** is optional if you use the included **Maven Wrapper** (`./mvnw`).
- Optional: **Docker**, for running the app in a container.
- Optional: a **LaunchDarkly** environment and **SDK key** for live feature flags.

### JDK with SDKMAN (recommended)

From the `java/` directory:

```bash
sdk env install   # first time: installs the Java version from .sdkmanrc
sdk env           # use pinned Java in this shell
java -version
```

If you prefer to install manually: `sdk install java 21.0.5-tem` (or another Temurin 21.x build), then `sdk use java 21.0.5-tem`.

## Configuration

The app reads configuration from the environment (and `application.properties` defaults).

| Variable | Purpose |
|----------|---------|
| `LAUNCHDARKLY_SDK_KEY` | LaunchDarkly server-side SDK key. If unset, the app runs with default flag values (same idea as the Python app). |
| `PORT` | HTTP port (default **5000**, matching the Python app). Spring maps this to `server.port`. |
| `SECRET_KEY` | Not used by Spring Boot the same way as Flask; session cookies use the default servlet session setup. For production, configure session hardening separately (e.g. Spring Session, secure cookie flags). |

## Build

From the `java/` directory, using the wrapper (no global Maven required):

```bash
./mvnw -DskipTests package
```

The runnable JAR is `target/dark-matter-1.0.0-SNAPSHOT.jar`.

## Run

### Local (JAR)

After a successful package:

```bash
export LAUNCHDARKLY_SDK_KEY=...   # optional
export PORT=5000                  # optional
java -jar target/dark-matter-1.0.0-SNAPSHOT.jar
```

Or run the main class without packaging:

```bash
./mvnw spring-boot:run
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

### Docker

From the `java/` directory (build context is the current folder):

```bash
docker build -t dark-matter-java .
docker run -p 5000:5000 -e LAUNCHDARKLY_SDK_KEY=... dark-matter-java
```

## Summary

| Step | Command |
|------|---------|
| Use pinned JDK | `sdk env` (from `java/`) |
| Build | `./mvnw -DskipTests package` |
| Run | `java -jar target/dark-matter-1.0.0-SNAPSHOT.jar` or `./mvnw spring-boot:run` |
| Container | `docker build -t dark-matter-java .` then `docker run -p 5000:5000 … dark-matter-java` |

For feature flags, navigation behavior, and LaunchDarkly events shared with the Python app, see the [repository root README](../README.md) and the [Python README](../python/README.md).
