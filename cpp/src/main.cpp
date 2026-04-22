// Dark Matter (C++) - reference implementation.
//
// This mirrors the same routes as the other implementations, but uses simple
// environment-variable driven flags to keep the build self-contained.

#include <crow.h>

#include <algorithm>
#include <chrono>
#include <cctype>
#include <cstdlib>
#include <iomanip>
#include <mutex>
#include <random>
#include <sstream>
#include <string>
#include <unordered_map>

namespace {

struct FeatureFlags {
  bool mam_about{false};
  std::string mam_bg_color{"white"};
  bool mam_toggle_case{false};
  bool mam_dark_mode{false};
  bool mam_inline_about{false};
};

struct SessionState {
  std::string name;
  std::string from_page;  // slug: upper-left, ...
  std::string nav_case{"lower"};  // lower | upper
  bool ui_color_mode_metric_sent{false};
};

std::mutex g_sessions_mu;
std::unordered_map<std::string, SessionState> g_sessions;

bool parse_bool(std::string s) {
  std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) {
    return static_cast<char>(std::tolower(c));
  });
  return s == "1" || s == "true" || s == "on" || s == "yes";
}

bool env_bool(const char* key, bool fallback) {
  const char* v = std::getenv(key);
  if (!v) return fallback;
  return parse_bool(v);
}

std::string env_string(const char* key, const std::string& fallback) {
  const char* v = std::getenv(key);
  if (!v) return fallback;
  std::string s(v);
  return s.empty() ? fallback : s;
}

FeatureFlags get_flags() {
  FeatureFlags f;
  f.mam_about = env_bool("MAM_ABOUT", false);
  f.mam_bg_color = env_string("MAM_BG_COLOR", "white");
  f.mam_toggle_case = env_bool("MAM_TOGGLE_CASE", false);
  f.mam_dark_mode = env_bool("MAM_DARK_MODE", false);
  f.mam_inline_about = env_bool("MAM_INLINE_ABOUT", false);
  if (f.mam_bg_color.empty()) f.mam_bg_color = "white";
  return f;
}

std::string random_hex(std::size_t bytes) {
  static thread_local std::mt19937_64 rng{std::random_device{}()};
  std::uniform_int_distribution<int> dist(0, 255);
  std::ostringstream oss;
  for (std::size_t i = 0; i < bytes; i++) {
    int b = dist(rng);
    oss << std::hex << std::setw(2) << std::setfill('0') << (b & 0xff);
  }
  return oss.str();
}

std::string cookie_get(const crow::request& req, const std::string& name) {
  auto it = req.headers.find("Cookie");
  if (it == req.headers.end()) return "";
  const std::string& cookie = it->second;
  const std::string needle = name + "=";
  std::size_t pos = 0;
  while (pos < cookie.size()) {
    std::size_t end = cookie.find(';', pos);
    if (end == std::string::npos) end = cookie.size();
    std::string part = cookie.substr(pos, end - pos);
    while (!part.empty() && part.front() == ' ') part.erase(part.begin());
    if (part.rfind(needle, 0) == 0) {
      return part.substr(needle.size());
    }
    pos = end + 1;
  }
  return "";
}

void cookie_set(crow::response& res, const std::string& name, const std::string& value) {
  std::ostringstream oss;
  oss << name << "=" << value << "; Path=/; HttpOnly";
  res.add_header("Set-Cookie", oss.str());
}

