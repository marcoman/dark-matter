package com.darkmatter.web;

import com.darkmatter.model.FeatureFlags;
import com.darkmatter.service.LaunchDarklyService;
import com.darkmatter.support.Navigation;
import com.darkmatter.support.SessionKeys;
import com.darkmatter.support.SystemInfoFactory;
import jakarta.servlet.http.HttpSession;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import java.util.List;

@Controller
public class DarkMatterController {

    private static final String AUTHOR = "Marco";
    private static final List<String> LIBRARIES = List.of(
            "spring-boot-starter-web",
            "spring-boot-starter-thymeleaf",
            "launchdarkly-java-server-sdk"
    );

    private final LaunchDarklyService ld;

    public DarkMatterController(LaunchDarklyService ld) {
        this.ld = ld;
    }

    @GetMapping("/")
    public String home(HttpSession session) {
        if (session.getAttribute(SessionKeys.NAME) != null) {
            return "redirect:/upper-left";
        }
        return "login";
    }

    @PostMapping("/")
    public String login(@RequestParam(value = "name", required = false) String name,
                        Model model,
                        HttpSession session) {
        if (name == null || name.isBlank()) {
            model.addAttribute("error", "Please enter your name.");
            return "login";
        }
        String trimmed = name.strip();
        session.setAttribute(SessionKeys.NAME, trimmed);
        session.setAttribute(SessionKeys.FROM_PAGE, null);
        session.setAttribute(SessionKeys.NAV_CASE, "lower");
        session.removeAttribute(SessionKeys.LD_UI_COLOR_MODE_SENT);
        return "redirect:/upper-left";
    }

    @GetMapping("/logout")
    public String logout(HttpSession session) {
        session.invalidate();
        return "redirect:/";
    }

    @PostMapping("/toggle-nav-case")
    public String toggleNavCase(@RequestParam(value = "next_page", required = false) String nextPage,
                                HttpSession session) {
        String userName = (String) session.getAttribute(SessionKeys.NAME);
        FeatureFlags flags = ld.featureFlags(userName);
        if (flags.mamToggleCase()) {
            String current = session.getAttribute(SessionKeys.NAV_CASE) instanceof String s ? s : "lower";
            String newCase = "lower".equals(current) ? "upper" : "lower";
            String fromPage = session.getAttribute(SessionKeys.FROM_PAGE) instanceof String fp ? fp : null;
            ld.trackNavCaseToggle(userName, current, newCase, fromPage);
            session.setAttribute(SessionKeys.NAV_CASE, newCase);
        }
        if (nextPage != null && !nextPage.isBlank()) {
            return "redirect:" + nextPage;
        }
        return "redirect:/upper-left";
    }

    @GetMapping("/nav/go/{direction}")
    public String navGo(@PathVariable String direction, HttpSession session) {
        String d = direction == null ? "" : direction.toLowerCase();
        if (!Navigation.VALID_DIRECTIONS.contains(d)) {
            return "redirect:/upper-left";
        }
        String userName = (String) session.getAttribute(SessionKeys.NAME);
        String current = session.getAttribute(SessionKeys.FROM_PAGE) instanceof String s ? s : null;
        Navigation.Edge edge = Navigation.resolve(current, d);
        if (edge == null) {
            return "redirect:/upper-left";
        }
        String fromNorm = Navigation.normalizeFromSlug(current);
        ld.trackNavClick(userName, d, fromNorm, edge.slug());
        return "redirect:" + edge.path();
    }

    @GetMapping("/upper-left")
    public String upperLeft(HttpSession session, Model model) {
        fillNavPage(session, model, "Upper Left", "upper-left");
        return "upper_left";
    }

    @GetMapping("/upper-right")
    public String upperRight(HttpSession session, Model model) {
        fillNavPage(session, model, "Upper Right", "upper-right");
        return "upper_right";
    }

    @GetMapping("/lower-left")
    public String lowerLeft(HttpSession session, Model model) {
        fillNavPage(session, model, "Lower Left", "lower-left");
        return "lower_left";
    }

    @GetMapping("/lower-right")
    public String lowerRight(HttpSession session, Model model) {
        fillNavPage(session, model, "Lower Right", "lower-right");
        return "lower_right";
    }

    @GetMapping("/about")
    public String about(HttpSession session, Model model) {
        String userName = (String) session.getAttribute(SessionKeys.NAME);
        FeatureFlags flags = ld.featureFlags(userName);
        if (!flags.mamAbout()) {
            return "redirect:/upper-left";
        }
        ld.reportUiColorModeWhenFlagOff(userName, flags, session);
        boolean navCaseUpper = "upper".equals(session.getAttribute(SessionKeys.NAV_CASE));
        model.addAttribute("name", userName);
        model.addAttribute("title", "About - Dark Matter");
        model.addAttribute("showAbout", true);
        model.addAttribute("showAboutNav", false);
        model.addAttribute("bgColor", flags.mamBgColor());
        model.addAttribute("showToggleCase", flags.mamToggleCase());
        model.addAttribute("showDarkModeToggle", flags.mamDarkMode());
        model.addAttribute("navCaseUpper", navCaseUpper);
        model.addAttribute("showInlineAbout", false);
        model.addAttribute("recordInlineLoadMetric", false);
        model.addAttribute("sysInfo", SystemInfoFactory.build());
        model.addAttribute("libraries", LIBRARIES);
        model.addAttribute("author", AUTHOR);
        return "about";
    }

    private void fillNavPage(HttpSession session, Model model, String pageTitle, String slug) {
        String userName = (String) session.getAttribute(SessionKeys.NAME);
        String fromPage = session.getAttribute(SessionKeys.FROM_PAGE) instanceof String s ? s : null;
        session.setAttribute(SessionKeys.FROM_PAGE, slug);
        FeatureFlags flags = ld.featureFlags(userName);
        ld.reportUiColorModeWhenFlagOff(userName, flags, session);
        boolean navCaseUpper = "upper".equals(session.getAttribute(SessionKeys.NAV_CASE));
        model.addAttribute("name", userName);
        model.addAttribute("fromPage", fromPage);
        model.addAttribute("title", pageTitle + " - Dark Matter");
        model.addAttribute("pageHeading", pageTitle);
        model.addAttribute("showAbout", flags.mamAbout());
        model.addAttribute("showAboutNav", flags.mamAbout());
        model.addAttribute("bgColor", flags.mamBgColor());
        model.addAttribute("showToggleCase", flags.mamToggleCase());
        model.addAttribute("showDarkModeToggle", flags.mamDarkMode());
        model.addAttribute("navCaseUpper", navCaseUpper);
        model.addAttribute("showInlineAbout", flags.mamInlineAbout());
        if (flags.mamInlineAbout()) {
            model.addAttribute("sysInfo", SystemInfoFactory.build());
            model.addAttribute("libraries", LIBRARIES);
            model.addAttribute("author", AUTHOR);
        }
        model.addAttribute("recordInlineLoadMetric", true);
        var dirs = Navigation.compassDirs(slug);
        model.addAttribute("navUp", dirs.up());
        model.addAttribute("navDown", dirs.down());
        model.addAttribute("navLeft", dirs.left());
        model.addAttribute("navRight", dirs.right());
    }
}
