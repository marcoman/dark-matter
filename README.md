# Dark Matter

Welcome to my humble project.  This is a simple Flask application with multi-page navigation and LaunchDarkly feature flags. 

You log in with your name only (no password), then move between four pages (upper-left, upper-right, lower-left, lower-right) using "Right", "Left", "Up", and "Down" links. 

I am implementing a few feature flags and other capabilities per the LD capabilities.  For example: 
- Feature flags control whether an "About" page is visible 
- The top banner background color (main page area stays white).
- Others TBD

## What this application does

- **Login**: Enter your name on the login page; no password is required.
- **Navigation**: After login you land on **Upper Left**. From there you can go **Right** (to Upper Right) or **Down** (to Lower Left). Each of the four corners has two links that follow the same grid (left/right and up/down). Clicks are routed through `/nav/go/...` so LaunchDarkly can record custom events for metrics.
- **Upper Left** → Right: Upper Right; Down: Lower Left  
- **Upper Right** → Left: Upper Left; Down: Lower Right  
- **Lower Left** → Right: Lower Right; Up: Upper Left  
- **Lower Right** → Up: Upper Right; Left: Lower Left  
- Every page shows your name, a logout button, and “from where you came from.”
- **Logout** clears the session and returns you to the login page.

## Feature flags (LaunchDarkly)

- **MAM_ABOUT** (boolean): When enabled, an “About” link appears and the About page is accessible. That page shows the application name, system details (Python version, OS, memory, CPU), the author name, and the libraries used.
- **MAM_BG_COLOR**: Sets the background color of the **top banner** (welcome, Logout, About when shown, case toggle when shown). The main navigation area stays **white**. Default is `white`; use standard HTML color names (e.g. `lightgray`, `lightblue`).
- **MAM_TOGGLE_CASE** (boolean): When enabled, a button appears on navigation pages to toggle compass link labels between lower and upper case (for experiments).

The LaunchDarkly SDK key is read from the environment variable **`LAUNCHDARKLY_SDK_KEY`**.

### Navigation custom events (metrics)

Compass clicks go through **`GET /nav/go/<direction>`** (`up`, `down`, `left`, `right`). Each valid click sends a LaunchDarkly custom event via `LDClient.track()`:

| Event key | When it fires |
|-----------|----------------|
| `nav_click_up` | User chose **Up** from a page where that move is allowed |
| `nav_click_down` | User chose **Down** |
| `nav_click_left` | User chose **Left** |
| `nav_click_right` | User chose **Right** |

Each `nav_click_*` event includes `data`: `from_page`, `to_page` (slugs like `upper-left`).

Case preference is **not** attached to compass clicks anymore. Use the toggle event instead:

| Event key | When it fires |
|-----------|----------------|
| `nav_case_toggle_clicked` | User clicked **switch->CASE** / **SWITCH->case** (only when `MAM_TOGGLE_CASE` is enabled) |

`nav_case_toggle_clicked` includes `data`: `previous_case`, `new_case` (`lower` or `upper`), and `from_page`.

**Event filters in LaunchDarkly:** reference custom data fields on the event (e.g. `new_case`, `from_page`) depending on your UI; naming often matches the keys sent in `track(..., data={...})`.

In LaunchDarkly, create **custom metrics** that count these event keys (e.g. one per `nav_click_*` direction, plus one for `nav_case_toggle_clicked`). Attach them to your experiment as needed.

---

## My Stack
I developed this code on a Win11 machine with WSL enabled.
The primary OS is Ubuntu 24.
Python verison 3.12.3
Virtual env.

## Prompt used to create this application

This is not the only prompt, but rather the first one that got things started.

