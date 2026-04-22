/**
 * Dark Matter — Express + EJS + LaunchDarkly (Node.js).
 */
import express from 'express';
import session from 'express-session';
import expressLayouts from 'express-ejs-layouts';
import path from 'path';
import os from 'os';
import { fileURLToPath } from 'url';
import LaunchDarkly from '@launchdarkly/node-server-sdk';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const AUTHOR = 'Marco';
const LIBRARIES = ['express', 'ejs', '@launchdarkly/node-server-sdk', 'express-session'];

const NAV = {
  'upper-left': { right: ['/upper-right', 'upper-right'], down: ['/lower-left', 'lower-left'] },
  'upper-right': { left: ['/upper-left', 'upper-left'], down: ['/lower-right', 'lower-right'] },
  'lower-left': { right: ['/lower-right', 'lower-right'], up: ['/upper-left', 'upper-left'] },
  'lower-right': { up: ['/upper-right', 'upper-right'], left: ['/lower-left', 'lower-left'] },
};

const COMPASS = {
  'upper-left': { navUp: false, navDown: true, navLeft: false, navRight: true },
  'upper-right': { navUp: false, navDown: true, navLeft: true, navRight: false },
  'lower-left': { navUp: true, navDown: false, navLeft: false, navRight: true },
  'lower-right': { navUp: true, navDown: false, navLeft: true, navRight: false },
};

const VALID = new Set(['up', 'down', 'left', 'right']);

function round2(n) {
  return Math.round(n * 100) / 100;
}

function buildSysInfo() {
  return {
    nodeVersion: process.version,
    os: os.type(),
    osRelease: os.release(),
    machine: os.machine(),
    processor: os.cpus()[0]?.model || 'N/A',
    memoryTotalGb: round2(os.totalmem() / 1024 ** 3),
    memoryAvailableGb: round2(os.freemem() / 1024 ** 3),
    cpuCount: os.cpus().length,
  };
}

function ldContext(userName) {
  if (!userName) return null;
  return { kind: 'user', key: `user-${userName}`, name: userName };
}

let ldClient = null;
let ldDisabled = false;

async function getLdClient() {
  if (ldDisabled) return null;
  if (ldClient) return ldClient;
  const sdkKey = process.env.LAUNCHDARKLY_SDK_KEY;
  if (!sdkKey) {
    ldDisabled = true;
    return null;
  }
  const client = LaunchDarkly.init(sdkKey);
  try {
    await client.waitForInitialization({ timeoutSeconds: 15 });
    ldClient = client;
    client.on('update', (payload) => {
      const flagKey = payload && payload.key;
      if (flagKey === 'MAM_BG_COLOR') {
        console.log(`[LaunchDarkly] flag config updated: ${flagKey}`);
      }
    });
    return client;
  } catch (e) {
    console.warn('[LaunchDarkly] initialization failed:', e?.message || e);
    try {
      await Promise.resolve(client.close());
    } catch (_) {
      /* ignore */
    }
    ldDisabled = true;
    return null;
  }
}

async function getFeatureFlags(userName) {
  const defaults = {
    MAM_ABOUT: false,
    MAM_BG_COLOR: 'white',
    MAM_TOGGLE_CASE: false,
    MAM_DARK_MODE: false,
    MAM_INLINE_ABOUT: false,
  };
  const client = await getLdClient();
  if (!client) return defaults;
  const ctx = ldContext(userName);
  if (!ctx) return defaults;
  try {
    let bg = await client.stringVariation('MAM_BG_COLOR', ctx, 'white');
    if (!bg || String(bg).trim() === '') bg = 'white';
    return {
      MAM_ABOUT: await client.boolVariation('MAM_ABOUT', ctx, false),
      MAM_BG_COLOR: bg,
      MAM_TOGGLE_CASE: await client.boolVariation('MAM_TOGGLE_CASE', ctx, false),
      MAM_DARK_MODE: await client.boolVariation('MAM_DARK_MODE', ctx, false),
      MAM_INLINE_ABOUT: await client.boolVariation('MAM_INLINE_ABOUT', ctx, false),
    };
  } catch {
    return defaults;
  }
}

async function trackInlineAboutLoad(userName, loadMs, mamInlineAbout) {
  const client = await getLdClient();
  if (!client) return;
  const ctx = ldContext(userName);
  if (!ctx) return;
  try {
    console.log(
      `Tracking inline_about for ${userName} with load_ms: ${loadMs} and mam_inline_about: ${mamInlineAbout}`,
    );
    client.track(
      'inline_about',
      ctx,
      { mam_inline_about: mamInlineAbout, load_ms: loadMs },
      loadMs,
    );
  } catch {
    /* ignore */
  }
}

