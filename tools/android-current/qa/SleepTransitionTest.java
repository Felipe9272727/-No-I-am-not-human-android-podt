package org.reconstruction.current;

public final class SleepTransitionTest {
    public static void main(String[] args) {
        ackWaitsForIdleAndIsClaimedOnce();
        lifecycleTimeDoesNotAdvanceFade();
        cancellationClearsStaleTransition();
        dayMusicFollowsCampaignStateThroughTvDialogue();
        System.out.println("SleepTransitionTest: PASS");
    }

    private static void ackWaitsForIdleAndIsClaimedOnce() {
        SleepTransition transition=new SleepTransition();
        transition.beginToBlack(100L);
        transition.tick(600L,true);
        check(transition.mode()==SleepTransition.WAITING_FOR_DAY_ACK,"fade completion enters ACK wait");
        check(transition.blackAlpha()==255,"ACK wait keeps screen black");
        check(!transition.claimDayTransitionAck(true,true),"busy native worker defers ACK");
        check(transition.needsAckRetry(),"deferred ACK remains retryable");
        check(transition.claimDayTransitionAck(false,true),"idle native worker receives ACK");
        check(!transition.needsAckRetry(),"claimed ACK is not retried");
        check(!transition.claimDayTransitionAck(false,true),"ACK is sent once");
    }

    private static void lifecycleTimeDoesNotAdvanceFade() {
        SleepTransition transition=new SleepTransition();
        transition.beginToBlack(0L);
        transition.tick(200L,true);
        transition.onHostPause(200L);
        transition.onHostResume(10000L);
        transition.tick(10001L,true);
        check(transition.mode()==SleepTransition.TO_BLACK,"background duration does not finish fade");
        check(transition.blackAlpha()>=100 && transition.blackAlpha()<=103,"fade resumes near its paused opacity");
        transition.tick(10300L,true);
        check(transition.mode()==SleepTransition.WAITING_FOR_DAY_ACK,"visible time completes remaining fade");
    }

    private static void cancellationClearsStaleTransition() {
        SleepTransition transition=new SleepTransition();
        transition.beginToBlack(0L);
        transition.tick(150L,true);
        transition.cancel(); // e.g. a new game or menu state supersedes an old pending transition
        check(transition.mode()==SleepTransition.IDLE && transition.blackAlpha()==0,"cancel clears stale fade");
        transition.beginToBlack(1000L);
        transition.tick(1500L,true);
        check(transition.mode()==SleepTransition.WAITING_FOR_DAY_ACK,"fresh transition can start after cancellation");
    }

    private static void dayMusicFollowsCampaignStateThroughTvDialogue() {
        check(!SleepTransition.useDayMusic("day",0,false),"source day zero remains night");
        check(!SleepTransition.useDayMusic("day",1,true),"pending transition defers day track");
        check(SleepTransition.useDayMusic("day",1,false),"day one keeps day track, including during TV dialogue");
        check(!SleepTransition.useDayMusic("night",1,false),"night state keeps night track");
    }

    private static void check(boolean condition,String message) {
        if(!condition)throw new AssertionError(message);
    }
}