std::string form_get(const crow::request& req, const char* key) {
  // Crow does not automatically parse application/x-www-form-urlencoded bodies.
  // For GET, use url_params; for POST form bodies, parse req.body.
  if (req.method == crow::HTTPMethod::GET) {
    auto* v = req.url_params.get(key);
    return v ? std::string(v) : "";
  }
  auto url_decode = [](std::string_view in) -> std::string {
    std::string out;
    out.reserve(in.size());
    for (std::size_t i = 0; i < in.size(); i++) {
      char c = in[i];
      if (c == '+') {
        out.push_back(' ');
        continue;
      }
      if (c == '%' && i + 2 < in.size()) {
        auto hex = [](char h) -> int {
          if (h >= '0' && h <= '9') return h - '0';
          if (h >= 'a' && h <= 'f') return 10 + (h - 'a');
          if (h >= 'A' && h <= 'F') return 10 + (h - 'A');
          return -1;
        };
        int hi = hex(in[i + 1]);
        int lo = hex(in[i + 2]);
        if (hi >= 0 && lo >= 0) {
          out.push_back(static_cast<char>((hi << 4) | lo));
          i += 2;
          continue;
        }
      }
      out.push_back(c);
    }
    return out;
  };

  std::string body = req.body;
  std::string target(key);
  std::size_t pos = 0;
  while (pos <= body.size()) {
    std::size_t amp = body.find('&', pos);
    if (amp == std::string::npos) amp = body.size();
    std::string_view pair(body.data() + pos, amp - pos);
    std::size_t eq = pair.find('=');
    std::string_view k = eq == std::string_view::npos ? pair : pair.substr(0, eq);
    std::string_view v = eq == std::string_view::npos ? std::string_view{} : pair.substr(eq + 1);
    if (k == target) {
      return url_decode(v);
    }
    if (amp == body.size()) break;
    pos = amp + 1;
  }
  return "";
}

std::string html_escape(const std::string& s) {
  std::string out;
  out.reserve(s.size());
  for (char c : s) {
    switch (c) {
      case '&': out += "&amp;"; break;
      case '<': out += "&lt;"; break;
      case '>': out += "&gt;"; break;
      case '"': out += "&quot;"; break;
      case '\'': out += "&#39;"; break;
      default: out += c; break;
    }
  }
  return out;
}

std::string login_html(const std::string& error) {
  std::ostringstream o;
  o << R"(<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Login - Dark Matter</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root { --surface:#fff; --text:#1a1a2e; --text-muted:#64748b; --accent:#6366f1; --accent-hover:#4f46e5; --border:#e2e8f0; --radius:12px; --shadow:0 1px 3px rgba(0,0,0,.08); --shadow-lg:0 10px 40px -10px rgba(0,0,0,.15); --error:#dc2626; }
    * { box-sizing: border-box; }
    body { font-family:'Plus Jakarta Sans',system-ui,sans-serif; margin:0; min-height:100vh; background:linear-gradient(135deg,#f5f7fa 0%,#e4e8ec 100%); color:var(--text); display:flex; align-items:center; justify-content:center; padding:2rem; }
    .login-card { background:var(--surface); border-radius:var(--radius); box-shadow:var(--shadow-lg); padding:2.5rem; width:100%; max-width:24rem; }
    h1 { font-size:1.75rem; font-weight:700; margin:0 0 .25rem 0; }
    .subtitle { color:var(--text-muted); font-size:.9375rem; margin-bottom:1.5rem; }
    .error { color:var(--error); font-size:.875rem; margin-bottom:1rem; }
    label { display:block; font-weight:500; font-size:.875rem; margin-bottom:.375rem; }
    input[type=text] { width:100%; padding:.625rem .75rem; font-family:inherit; font-size:1rem; border:1px solid var(--border); border-radius:8px; margin-bottom:1.25rem; transition:border-color .15s, box-shadow .15s; }
    input[type=text]:focus { outline:none; border-color:var(--accent); box-shadow:0 0 0 3px rgba(99,102,241,.15); }
    .btn { display:inline-block; padding:.625rem 1.25rem; font-family:inherit; font-size:.9375rem; font-weight:600; border-radius:8px; border:none; cursor:pointer; background:var(--accent); color:#fff; width:100%; transition:background .15s; }
    .btn:hover { background:var(--accent-hover); }
  </style>
</head>
<body>
  <div class="login-card">
    <h1>Dark Matter</h1>
    <p class="subtitle">Enter your name to continue (no password).</p>
)";
  if (!error.empty()) {
    o << "    <p class=\"error\">" << html_escape(error) << "</p>\n";
  }
  o << R"(    <form method="post" action="/">
      <label for="name">Name</label>
      <input id="name" name="name" type="text" autofocus required placeholder="Your name">
      <button type="submit" class="btn">Log in</button>
    </form>
  </div>
</body>
</html>
)";
  return o.str();
}

std::string compass_html(const std::string& slug, bool nav_case_upper) {
  bool up = false, down = false, left = false, right = false;
  if (slug == "upper-left") { down = true; right = true; }
  else if (slug == "upper-right") { down = true; left = true; }
  else if (slug == "lower-left") { up = true; right = true; }
  else if (slug == "lower-right") { up = true; left = true; }
  auto upLabel = nav_case_upper ? "UP" : "up";
  auto downLabel = nav_case_upper ? "DOWN" : "down";
  auto leftLabel = nav_case_upper ? "LEFT" : "left";
  auto rightLabel = nav_case_upper ? "RIGHT" : "right";

  std::ostringstream o;
  o << R"(<div class="compass-wrap">
  <p class="from-page" style="margin-bottom: 0.5rem;">Navigate</p>
  <div class="compass">)";
  o << "<span class=\"up " << (up ? "" : "disabled") << "\">";
  if (up) o << "<a href=\"/nav/go/up\">" << upLabel << "</a>";
  else o << upLabel;
  o << "</span>";

  o << "<span class=\"left " << (left ? "" : "disabled") << "\">";
  if (left) o << "<a href=\"/nav/go/left\">" << leftLabel << "</a>";
  else o << leftLabel;
  o << "</span>";

  o << "<span class=\"center\">·</span>";

  o << "<span class=\"right " << (right ? "" : "disabled") << "\">";
  if (right) o << "<a href=\"/nav/go/right\">" << rightLabel << "</a>";
  else o << rightLabel;
  o << "</span>";

  o << "<span class=\"down " << (down ? "" : "disabled") << "\">";
  if (down) o << "<a href=\"/nav/go/down\">" << downLabel << "</a>";
  else o << downLabel;
  o << "</span>";

  o << R"(</div>
</div>)";
  return o.str();
}