async function trackUiColorMode(userName, mode) {
  if (mode !== 'light' && mode !== 'dark') return;
  const client = await getLdClient();
  if (!client) return;
  const ctx = ldContext(userName);
  if (!ctx) return;
  try {
    client.track('ui_color_mode', ctx, { mode });
  } catch {
    /* ignore */
  }
}

async function reportUiColorModeWhenFlagOff(req, userName, flags) {
  if (flags.MAM_DARK_MODE) return;
  if (req.session.ldUiColorMetricSent) return;
  await trackUiColorMode(userName, 'light');
  req.session.ldUiColorMetricSent = true;
}

async function trackNavClick(userName, direction, fromSlug, toSlug) {
  const client = await getLdClient();
  if (!client) return;
  const ctx = ldContext(userName);
  if (!ctx) return;
  try {
    client.track(`nav_click_${direction}`, ctx, { from_page: fromSlug, to_page: toSlug });
  } catch {
    /* ignore */
  }
}

async function trackNavCaseToggle(userName, previousCase, newCase, fromPage) {
  const client = await getLdClient();
  if (!client) return;
  const ctx = ldContext(userName);
  if (!ctx) return;
  try {
    client.track('nav_case_toggle_clicked', ctx, {
      previous_case: previousCase,
      new_case: newCase,
      from_page: fromPage ?? '',
    });
  } catch {
    /* ignore */
  }
}

function normalizeFrom(slug) {
  if (!slug || !NAV[slug]) return 'upper-left';
  return slug;
}

function asyncHandler(fn) {
  return (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);
}

function requireLogin(req, res, next) {
  if (!req.session.name) {
    res.redirect('/');
    return;
  }
  next();
}

const app = express();
const PORT = Number.parseInt(process.env.PORT || '5000', 10);

app.set('views', path.join(__dirname, '..', 'views'));
app.set('view engine', 'ejs');
app.use(expressLayouts);
app.set('layout', 'layout');

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(
  session({
    name: 'darkmatter.sid',
    secret: process.env.SESSION_SECRET || process.env.SECRET_KEY || 'dark-matter-dev-secret-change-in-production',
    resave: false,
    saveUninitialized: false,
    cookie: { maxAge: 24 * 60 * 60 * 1000 },
  }),
);

app.use((req, res, next) => {
  res.locals.currentPath = req.path;
  next();
});

app.get(
  '/',
  asyncHandler(async (req, res) => {
    if (req.session.name) {
      res.redirect('/upper-left');
      return;
    }
    res.render('login', { layout: false, title: 'Login - Dark Matter', error: null });
  }),
);

app.post(
  '/',
  asyncHandler(async (req, res) => {
    const name = (req.body.name || '').trim();
    if (!name) {
      res.render('login', { layout: false, title: 'Login - Dark Matter', error: 'Please enter your name.' });
      return;
    }
    req.session.name = name;
    req.session.fromPage = null;
    req.session.navCase = 'lower';
    delete req.session.ldUiColorMetricSent;
    res.redirect('/upper-left');
  }),
);

app.get('/logout', (req, res) => {
  req.session.destroy(() => {
    res.redirect('/');
  });
});

app.post(
  '/toggle-nav-case',
  requireLogin,
  asyncHandler(async (req, res) => {
    const userName = req.session.name;
    const flags = await getFeatureFlags(userName);
    if (flags.MAM_TOGGLE_CASE) {
      const current = req.session.navCase || 'lower';
      const newCase = current === 'lower' ? 'upper' : 'lower';
      await trackNavCaseToggle(userName, current, newCase, req.session.fromPage);
      req.session.navCase = newCase;
    }
    const nextPage = (req.body.next_page || '').trim();
    if (nextPage) {
      res.redirect(nextPage);
      return;
    }
    res.redirect('/upper-left');
  }),
);

app.post(
  '/api/ui-color-mode',
  requireLogin,
  asyncHandler(async (req, res) => {
    const userName = req.session.name;
    const flags = await getFeatureFlags(userName);
    if (!flags.MAM_DARK_MODE) {
      res.json({ ok: true, ignored: true });
      return;
    }
    const mode = String(req.body?.mode || '').toLowerCase();
    if (mode !== 'light' && mode !== 'dark') {
      res.status(400).json({ error: 'mode must be light or dark' });
      return;
    }
    await trackUiColorMode(userName, mode);
    res.json({ ok: true });
  }),
);

