package org.reconstruction.current;

public final class FrameSequenceTest {
    private static void eq(long got, long want) { if (got != want) throw new AssertionError(got + " != " + want); }
    public static void main(String[] args) {
        // Recovered modes: PlayOnce disables the image after N frame delays,
        // Cycle repeats, FixLastFrame keeps the final sprite visible.
        for (int mode = 0; mode <= 2; mode++) {
            eq(FrameSequence.frameAt(3, 8, mode, 0), 0);
            eq(FrameSequence.frameAt(3, 8, mode, 124), 0);
            eq(FrameSequence.frameAt(3, 8, mode, 125), 1);
            eq(FrameSequence.frameAt(3, 8, mode, 250), 2);
            eq(FrameSequence.frameAt(3, 8, mode, 375), mode == 0 ? -1 : mode == 1 ? 0 : 2);
        }
        eq(FrameSequence.nextFrameDelay(3, 8, 0, 250), 125); // must hide after last frame
        eq(FrameSequence.nextFrameDelay(3, 8, 0, 375), -1);
        eq(FrameSequence.nextFrameDelay(3, 8, 2, 250), -1);
        eq(FrameSequence.nextFrameDelay(3, 8, 1, 374), 1);
        eq(FrameSequence.frameAt(1, 8, 0, 125), -1);
        eq(FrameSequence.frameAt(1, 8, 1, 10000), 0);
        eq(FrameSequence.frameAt(0, 8, 1, 100), -1);
        eq(FrameSequence.frameAt(3, 0, 1, 10000), 0);
        eq(FrameSequence.frameAt(3, 8, 2, -50), 0);
        eq(FrameSequence.frameAt(3, Integer.MAX_VALUE, 2, Long.MAX_VALUE), 2);
        FrameSequence.Clock c = new FrameSequence.Clock();
        eq(c.now(100), 100);
        c.setPaused(true, 200); eq(c.now(1200), 200);
        c.setPaused(true, 1400); c.setPaused(false, 2200); eq(c.now(2250), 250);
        c.setPaused(true, 2300); c.setPaused(false, 2400); eq(c.now(2500), 400);
        System.out.println("PASS FrameSequenceTest: source cycling modes, boundaries, pause/resume");
    }
}
