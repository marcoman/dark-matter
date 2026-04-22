package com.darkmatter.service;

import com.darkmatter.model.FeatureFlags;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.LDValue;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;
import com.launchdarkly.sdk.server.interfaces.FlagTracker;
import com.darkmatter.support.SessionKeys;
import jakarta.annotation.PreDestroy;
import jakarta.servlet.http.HttpSession;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.time.Duration;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class LaunchDarklyService {

    private static final Logger log = LoggerFactory.getLogger(LaunchDarklyService.class);

    private final Object clientLock = new Object();
    private volatile LDClient client;
    private volatile boolean clientDisabled;
    private final Set<String> bgColorListenerKeys = ConcurrentHashMap.newKeySet();

    public LDContext contextForUser(String userName) {
        if (userName == null || userName.isBlank()) {
            return null;
        }
        return LDContext.builder("user-" + userName).name(userName).build();
    }

    private LDClient getOrInitClient() {
        if (clientDisabled) {
            return null;
        }
        if (client != null) {
            return client.isInitialized() ? client : null;
        }
        synchronized (clientLock) {
            if (clientDisabled) {
                return null;
            }
            if (client != null) {
                return client.isInitialized() ? client : null;
            }
            String sdkKey = System.getenv("LAUNCHDARKLY_SDK_KEY");
            if (sdkKey == null || sdkKey.isBlank()) {
                clientDisabled = true;
                return null;
            }
            LDConfig config = new LDConfig.Builder()
                    .startWait(Duration.ofSeconds(15))
                    .build();
            LDClient c = new LDClient(sdkKey, config);
            if (!c.isInitialized()) {
                try {
                    c.close();
                } catch (IOException e) {
                    log.debug("LaunchDarkly client close after failed init", e);
                }
                clientDisabled = true;
                return null;
            }
            client = c;
            return client;
        }
    }

    public FeatureFlags featureFlags(String userName) {
        FeatureFlags defaults = FeatureFlags.defaults();
        LDClient ld = getOrInitClient();
        if (ld == null || !ld.isInitialized()) {
            return defaults;
        }
        LDContext ctx = contextForUser(userName);
        if (ctx == null) {
            return defaults;
        }
        maybeAttachBgColorListener(ld, ctx);
        try {
            String bg = ld.stringVariation("MAM_BG_COLOR", ctx, "white");
            if (bg == null || bg.isBlank()) {
                bg = "white";
            }
            return new FeatureFlags(
                    ld.boolVariation("MAM_ABOUT", ctx, false),
                    bg,
                    ld.boolVariation("MAM_TOGGLE_CASE", ctx, false),
                    ld.boolVariation("MAM_DARK_MODE", ctx, false),
                    ld.boolVariation("MAM_INLINE_ABOUT", ctx, false)
            );
        } catch (Exception e) {
            return defaults;
        }
    }

    private void maybeAttachBgColorListener(LDClient ld, LDContext ctx) {
        String key = ctx.getKey();
        if (bgColorListenerKeys.contains(key)) {
            return;
        }
        try {
            FlagTracker tracker = ld.getFlagTracker();
            tracker.addFlagValueChangeListener("MAM_BG_COLOR", ctx, event ->
                    log.info("[LaunchDarkly] MAM_BG_COLOR changed for {}: {} -> {}",
                            key, event.getOldValue(), event.getNewValue()));
            bgColorListenerKeys.add(key);
        } catch (Exception e) {
            log.debug("LD flag listener attach skipped", e);
        }
    }

    public void trackInlineAboutLoad(String userName, double loadMs, boolean mamInlineAbout) {
        LDClient ld = getOrInitClient();
        if (ld == null || !ld.isInitialized()) {
            return;
        }
        LDContext ctx = contextForUser(userName);
        if (ctx == null) {
            return;
        }
        try {
            LDValue data = LDValue.buildObject()
                    .put("mam_inline_about", LDValue.of(mamInlineAbout))
                    .put("load_ms", LDValue.of(loadMs))
                    .build();
            log.info("Tracking inline_about for {} with load_ms: {} and mam_inline_about: {}",
                    userName, loadMs, mamInlineAbout);
            ld.trackMetric("inline_about", ctx, data, loadMs);
        } catch (Exception e) {
            log.debug("LD track inline_about failed", e);
        }
    }

    public void trackUiColorMode(String userName, String mode) {
        if (!"light".equals(mode) && !"dark".equals(mode)) {
            return;
        }
        LDClient ld = getOrInitClient();
        if (ld == null || !ld.isInitialized()) {
            return;
        }
        LDContext ctx = contextForUser(userName);
        if (ctx == null) {
            return;
        }
        try {
            LDValue data = LDValue.buildObject().put("mode", LDValue.of(mode)).build();
            ld.trackData("ui_color_mode", ctx, data);
        } catch (Exception e) {
            log.debug("LD track ui_color_mode failed", e);
        }
    }

    public void reportUiColorModeWhenFlagOff(String userName, FeatureFlags flags, HttpSession session) {
        if (flags.mamDarkMode()) {
            return;
        }
        if (Boolean.TRUE.equals(session.getAttribute(SessionKeys.LD_UI_COLOR_MODE_SENT))) {
            return;
        }
        trackUiColorMode(userName, "light");
        session.setAttribute(SessionKeys.LD_UI_COLOR_MODE_SENT, Boolean.TRUE);
    }

    public void trackNavClick(String userName, String direction, String fromSlug, String toSlug) {
        LDClient ld = getOrInitClient();
        if (ld == null || !ld.isInitialized()) {
            return;
        }
        LDContext ctx = contextForUser(userName);
        if (ctx == null) {
            return;
        }
        try {
            LDValue data = LDValue.buildObject()
                    .put("from_page", LDValue.of(fromSlug))
                    .put("to_page", LDValue.of(toSlug))
                    .build();
            ld.trackData("nav_click_" + direction, ctx, data);
        } catch (Exception e) {
            log.debug("LD track nav failed", e);
        }
    }

    public void trackNavCaseToggle(String userName, String previousCase, String newCase, String fromPage) {
        LDClient ld = getOrInitClient();
        if (ld == null || !ld.isInitialized()) {
            return;
        }
        LDContext ctx = contextForUser(userName);
        if (ctx == null) {
            return;
        }
        try {
            LDValue data = LDValue.buildObject()
                    .put("previous_case", LDValue.of(previousCase))
                    .put("new_case", LDValue.of(newCase))
                    .put("from_page", LDValue.of(fromPage == null ? "" : fromPage))
                    .build();
            ld.trackData("nav_case_toggle_clicked", ctx, data);
        } catch (Exception e) {
            log.debug("LD track nav_case_toggle failed", e);
        }
    }

    @PreDestroy
    public void shutdown() {
        synchronized (clientLock) {
            if (client != null) {
                try {
                    client.close();
                } catch (IOException e) {
                    log.warn("LaunchDarkly client close failed", e);
                }
                client = null;
            }
        }
    }
}