> Let's create a python application named "dark-matter"
>
> This is a python application that uses flask.
> When you build this application, include a @README.md that tells the user what the application is about, and the prompt that I used. Also include instructions for how to build the application.
>
> The application can run from the command line with python 3. The application can also run from a docker container.
> include a multi-stage docker build that creates an image.
> Include a requirements.txt file with the necessary dependencies.
> Please use LaunchDarkly for python to enable feature flags.
> The application is a simple flask application with multiple pages.
> Start by asking the person for their login, which is only their name. There is no password.
> When they log in, they are taken to a page, which we'll call upper-left. The navigation options are "right" or "down." Right takes you to upper-right, and down takes you to lower-left.
> Lower-left has two navigation options: right, and up. Right takes you to lower-right, and up takes you to upper-left.
> lower-right has two navigation options: up and left. Up takes you to upper-right, left takes you to lower-left.
> Upper-right has two navigation options: left and down. Left takes you to upper-left, and down takes you to lower-right.
> All pages display your name, and a logout button.
> All pages also display from where you came from.
> Logout starts all over.
> Let's have a few feature flags:
> - One feature flag toggles the state of the "about" page, which will display the name of the application, plus details about the underlying system such as python version, OS, memory, and other interesting details. Also include the name of the author and the libraries used within. This is a boolean value. This flag is named MAM_ABOUT.
> - Another feature flag changes the default background color. The default is "white" and the options are standard HTML values by name. This flag is named MAM_BG_COLOR.
> The Launchdarkly API token is named LAUNCHCDARKLY_SDK_KEY.

---

## How to build and run

### Prerequisites

- Python 3.10+ (or 3.12 for Docker)
- Optional: Docker (for container run)
- Optional: LaunchDarkly project and SDK key for feature flags

### Environment variables:

I use these envvars to direct my application.  Of course, I don't have my secrets here, but I do state how big each field is.

- export LAUNCHDARKLY_SDK_KEY=sdk-8chars-4chars-4chars-4chars-12chars
- export LAUNCHDARKLY_API_KEY=api-8chars-4chars-4chars-4chars-12chars


### Run from the command line (Python 3)

1. Create a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set the LaunchDarkly SDK key (optional; if unset, flags default to off/white):
   ```bash
   export LAUNCHDARKLY_SDK_KEY=sdk-xxxx-your-key
   ```
I happen to have this envvar set up in my ~/.bashrc.

4. Run the app:
   ```bash
   python app.py
   ```
   The app listens on `http://127.0.0.1:5000`. Open that URL in your browser.

5. Optional: set a secret key for production and/or port:
   ```bash
   export SECRET_KEY=your-secret-key
   export PORT=8080
   python app.py
   ```

### Build and run with Docker

1. Build the image (multi-stage build):
   ```bash
   docker build -t dark-matter .
   ```

2. Run the container:
   ```bash
   docker run -p 5000:5000 -e LAUNCHDARKLY_SDK_KEY=sdk-xxxx-your-key dark-matter
   ```
   Omit `-e LAUNCHDARKLY_SDK_KEY=...` if you are not using LaunchDarkly; the app will still run with default flag behavior.

3. Open `http://localhost:5000` in your browser.

### Summary

| Method        | Command / step                                              |
|---------------|-------------------------------------------------------------|
| Local Python  | `pip install -r requirements.txt` then `python app.py`     |
| Docker        | `docker build -t dark-matter .` then `docker run -p 5000:5000 -e LAUNCHDARKLY_SDK_KEY=... dark-matter` |


## Next Steps

These are notes to self, and some are aspirational.

Per the ingredients, and when time permits, I'd like or need to do the following:
- Metrics
   - Create a metric for one of my FF
   - Create an experiment that uses one of my FF and the metric.
   - Run the experiment long enough to gather data to make an informed decision.
- AI Configs
   - Implmenent an AI configuration in my application to change prompts
   - Test variations of prompts and models to see which is most effective, based on metrics.
   - (Time sounds like a good one.)
   - For fun, maybe create a metric based on the size of the payload.
- Integrations
   - Explore one of the many integrations
   - See https://launchdarkly.com/docs/integrations
   - Maybe: CloudTrail Lake (I haven't tested this before)
   - Maybe: Elk (I would need to provision an Elk stack)
   - GHA: Flag evaluations?  That would be new to mem.
   - GHA find references
   - GHA Copilot with VSCode
   - GH code referencces
   - Maybe the point is: there is quite a lot to explore.
- Create a terraform script to deploy to my AWS instance.
   - I'll use my envvars to drive the TF script for my AWS secrets
   - I'll likely deploy to ECS
   - Deploy 2 instances, and see about targeting one instance with FF.  This will require me to better understand how to use LD.

## Notes

- I  tested some CURL commands, the REST API docs look to be small.
- I am testing the CLI
   - https://github.com/launchdarkly/ldcli
   - Of course, I prefer the straight CLI over the npm cli

