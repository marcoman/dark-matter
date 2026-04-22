package com.darkmatter.support;

import com.darkmatter.model.SystemInfo;

import java.lang.management.ManagementFactory;
import java.util.Optional;

import com.sun.management.OperatingSystemMXBean;

public final class SystemInfoFactory {

    private SystemInfoFactory() {}

    public static SystemInfo build() {
        var osBean = ManagementFactory.getOperatingSystemMXBean();
        long totalMem;
        long freeMem;
        try {
            var sunOs = (OperatingSystemMXBean) osBean;
            totalMem = sunOs.getTotalMemorySize();
            freeMem = sunOs.getFreeMemorySize();
        } catch (Exception e) {
            Runtime rt = Runtime.getRuntime();
            totalMem = rt.maxMemory();
            freeMem = rt.freeMemory();
        }
        double totalGb = round2(totalMem / (1024.0 * 1024 * 1024));
        double availGb = round2(freeMem / (1024.0 * 1024 * 1024));

        String proc = Optional.ofNullable(System.getenv("PROCESSOR_IDENTIFIER"))
                .filter(s -> !s.isBlank())
                .orElseGet(() -> System.getProperty("os.arch", "N/A"));

        return new SystemInfo(
                Runtime.version().toString(),
                System.getProperty("os.name", "unknown"),
                System.getProperty("os.version", ""),
                System.getProperty("os.arch", ""),
                proc,
                totalGb,
                availGb,
                osBean.getAvailableProcessors()
        );
    }

    private static double round2(double v) {
        return Math.round(v * 100.0) / 100.0;
    }
}
