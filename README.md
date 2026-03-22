# Dark Matter

Welcome to my humble project.  This is a small Python Flask application with multi-page navigation that utilizes LaunchDarkly capabilities. 

The application promnpts you for a name-only log in (no password), and your primary options are to navitate between four pages in a box formation (upper-left, upper-right, lower-left, lower-right) using "Right", "Left", "Up", and "Down" buttons. 

Along the way, I added a few extra pages and links to help illustrate some LD capabilities. For example: 
- Feature flags control whether an "About" page is visible.
- The top banner background change based on the user by using targeted feature flags.
- A dark mode toggle is available as part of an experiment, also governed by feature flags. I collect metrics as part of this experiment.

## What this application does

- **Login**: Enter your name on the login page; no password is required.
- **Navigation**: After login you land on **Upper Left**. From there you can go **Right** (to Upper Right) or **Down** (to Lower Left). Each of the four corners has two links that follow the same grid (left/right and up/down). Clicks are routed through `/nav/go/...` so LaunchDarkly can record custom events for metrics.
- **Upper Left** → Right: Upper Right; Down: Lower Left  
- **Upper Right** → Left: Upper Left; Down: Lower Right  
- **Lower Left** → Right: Lower Right; Up: Upper Left  
- **Lower Right** → Up: Upper Right; Left: Lower Left  
- Every page shows your name, a logout button, and “from where you came from.”
- **Navigation area** (below the banner): **light / dark mode** toggle (upper right) only when LaunchDarkly flag **`MAM_DARK_MODE`** is on. Choice is stored in `localStorage`. With the flag off, the UI stays **light** and the toggle is hidden. The banner is not affected.
- **Logout** clears the session and returns you to the login page.

## Feature flags (LaunchDarkly)

These are the feature flags by name that I use in this example:

- **MAM_ABOUT** (boolean): When enabled, an “About” link appears and the About page is accessible. That page shows the application name, system details (Python version, OS, memory, CPU), the author name, and the libraries used.
- **MAM_BG_COLOR**: Sets the background color of the **top banner** (welcome, Logout, About when shown, case toggle when shown). The main navigation area stays **white**. Default is `white`; use standard HTML color names (e.g. `lightgray`, `lightblue`).  This page has several options, for when the feature is false, a default color for when it is true, and different colors depending on the username.
- **MAM_TOGGLE_CASE** (boolean): When enabled, a button appears on navigation pages to toggle compass link labels between lower and upper case (for experiments).  This button is designed to test the collection of LD metrics.
- **MAM_DARK_MODE** (boolean, default **off**): When enabled, the nav-area **light/dark** toggle is shown; when off, the nav area stays light and the toggle is hidden.  Ths toggle is designed ot test experimentation to find out, "Do people prefer dark or light mode?"

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

| Event key | When it fires |
|-----------|----------------|
| `ui_color_mode` | Reports effective nav color mode: `data.mode` is **`light`** or **`dark`**. If **`MAM_DARK_MODE`** is off, the server sends **`light`** once per login session. If **`MAM_DARK_MODE`** is on, the browser POSTs to `/api/ui-color-mode` when the page loads (current preference) and when the user toggles (deduped per tab session for unchanged mode). |

**Event filters in LaunchDarkly:** reference custom data fields on the event (e.g. `new_case`, `from_page`) depending on your UI; naming often matches the keys sent in `track(..., data={...})`.

In LaunchDarkly, create **custom metrics** that count these event keys (e.g. one per `nav_click_*` direction, plus one for `nav_case_toggle_clicked`). Attach them to your experiment as needed.

---

## My Stack
I developed this code on a Win11 machine with WSL enabled.
The primary OS is Ubuntu 24.
Python verison 3.12.3
I use Python Virtual environments, as noted below.
I developed with Cursor.  This is my first major usage of that IDE for a multi-session test.  Previously, I used cursor for simple projects, typically 15-20 minutes.

## Prompt used to create this application

This was the first prompt, but not the only prompt.

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

Since the initial prompt, I added more to separate the top and bottom into a banner + body section.
To better support contrast, I modified the banner to enclose text in persistent backgrounds.
I added a toggle for dark/light mode.  To support this, I asked to change the color scheme to better support the different contrast requirements.
Along the way, I made changes to navigation, words, the about page, and more and this resulted in shifting logic from the python application to the *.html pages, to a reusable banner section, to updates in  the .css files to better support text switches.  I reviewed about 90% of the code changes suggested to me...eerily spot-on.

---

## How to build and run

### Prerequisites

- Python 3.10+ (or 3.12 for Docker)
- Optional: Docker (for container run)
- Optional: LaunchDarkly project and SDK key for feature flags

### Environment variables:

I use these envvars to direct my application.  Of course, I don't have my secrets here, but I do state how big each field is.

`export LAUNCHDARKLY_SDK_KEY=sdk-8chars-4chars-4chars-4chars-12chars`
`export LAUNCHDARKLY_API_KEY=api-8chars-4chars-4chars-4chars-12chars`


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

3. Set the LaunchDarkly envvars (optional; if unset, flags default to off/white):
   ```bash
   export LAUNCHDARKLY_SDK_KEY=sdk-8chars-4chars-4chars-4chars-12chars
   export LAUNCHDARKLY_API_KEY=api-8chars-4chars-4chars-4chars-12chars
   ```
I happen to have this envvar set up in my ~/.bashrc.

4. Run the app:
   ```bash
   python app.py
   ```
   The app listens on `http://127.0.0.1:5000`. Open that URL in your browser.

5. Optional: set a secret key for production and/or port (not tested in this configuration)
   ```bash
   export SECRET_KEY=your-secret-key
   export PORT=8080
   python app.py
   ```

### Build and run with Docker (not tested...yet)

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


## Ideas, musings, next steps

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

## Observations, issues, bugs
- I  tested some CURL commands, the REST API docs look to be small.
- I am testing the CLI
   - https://github.com/launchdarkly/ldcli
   - Of course, I prefer the straight CLI over the npm cli
- I noticed that rapid navigation clicking may send you to the login page...may need investigation.

# Images

This is a screenshot of the metrics page, showing activity for several mtrics.
![metrics screenshot](./images/metrics.png)


This is the screenshot of the FF page, showing the list of FFs in this project, plus one that is unused.
![Feature Flags screenshot](./images/ld_ff.png)


This screenshot shows the details for a single feature flag - MAM_BG_COLOR.  The details highlight the default values for different targets.
![Feature Flags screenshot](./images/ld_ff_bg_color.png)

