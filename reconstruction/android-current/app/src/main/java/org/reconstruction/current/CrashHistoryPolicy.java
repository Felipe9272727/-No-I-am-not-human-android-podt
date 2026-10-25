package org.reconstruction.current;

/** Event-time rules kept independent of Android for regression checks. */
final class CrashHistoryPolicy {
    static boolean shouldNotify(long eventTime, long installedAt, long seenTime, String eventId, String seenId) {
        return eventTime > 0 && eventTime >= installedAt && eventTime > seenTime &&
            eventId != null && !eventId.isEmpty() && !eventId.equals(seenId);
    }

    static boolean matchesJavaCapture(long exitTime, boolean isJavaCrash, long capturedAt) {
        return isJavaCrash && exitTime > 0 && capturedAt > 0 && Math.abs(exitTime - capturedAt) <= 10000;
    }
}
