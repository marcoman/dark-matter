package com.darkmatter.support;

import java.util.Map;
import java.util.Set;

public final class Navigation {

    public record Edge(String path, String slug) {}

    /** Enabled compass directions per corner page (matches Python templates). */
    public record CompassDirs(boolean up, boolean down, boolean left, boolean right) {}

    private static final Map<String, CompassDirs> COMPASS = Map.of(
            "upper-left", new CompassDirs(false, true, false, true),
            "upper-right", new CompassDirs(false, true, true, false),
            "lower-left", new CompassDirs(true, false, false, true),
            "lower-right", new CompassDirs(true, false, true, false)
    );

    public static CompassDirs compassDirs(String slug) {
        return COMPASS.getOrDefault(slug, COMPASS.get("upper-left"));
    }

    private static final Map<String, Map<String, Edge>> TRANSITIONS = Map.of(
            "upper-left", Map.of(
                    "right", new Edge("/upper-right", "upper-right"),
                    "down", new Edge("/lower-left", "lower-left")
            ),
            "upper-right", Map.of(
                    "left", new Edge("/upper-left", "upper-left"),
                    "down", new Edge("/lower-right", "lower-right")
            ),
            "lower-left", Map.of(
                    "right", new Edge("/lower-right", "lower-right"),
                    "up", new Edge("/upper-left", "upper-left")
            ),
            "lower-right", Map.of(
                    "up", new Edge("/upper-right", "upper-right"),
                    "left", new Edge("/lower-left", "lower-left")
            )
    );

    public static final Set<String> VALID_DIRECTIONS = Set.of("up", "down", "left", "right");

    private Navigation() {}

    /** Normalized "from" slug for metrics (matches Python session semantics). */
    public static String normalizeFromSlug(String currentSlug) {
        if (currentSlug == null || !TRANSITIONS.containsKey(currentSlug)) {
            return "upper-left";
        }
        return currentSlug;
    }

    public static Edge resolve(String currentSlug, String direction) {
        String from = normalizeFromSlug(currentSlug);
        Map<String, Edge> edges = TRANSITIONS.get(from);
        if (edges == null) {
            return null;
        }
        return edges.get(direction.toLowerCase());
    }
}
