package com.darkmatter.model;

public record FeatureFlags(
        boolean mamAbout,
        String mamBgColor,
        boolean mamToggleCase,
        boolean mamDarkMode,
        boolean mamInlineAbout
) {
    public static FeatureFlags defaults() {
        return new FeatureFlags(false, "white", false, false, false);
    }
}
