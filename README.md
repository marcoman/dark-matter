# Dark Matter

A simple Flask application with multi-page navigation and LaunchDarkly feature flags. You log in with your name only (no password), then move between four pages (upper-left, upper-right, lower-left, lower-right) using "Right", "Left", "Up", and "Down" links. Feature flags control whether an "About" page is visible and the default background color.

## What this application does

- **Login**: Enter your name on the login page; no password is required.
- **Navigation**: After login you land on **Upper Left**. From there you can go **Right** (to Upper Right) or **Down** (to Lower Left). Each of the four corners has two links that follow the same grid (left/right and up/down).
- **Upper Left** → Right: Upper Right; Down: Lower Left  
- **Upper Right** → Left: Upper Left; Down: Lower Right  
- **Lower Left** → Right: Lower Right; Up: Upper Left  
- **Lower Right** → Up: Upper Right; Left: Lower Left  
- Every page shows your name, a logout button, and “from where you came from.”
- **Logout** clears the session and returns you to the login page.

## Feature flags (LaunchDarkly)

- **MAM_ABOUT** (boolean): When enabled, an “About” link appears and the About page is accessible. That page shows the application name, system details (Python version, OS, memory, CPU), the author name, and the libraries used.
- **MAM_BG_COLOR**: Sets the default background color for the app. The default is `white`; the value should be a standard HTML color name (e.g. `white`, `lightgray`, `lightblue`).

The LaunchDarkly SDK key is read from the environment variable **`LAUNCHDARKLY_SDK_KEY`** (you may have referred to it as `LAUNCHCDARKLY_SDK_KEY`; the app uses `LAUNCHDARKLY_SDK_KEY`).

---

## Prompt used to create this application

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

### Run from the command line (Python 3)

1. Create a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set the LaunchDarkly SDK key (optional; if unset, flags default to off/white):
   ```bash
   export LAUNCHDARKLY_SDK_KEY=sdk-xxxx-your-key
   ```

4. Run the app:
   ```bash
   python app.py
   ```
   The app listens on `http://0.0.0.0:5000`. Open that URL in your browser.

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