std::string inline_about_html() {
  return R"(<div class="card inline-about">
  <h1>About Dark Matter</h1>
  <p>Dark Matter is a C++ application with feature-flagged navigation and an about page.</p>
  <h2>Author</h2>
  <p>Marco</p>
  <h2>Libraries used</h2>
  <ul style="margin: 0.5rem 0; padding-left: 1.5rem;">
    <li>Crow</li>
  </ul>
</div>)";
}

std::string layout_html(
    const std::string& title,
    const FeatureFlags& flags,
    const SessionState* sess,
    bool show_about_nav,
    const std::string& current_path,
    bool record_inline_metric,
    const std::string& body_html,
    bool show_inline_about) {
  std::ostringstream o;
  o << R"(<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>)" << html_escape(title) << R"(</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --banner-bg: )" << html_escape(flags.mam_bg_color) << R"(;
      --surface: #ffffff;
      --text: #1a1a2e;
      --text-muted: #64748b;
      --accent: #6366f1;
      --accent-hover: #4f46e5;
      --border: #e2e8f0;
      --radius: 12px;
      --shadow: 0 1px 3px rgba(0,0,0,.08);
      --shadow-lg: 0 10px 40px -10px rgba(0,0,0,.15);
    }
    * { box-sizing: border-box; }
    body { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; margin:0; min-height:100vh; background:#ffffff; color:var(--text); font-size:1rem; line-height:1.6; }
    .banner { width:100%; padding:1rem 1.5rem 1.25rem; background-color:var(--banner-bg); border-bottom:1px solid rgba(0,0,0,0.08); box-shadow:0 1px 0 rgba(255,255,255,0.5) inset; }
    .banner-inner { max-width:56rem; margin:0 auto; display:flex; flex-wrap:wrap; align-items:center; gap:.75rem 1rem; }
    .banner-screen { display:inline-flex; flex-wrap:wrap; align-items:center; gap:.5rem 1rem; padding:.5rem 1rem; background:#f1f5f9; border:1px solid rgba(15,23,42,0.1); border-radius:10px; box-shadow:0 1px 2px rgba(15,23,42,0.06); }
    .banner-screen--grow { flex:1 1 auto; min-width:min(100%,14rem); }
    .banner-screen .user { font-weight:600; color:var(--text); }
    .banner-screen a:not(.btn) { font-weight:500; }
    .banner-screen .btn-ghost { background:rgba(255,255,255,0.85); border:1px solid var(--border); }
    .banner-screen .btn-ghost:hover { background:#ffffff; }
    .banner-screen__sep { width:1px; height:1.25rem; background:var(--border); flex-shrink:0; }
    .banner-toggle form { margin:0; }
    .app { max-width:56rem; margin:0 auto; padding:1.25rem 1.5rem 2rem; background:#ffffff; }
    .nav-section { position:relative; padding:2.75rem 1.25rem 1.75rem; border-radius:var(--radius); transition: background-color 0.2s ease, color 0.2s ease; }
    .nav-section--light { --nav-text:#0f172a; --nav-text-muted:#64748b; --nav-border:#e2e8f0; --nav-card-bg:#ffffff; --nav-muted-bg:rgba(15,23,42,0.06); background:#f1f5f9; color:var(--nav-text); }
    .nav-section--dark { --nav-text:#f1f5f9; --nav-text-muted:#94a3b8; --nav-border:rgba(148,163,184,0.35); --nav-card-bg:#1e293b; --nav-muted-bg:rgba(0,0,0,0.28); background:#0f172a; color:var(--nav-text); }
    .nav-section .card { background:var(--nav-card-bg); border-color:var(--nav-border); color:var(--nav-text); box-shadow:0 1px 3px rgba(0,0,0,0.08); }
    .nav-section--dark .card { box-shadow:0 1px 3px rgba(0,0,0,0.35); }
    .nav-section .from-page { color:var(--nav-text-muted); }
    .nav-section h1, .nav-section h2 { color:var(--nav-text); }
    .nav-section .about-info { padding:1rem; border-radius:8px; overflow-x:auto; background:var(--nav-muted-bg); border:1px solid var(--nav-border); }
    .nav-section .compass-wrap { border-top-color:var(--nav-border); }
    .nav-section .compass .center, .nav-section .compass .disabled { color:var(--nav-text-muted); }
    .nav-theme-toggle { position:absolute; top:.35rem; right:.35rem; display:inline-flex; align-items:center; gap:.4rem; padding:.45rem .85rem; font-family:inherit; font-size:.8125rem; font-weight:600; line-height:1.2; color:#fff; background:#312e81; border:2px solid rgba(255,255,255,0.95); border-radius:999px; cursor:pointer; box-shadow:0 2px 10px rgba(0,0,0,0.28); transition:background .15s ease, transform .05s ease; }
    .nav-theme-toggle:hover { background:#4338ca; color:#fff; }
    .nav-theme-toggle:focus-visible { outline:2px solid #fbbf24; outline-offset:3px; }
    .nav-theme-toggle__icon { font-size:1rem; line-height:1; }
    .btn { display:inline-block; padding:.5rem 1rem; font-family:inherit; font-size:.875rem; font-weight:500; text-decoration:none; border-radius:8px; border:none; cursor:pointer; transition:background .15s, color .15s; }
    .btn-ghost { background:rgba(0,0,0,0.06); color:var(--text); }
    .btn-ghost:hover { background:rgba(0,0,0,0.1); color:var(--text); text-decoration:none; }
    .btn-primary { background:var(--accent); color:white; }
    .btn-primary:hover { background:var(--accent-hover); color:white; }
    .card { background:var(--surface); border-radius:var(--radius); box-shadow:var(--shadow); padding:1.5rem 2rem; margin-bottom:1.5rem; border:1px solid var(--border); }
    .from-page { color:var(--text-muted); font-size:.875rem; margin-bottom:1rem; }
    h1 { font-size:1.75rem; font-weight:700; margin:0 0 .5rem 0; }
    h2 { font-size:1.25rem; font-weight:600; margin:0 0 1rem 0; color:var(--text); }
    a { color:var(--accent); text-decoration:none; font-weight:500; }
    a:hover { text-decoration:underline; }
    .compass-wrap { margin-top:2rem; padding-top:1.5rem; border-top:1px solid var(--border); }
    .compass { display:grid; grid-template-columns:1fr auto 1fr; grid-template-rows:auto auto auto; gap:.5rem 1rem; max-width:16rem; margin:0 auto; place-items:center; }
    .compass .up { grid-column:2; grid-row:1; }
    .compass .down { grid-column:2; grid-row:3; }
    .compass .left { grid-column:1; grid-row:2; }
    .compass .right { grid-column:3; grid-row:2; }
    .compass .center { grid-column:2; grid-row:2; color:var(--text-muted); font-size:1.25rem; }
    .compass a { display:inline-block; padding:.5rem 1rem; border-radius:8px; background:var(--accent); color:white; font-weight:500; transition:background .15s, transform .05s; }
    .compass a:hover { background:var(--accent-hover); text-decoration:none; }
    .compass .disabled { color:var(--text-muted); cursor:default; font-weight:500; padding:.5rem 1rem; }
    .nav-section .inline-about { margin-top:1.5rem; }
    .nav-section .inline-about h1 { font-size:1.5rem; }
  </style>
</head>
<body>
)";

  if (sess) {
    o << R"(<header class="banner"><div class="banner-inner">)";
    o << R"(<div class="banner-screen banner-screen--grow">)";
    o << "<span class=\"user\">Hello, " << html_escape(sess->name) << "</span>";
    o << R"(<a href="/logout" class="btn btn-ghost">Logout</a>)";
    if (show_about_nav) {
      o << R"(<span class="banner-screen__sep" aria-hidden="true"></span><a href="/about">About</a>)";
    }
    o << "</div>";
    if (flags.mam_toggle_case) {
      o << R"(<div class="banner-screen banner-toggle"><form method="post" action="/toggle-nav-case">)";
      o << "<input type=\"hidden\" name=\"next_page\" value=\"" << html_escape(current_path) << "\">";
      o << R"(<button type="submit" class="btn btn-primary">)";
      if (sess->nav_case == "upper") o << "SWITCH->case";
      else o << "switch->CASE";
      o << R"(</button></form></div>)";
    }
    o << "</div></header>";
  }

  o << R"(<div class="app">
  <div class="nav-section nav-section--light" id="nav-section"
       data-mam-dark-mode=")" << (flags.mam_dark_mode ? "true" : "false") << R"("
       data-report-url="/api/ui-color-mode"
       data-inline-metric-url="/api/inline-about-load">)";
  if (flags.mam_dark_mode) {
    o << R"(<button type="button" class="nav-theme-toggle" id="nav-theme-toggle" aria-pressed="false" aria-label="Switch to dark mode">
      <span class="nav-theme-toggle__icon" aria-hidden="true">🌙</span>
      <span class="nav-theme-toggle__label">Dark mode</span>
    </button>)";
  }
  o << R"(<div class="nav-section__inner">)" << body_html << R"(</div>)";
  if (show_inline_about) {
    o << inline_about_html();
  }
  o << R"(</div></div>)";

  // theme toggle JS + metrics posts (ported from python/templates/base.html)
  o << R"(<script>
(function () {
  var STORAGE_KEY = 'dark-matter-nav-theme';
  var REPORT_SS_KEY = 'ld_ui_color_mode_last_sent';
  var shell = document.getElementById('nav-section');
  if (!shell) return;
  var darkFlagOn = shell.getAttribute('data-mam-dark-mode') === 'true';
  var reportUrl = shell.getAttribute('data-report-url') || '';
  var btn = document.getElementById('nav-theme-toggle');
  var labelEl = btn ? btn.querySelector('.nav-theme-toggle__label') : null;
  var iconEl = btn ? btn.querySelector('.nav-theme-toggle__icon') : null;

  function applyVisual(theme) {
    var isDark = theme === 'dark';
    shell.classList.remove('nav-section--light', 'nav-section--dark');
    shell.classList.add(isDark ? 'nav-section--dark' : 'nav-section--light');
    if (btn) {
      btn.setAttribute('aria-pressed', isDark ? 'true' : 'false');
      if (isDark) {
        btn.setAttribute('aria-label', 'Switch to light mode');
        if (labelEl) labelEl.textContent = 'Light mode';
        if (iconEl) iconEl.textContent = '☀️';
      } else {
        btn.setAttribute('aria-label', 'Switch to dark mode');
        if (labelEl) labelEl.textContent = 'Dark mode';
        if (iconEl) iconEl.textContent = '🌙';
      }
    }
  }

  function persistTheme(theme) {
    try { localStorage.setItem(STORAGE_KEY, theme); } catch (e) {}
  }

  function reportMode(mode) {
    if (!darkFlagOn || !reportUrl) return;
    try {
      var last = sessionStorage.getItem(REPORT_SS_KEY);
      if (last === mode) return;
      sessionStorage.setItem(REPORT_SS_KEY, mode);
    } catch (e) {}
    fetch(reportUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ mode: mode })
    }).catch(function () {});
  }

  if (!darkFlagOn) {
    applyVisual('light');
    return;
  }

  var stored = null;
  try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) {}
  var theme = stored === 'dark' ? 'dark' : 'light';
  applyVisual(theme);
  persistTheme(theme);
  reportMode(theme);

  if (btn) {
    btn.addEventListener('click', function () {
      var next = shell.classList.contains('nav-section--dark') ? 'light' : 'dark';
      applyVisual(next);
      persistTheme(next);
      try { sessionStorage.removeItem(REPORT_SS_KEY); } catch (e) {}
      reportMode(next);
    });
  }
})();
</script>)";

  if (sess && record_inline_metric) {
    o << R"(<script>
(function () {
  var shell = document.getElementById('nav-section');
  if (!shell) return;
  var url = shell.getAttribute('data-inline-metric-url');
  if (!url) return;
  function sendLoadMetric() {
    var loadMs = null;
    var list = performance.getEntriesByType && performance.getEntriesByType('navigation');
    if (list && list.length && list[0].loadEventEnd > 0) {
      loadMs = Math.round(list[0].loadEventEnd - list[0].startTime);
    } else if (window.performance && performance.timing && performance.timing.loadEventEnd) {
      var t = performance.timing;
      loadMs = t.loadEventEnd - t.navigationStart;
    }
    if (loadMs == null || loadMs < 0 || loadMs > 600000) return;
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ load_ms: loadMs })
    }).catch(function () {});
  }
  if (document.readyState === 'complete') sendLoadMetric();
  else window.addEventListener('load', sendLoadMetric);
})();
</script>)";
  }

  o << R"(</body></html>)";
  return o.str();
}