app.post(
  '/api/inline-about-load',
  requireLogin,
  asyncHandler(async (req, res) => {
    const userName = req.session.name;
    const flags = await getFeatureFlags(userName);
    const raw = req.body?.load_ms;
    console.log(`load_ms: ${raw}`);
    const loadMs = Number(raw);
    if (!Number.isFinite(loadMs)) {
      res.status(400).json({ error: 'invalid load_ms' });
      return;
    }
    if (loadMs < 0 || loadMs > 600000) {
      res.status(400).json({ error: 'load_ms out of range' });
      return;
    }
    await trackInlineAboutLoad(userName, loadMs, Boolean(flags.MAM_INLINE_ABOUT));
    res.json({ ok: true });
  }),
);

app.get(
  '/nav/go/:direction',
  requireLogin,
  asyncHandler(async (req, res) => {
    const d = (req.params.direction || '').toLowerCase();
    if (!VALID.has(d)) {
      res.redirect('/upper-left');
      return;
    }
    const userName = req.session.name;
    let current = req.session.fromPage;
    current = normalizeFrom(current);
    const edges = NAV[current];
    if (!edges || !edges[d]) {
      res.redirect('/upper-left');
      return;
    }
    const [path, slug] = edges[d];
    await trackNavClick(userName, d, current, slug);
    res.redirect(path);
  }),
);

async function renderNavPage(req, res, slug, pageHeading, title) {
  const userName = req.session.name;
  const fromPage = req.session.fromPage;
  req.session.fromPage = slug;
  const flags = await getFeatureFlags(userName);
  await reportUiColorModeWhenFlagOff(req, userName, flags);
  const navCaseUpper = req.session.navCase === 'upper';
  const c = COMPASS[slug];
  const showInline = flags.MAM_INLINE_ABOUT;
  const locals = {
    title,
    name: userName,
    fromPage,
    pageHeading,
    showAbout: flags.MAM_ABOUT,
    showAboutNav: flags.MAM_ABOUT,
    bgColor: flags.MAM_BG_COLOR,
    showToggleCase: flags.MAM_TOGGLE_CASE,
    showDarkModeToggle: flags.MAM_DARK_MODE,
    navCaseUpper,
    showInlineAbout: showInline,
    recordInlineLoadMetric: true,
    ...c,
  };
  if (showInline) {
    locals.sysInfo = buildSysInfo();
    locals.libraries = LIBRARIES;
    locals.author = AUTHOR;
  }
  res.render(slug.replace(/-/g, '_'), locals);
}

app.get(
  '/upper-left',
  requireLogin,
  asyncHandler(async (req, res) => {
    await renderNavPage(req, res, 'upper-left', 'Upper Left', 'Upper Left - Dark Matter');
  }),
);

app.get(
  '/upper-right',
  requireLogin,
  asyncHandler(async (req, res) => {
    await renderNavPage(req, res, 'upper-right', 'Upper Right', 'Upper Right - Dark Matter');
  }),
);

app.get(
  '/lower-left',
  requireLogin,
  asyncHandler(async (req, res) => {
    await renderNavPage(req, res, 'lower-left', 'Lower Left', 'Lower Left - Dark Matter');
  }),
);

app.get(
  '/lower-right',
  requireLogin,
  asyncHandler(async (req, res) => {
    await renderNavPage(req, res, 'lower-right', 'Lower Right', 'Lower Right - Dark Matter');
  }),
);

app.get(
  '/about',
  requireLogin,
  asyncHandler(async (req, res) => {
    const userName = req.session.name;
    const flags = await getFeatureFlags(userName);
    if (!flags.MAM_ABOUT) {
      res.redirect('/upper-left');
      return;
    }
    await reportUiColorModeWhenFlagOff(req, userName, flags);
    res.render('about', {
      title: 'About - Dark Matter',
      name: userName,
      showAbout: true,
      showAboutNav: false,
      bgColor: flags.MAM_BG_COLOR,
      showToggleCase: flags.MAM_TOGGLE_CASE,
      showDarkModeToggle: flags.MAM_DARK_MODE,
      navCaseUpper: req.session.navCase === 'upper',
      showInlineAbout: false,
      recordInlineLoadMetric: false,
      sysInfo: buildSysInfo(),
      libraries: LIBRARIES,
      author: AUTHOR,
    });
  }),
);

app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).send('Internal Server Error');
});

async function main() {
  await getLdClient();
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Dark Matter (Node) listening on http://0.0.0.0:${PORT}`);
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
