package com.darkmatter.model;

public record SystemInfo(
        String javaVersion,
        String os,
        String osRelease,
        String machine,
        String processor,
        double memoryTotalGb,
        double memoryAvailableGb,
        int cpuCount
) {}