SessionState* require_session(const crow::request& req, crow::response& res) {
  std::string sid = cookie_get(req, "dm_sid");
  if (sid.empty()) {
    res.code = 302;
    res.add_header("Location", "/");
    res.end();
    return nullptr;
  }
  std::scoped_lock lk(g_sessions_mu);
  auto it = g_sessions.find(sid);
  if (it == g_sessions.end() || it->second.name.empty()) {
    res.code = 302;
    res.add_header("Location", "/");
    res.end();
    return nullptr;
  }
  return &it->second;
}

void track_ui_color_mode(const std::string& user, const std::string& mode) {
  if (mode != "light" && mode != "dark") return;
  std::cerr << "[metric] ui_color_mode user=" << user << " mode=" << mode << "\n";
}

void track_inline_about(const std::string& user, double load_ms, bool mam_inline_about) {
  std::cerr << "[metric] inline_about user=" << user << " load_ms=" << load_ms
            << " mam_inline_about=" << (mam_inline_about ? "true" : "false") << "\n";
}

void track_nav_click(const std::string& user, const std::string& dir, const std::string& from, const std::string& to) {
  std::cerr << "[metric] nav_click_" << dir << " user=" << user << " from=" << from << " to=" << to << "\n";
}

void track_nav_case_toggle(const std::string& user, const std::string& prev, const std::string& next, const std::string& from_page) {
  std::cerr << "[metric] nav_case_toggle_clicked user=" << user << " previous_case=" << prev
            << " new_case=" << next << " from_page=" << from_page << "\n";
}

}  // namespace

