package com.darkmatter.web;

import com.darkmatter.model.FeatureFlags;
import com.darkmatter.service.LaunchDarklyService;
import com.darkmatter.support.SessionKeys;
import jakarta.servlet.http.HttpSession;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api")
public class ApiController {

    private final LaunchDarklyService ld;

    public ApiController(LaunchDarklyService ld) {
        this.ld = ld;
    }

    @PostMapping("/ui-color-mode")
    public ResponseEntity<Map<String, Object>> uiColorMode(@RequestBody(required = false) Map<String, Object> body,
                                                           HttpSession session) {
        String name = (String) session.getAttribute(SessionKeys.NAME);
        FeatureFlags flags = ld.featureFlags(name);
        if (!flags.mamDarkMode()) {
            return ResponseEntity.ok(Map.of("ok", true, "ignored", true));
        }
        String mode = body == null ? "" : String.valueOf(body.getOrDefault("mode", ""));
        mode = mode.toLowerCase();
        if (!"light".equals(mode) && !"dark".equals(mode)) {
            return ResponseEntity.badRequest().body(Map.of("error", "mode must be light or dark"));
        }
        ld.trackUiColorMode(name, mode);
        return ResponseEntity.ok(Map.of("ok", true));
    }

    @PostMapping("/inline-about-load")
    public ResponseEntity<Map<String, Object>> inlineAboutLoad(@RequestBody(required = false) Map<String, Object> body,
                                                               HttpSession session) {
        String name = (String) session.getAttribute(SessionKeys.NAME);
        FeatureFlags flags = ld.featureFlags(name);
        Object raw = body == null ? null : body.get("load_ms");
        double loadMs;
        try {
            if (raw instanceof Number n) {
                loadMs = n.doubleValue();
            } else if (raw != null) {
                loadMs = Double.parseDouble(raw.toString());
            } else {
                return ResponseEntity.badRequest().body(Map.of("error", "invalid load_ms"));
            }
        } catch (NumberFormatException e) {
            return ResponseEntity.badRequest().body(Map.of("error", "invalid load_ms"));
        }
        if (loadMs < 0 || loadMs > 600000) {
            return ResponseEntity.badRequest().body(Map.of("error", "load_ms out of range"));
        }
        ld.trackInlineAboutLoad(name, loadMs, flags.mamInlineAbout());
        return ResponseEntity.ok(Map.of("ok", true));
    }
}
