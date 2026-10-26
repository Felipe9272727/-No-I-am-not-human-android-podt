package org.reconstruction.current;

/** Pure timing and ACK policy for the adapted night-to-day sleep transition. */
final class SleepTransition {
    static final int IDLE = 0;
    static final int TO_BLACK = 1;
    static final int WAITING_FOR_DAY_ACK = 2;
    static final int REVEALING_DAY = -1;
    static final long DURATION_MS = 500L;

    private int mode = IDLE;
    private long elapsedMs;
    private long lastTickMs;
    private boolean ackSent;

    int mode() { return mode; }
    boolean isActive() { return mode != IDLE; }
    boolean isBlocking() { return isActive(); }

    void beginToBlack(long nowMs) {
        mode = TO_BLACK;
        elapsedMs = 0L;
        lastTickMs = nowMs;
        ackSent = false;
    }

    void beginReveal(long nowMs) {
        mode = REVEALING_DAY;
        elapsedMs = 0L;
        lastTickMs = nowMs;
    }

    void cancel() {
        mode = IDLE;
        elapsedMs = 0L;
        ackSent = false;
    }

    /** Rebase the animation clock at host lifecycle boundaries so background time is not consumed. */
    void onHostPause(long nowMs) { lastTickMs = nowMs; }
    void onHostResume(long nowMs) { lastTickMs = nowMs; }

    /** Advances only while the activity is visible and its game UI is not paused. */
    void tick(long nowMs, boolean advancing) {
        if (mode != TO_BLACK && mode != REVEALING_DAY) {
            lastTickMs = nowMs;
            return;
        }
        if (advancing) elapsedMs += Math.max(0L, nowMs - lastTickMs);
        lastTickMs = nowMs;
        if (elapsedMs < DURATION_MS) return;
        if (mode == TO_BLACK) {
            mode = WAITING_FOR_DAY_ACK;
            elapsedMs = 0L;
        } else {
            mode = IDLE;
            elapsedMs = 0L;
        }
    }

    /** Claims the native ACK once, and only after the fade has finished and native work is idle. */
    boolean claimDayTransitionAck(boolean nativeBusy, boolean transitionPending) {
        if (mode != WAITING_FOR_DAY_ACK || ackSent || nativeBusy || !transitionPending) return false;
        ackSent = true;
        return true;
    }

    boolean needsAckRetry() { return mode == WAITING_FOR_DAY_ACK && !ackSent; }

    int blackAlpha() {
        if (mode == WAITING_FOR_DAY_ACK) return 255;
        if (mode != TO_BLACK && mode != REVEALING_DAY) return 0;
        float progress = Math.max(0f, Math.min(1f, elapsedMs / (float) DURATION_MS));
        return Math.round((mode == TO_BLACK ? progress : 1f - progress) * 255f);
    }

    static boolean useDayMusic(String timeOfDay, int day, boolean transitionPending) {
        return "day".equals(timeOfDay) && day >= 1 && !transitionPending;
    }
}