int main() {
  crow::SimpleApp app;

  CROW_ROUTE(app, "/").methods("GET"_method)([](const crow::request& req) {
    crow::response res;
    // If already logged in, redirect to upper-left
    std::string sid = cookie_get(req, "dm_sid");
    if (!sid.empty()) {
      std::scoped_lock lk(g_sessions_mu);
      auto it = g_sessions.find(sid);
      if (it != g_sessions.end() && !it->second.name.empty()) {
        res.code = 302;
        res.add_header("Location", "/upper-left");
        return res;
      }
    }
    res.set_header("Content-Type", "text/html; charset=utf-8");
    res.write(login_html(""));
    return res;
  });

  CROW_ROUTE(app, "/").methods("POST"_method)([](const crow::request& req) {
    crow::response res;
    std::string n = form_get(req, "name");
    // trim
    n.erase(n.begin(), std::find_if(n.begin(), n.end(), [](unsigned char ch) { return !std::isspace(ch); }));
    n.erase(std::find_if(n.rbegin(), n.rend(), [](unsigned char ch) { return !std::isspace(ch); }).base(), n.end());
    if (n.empty()) {
      res.set_header("Content-Type", "text/html; charset=utf-8");
      res.write(login_html("Please enter your name."));
      return res;
    }
    std::string sid = random_hex(16);
    {
      std::scoped_lock lk(g_sessions_mu);
      g_sessions[sid] = SessionState{.name = n, .from_page = "", .nav_case = "lower", .ui_color_mode_metric_sent = false};
    }
    cookie_set(res, "dm_sid", sid);
    res.code = 302;
    res.add_header("Location", "/upper-left");
    return res;
  });

  CROW_ROUTE(app, "/logout").methods("GET"_method)([](const crow::request& req) {
    crow::response res;
    std::string sid = cookie_get(req, "dm_sid");
    if (!sid.empty()) {
      std::scoped_lock lk(g_sessions_mu);
      g_sessions.erase(sid);
    }
    cookie_set(res, "dm_sid", "deleted; Max-Age=0");
    res.code = 302;
    res.add_header("Location", "/");
    return res;
  });

  CROW_ROUTE(app, "/toggle-nav-case").methods("POST"_method)([](const crow::request& req) {
    crow::response res;
    auto* sess = require_session(req, res);
    if (!sess) return res;
    FeatureFlags flags = get_flags();
    if (flags.mam_toggle_case) {
      std::string current = sess->nav_case.empty() ? "lower" : sess->nav_case;
      std::string next = (current == "lower") ? "upper" : "lower";
      track_nav_case_toggle(sess->name, current, next, sess->from_page);
      sess->nav_case = next;
    }
    std::string next_page = form_get(req, "next_page");
    if (!next_page.empty()) {
      res.code = 302;
      res.add_header("Location", next_page);
      return res;
    }
    res.code = 302;
    res.add_header("Location", "/upper-left");
    return res;
  });

  CROW_ROUTE(app, "/api/ui-color-mode").methods("POST"_method)([](const crow::request& req) {
    crow::response res;
    auto* sess = require_session(req, res);
    if (!sess) return res;
    FeatureFlags flags = get_flags();
    if (!flags.mam_dark_mode) {
      res.set_header("Content-Type", "application/json");
      res.write(R"({"ok":true,"ignored":true})");
      return res;
    }
    auto payload = crow::json::load(req.body);
    std::string mode = payload.has("mode") ? std::string(payload["mode"].s()) : "";
    std::transform(mode.begin(), mode.end(), mode.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (mode != "light" && mode != "dark") {
      res.code = 400;
      res.set_header("Content-Type", "application/json");
      res.write(R"({"error":"mode must be light or dark"})");
      return res;
    }
    track_ui_color_mode(sess->name, mode);
    res.set_header("Content-Type", "application/json");
    res.write(R"({"ok":true})");
    return res;
  });

  CROW_ROUTE(app, "/api/inline-about-load").methods("POST"_method)([](const crow::request& req) {
    crow::response res;
    auto* sess = require_session(req, res);
    if (!sess) return res;
    FeatureFlags flags = get_flags();
    auto payload = crow::json::load(req.body);
    if (!payload.has("load_ms")) {
      res.code = 400;
      res.set_header("Content-Type", "application/json");
      res.write(R"({"error":"invalid load_ms"})");
      return res;
    }
    double load_ms = payload["load_ms"].d();
    if (load_ms < 0 || load_ms > 600000) {
      res.code = 400;
      res.set_header("Content-Type", "application/json");
      res.write(R"({"error":"load_ms out of range"})");
      return res;
    }
    track_inline_about(sess->name, load_ms, flags.mam_inline_about);
    res.set_header("Content-Type", "application/json");
    res.write(R"({"ok":true})");
    return res;
  });

  CROW_ROUTE(app, "/nav/go/<string>").methods("GET"_method)([](const crow::request& req, std::string direction) {
    crow::response res;
    auto* sess = require_session(req, res);
    if (!sess) return res;
    std::transform(direction.begin(), direction.end(), direction.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (direction != "up" && direction != "down" && direction != "left" && direction != "right") {
      res.code = 302;
      res.add_header("Location", "/upper-left");
      return res;
    }
    std::string current = sess->from_page;
    if (current != "upper-left" && current != "upper-right" && current != "lower-left" && current != "lower-right") {
      current = "upper-left";
    }
    std::string to_path = "/upper-left";
    std::string to_slug = "upper-left";
    if (current == "upper-left") {
      if (direction == "right") { to_path = "/upper-right"; to_slug = "upper-right"; }
      else if (direction == "down") { to_path = "/lower-left"; to_slug = "lower-left"; }
      else { res.code = 302; res.add_header("Location", "/upper-left"); return res; }
    } else if (current == "upper-right") {
      if (direction == "left") { to_path = "/upper-left"; to_slug = "upper-left"; }
      else if (direction == "down") { to_path = "/lower-right"; to_slug = "lower-right"; }
      else { res.code = 302; res.add_header("Location", "/upper-left"); return res; }
    } else if (current == "lower-left") {
      if (direction == "right") { to_path = "/lower-right"; to_slug = "lower-right"; }
      else if (direction == "up") { to_path = "/upper-left"; to_slug = "upper-left"; }
      else { res.code = 302; res.add_header("Location", "/upper-left"); return res; }
    } else if (current == "lower-right") {
      if (direction == "left") { to_path = "/lower-left"; to_slug = "lower-left"; }
      else if (direction == "up") { to_path = "/upper-right"; to_slug = "upper-right"; }
      else { res.code = 302; res.add_header("Location", "/upper-left"); return res; }
    }
    track_nav_click(sess->name, direction, current, to_slug);
    res.code = 302;
    res.add_header("Location", to_path);
    return res;
  });

  auto render_corner = [&](const crow::request& req, const std::string& slug, const std::string& heading) {
    crow::response res;
    auto* sess = require_session(req, res);
    if (!sess) return res;
    FeatureFlags flags = get_flags();
    if (!flags.mam_dark_mode && !sess->ui_color_mode_metric_sent) {
      track_ui_color_mode(sess->name, "light");
      sess->ui_color_mode_metric_sent = true;
    }
    std::string from = sess->from_page;
    sess->from_page = slug;
    std::ostringstream body;
    if (!from.empty()) {
      body << "<p class=\"from-page\">You came from: " << html_escape(from) << "</p>";
    }
    body << "<div class=\"card\"><h2>" << html_escape(heading) << "</h2>";
    body << compass_html(slug, sess->nav_case == "upper");
    body << "</div>";
    res.set_header("Content-Type", "text/html; charset=utf-8");
    res.write(layout_html(heading + " - Dark Matter", flags, sess, flags.mam_about, req.url, true, body.str(),
                          flags.mam_inline_about));
    return res;
  };

  CROW_ROUTE(app, "/upper-left").methods("GET"_method)([&](const crow::request& req) {
    return render_corner(req, "upper-left", "Upper Left");
  });
  CROW_ROUTE(app, "/upper-right").methods("GET"_method)([&](const crow::request& req) {
    return render_corner(req, "upper-right", "Upper Right");
  });
  CROW_ROUTE(app, "/lower-left").methods("GET"_method)([&](const crow::request& req) {
    return render_corner(req, "lower-left", "Lower Left");
  });
  CROW_ROUTE(app, "/lower-right").methods("GET"_method)([&](const crow::request& req) {
    return render_corner(req, "lower-right", "Lower Right");
  });

  CROW_ROUTE(app, "/about").methods("GET"_method)([](const crow::request& req) {
    crow::response res;
    auto* sess = require_session(req, res);
    if (!sess) return res;
    FeatureFlags flags = get_flags();
    if (!flags.mam_about) {
      res.code = 302;
      res.add_header("Location", "/upper-left");
      return res;
    }
    if (!flags.mam_dark_mode && !sess->ui_color_mode_metric_sent) {
      track_ui_color_mode(sess->name, "light");
      sess->ui_color_mode_metric_sent = true;
    }
    std::ostringstream body;
    body << "<p class=\"from-page\"><a href=\"/upper-left\">← Back to Upper Left</a></p>";
    body << inline_about_html();
    res.set_header("Content-Type", "text/html; charset=utf-8");
    res.write(layout_html("About - Dark Matter", flags, sess, false, req.url, false, body.str(), false));
    return res;
  });

  int port = 5000;
  if (const char* p = std::getenv("PORT")) {
    try {
      port = std::stoi(p);
    } catch (...) {
      port = 5000;
    }
  }

  std::cerr << "Dark Matter (C++) listening on http://0.0.0.0:" << port << "\n";
  app.port(static_cast<uint16_t>(port)).multithreaded().run();
  return 0;
}
