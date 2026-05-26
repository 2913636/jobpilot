"use client";

import { useEffect } from "react";

interface Metric {
  name: string;
  value: number;
  rating: "good" | "needs-improvement" | "poor";
  delta: number;
}

const reportWebVitals = (metric: Metric) => {
  if (process.env.NODE_ENV === "production") {
    const body = {
      name: metric.name,
      value: metric.value,
      rating: metric.rating,
      page: window.location.pathname,
    };
    navigator.sendBeacon("/api/agents/metrics/web-vitals", JSON.stringify(body));
  } else {
    console.debug(`[WebVitals] ${metric.name}: ${metric.value}ms (${metric.rating})`);
  }
};

export function WebVitalsReporter() {
  useEffect(() => {
    let LCP: number, FCP: number, CLS: number, INP: number;

    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.entryType === "largest-contentful-paint") {
            LCP = entry.startTime;
            reportWebVitals({
              name: "LCP", value: LCP,
              rating: LCP < 2500 ? "good" : LCP < 4000 ? "needs-improvement" : "poor",
              delta: LCP,
            });
          }
        }
      }).observe({ type: "largest-contentful-paint", buffered: true });

      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.name === "first-contentful-paint") {
            FCP = entry.startTime;
            reportWebVitals({
              name: "FCP", value: FCP,
              rating: FCP < 1800 ? "good" : FCP < 3000 ? "needs-improvement" : "poor",
              delta: FCP,
            });
          }
        }
      }).observe({ type: "paint", buffered: true });

      new PerformanceObserver((list) => {
        let score = 0;
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) score += entry.value;
        }
        CLS = score;
        reportWebVitals({
          name: "CLS", value: CLS,
          rating: CLS < 0.1 ? "good" : CLS < 0.25 ? "needs-improvement" : "poor",
          delta: CLS,
        });
      }).observe({ type: "layout-shift", buffered: true });
    } catch {
      // Non-browser env
    }
  }, []);

  return null;
}
