package org.reconstruction.current;

public final class SignLayoutMotionTest {
    public static void main(String[] args) {
        handsTweenUsesSourceInSineAndCanvasYAxis();
        photoTweenKeepsItsTwoSecondDelayAndOutCubic();
        staticLayersDoNotAcquireContentMotion();
        System.out.println("SignLayoutMotionTest: PASS");
    }

    private static void handsTweenUsesSourceInSineAndCanvasYAxis() {
        SignLayout.Movement motion=new SignLayout.Movement(5178,2,
            new float[]{0,-400,0},new float[]{0,0,0},.666667f,0,true);
        SignLayout.Layer content=new SignLayout.Layer(5178,3,1919,4527,"content","",
            new float[]{959.4084f,230.5715f,1669.09f,622.4329f},true,motion);
        float[] start=content.rectAt(0);
        check(close(start[1],630.5715f),"Hands starts 400 source units below its authored content position");
        float[] middle=content.rectAt(333);
        check(close(middle[1],513.57f),"Hands uses DG Ease.InSine at halfway");
        float[] end=content.rectAt(667);
        check(close(end[1],230.5715f),"Hands ends at the authored content rectangle");
        SignLayout.View view=new SignLayout.View(SignLayout.HANDS,"hands",new float[4],
            java.util.Collections.singletonList(content),motion,true,false);
        check(view.nextRedrawDelayMs(0)==16 && view.nextRedrawDelayMs(667)==0,
            "Hands only requests redraw while the tween is active");
    }

    private static void photoTweenKeepsItsTwoSecondDelayAndOutCubic() {
        SignLayout.Movement motion=new SignLayout.Movement(4600,9,
            new float[]{0,-1100,0},new float[]{0,0,0},1,2,true);
        SignLayout.Layer content=new SignLayout.Layer(4600,3,1661,-1,"content","",
            new float[]{1018.84f,102,1668.84f,752},true,motion);
        check(close(content.rectAt(0)[1],1202),"Photo starts 1100 units below its final rectangle");
        check(close(content.rectAt(1999)[1],1202),"Photo waits for its authored 2 second delay");
        check(close(content.rectAt(2000)[1],1202),"Photo tween begins at the end of its delay");
        check(close(content.rectAt(2500)[1],239.5f),"Photo uses DG Ease.OutCubic at halfway");
        check(close(content.rectAt(3000)[1],102),"Photo reaches its source rectangle after 3 seconds");
        SignLayout.View view=new SignLayout.View(SignLayout.PHOTO,"photo",new float[4],
            java.util.Collections.singletonList(content),motion,true,true);
        check(view.hideDialogPlate && view.hideDialogueText,"Photo hides the source plate and normal text");
        check(view.nextRedrawDelayMs(0)==2000 && view.nextRedrawDelayMs(1999)==1,
            "Photo requests the next redraw at the end of its start delay");
        check(view.nextRedrawDelayMs(2000)==16 && view.nextRedrawDelayMs(3000)==0,
            "Photo requests frame redraws only during the tween");
    }

    private static void staticLayersDoNotAcquireContentMotion() {
        SignLayout.Layer frame=new SignLayout.Layer(4393,3,2037,4527,"static","",
            new float[]{959.4f,103.4f,1669.0f,749.6f},true,null);
        check(close(frame.rectAt(0)[1],103.4f) && close(frame.rectAt(500)[1],103.4f),
            "static source frames remain at their authored rectangles");
        SignLayout.View hands=new SignLayout.View(SignLayout.HANDS,"hands",new float[4],
            java.util.Collections.singletonList(frame),null,true,false);
        check(hands.hideDialogPlate && !hands.hideDialogueText,"Hands hides only the source panel plate");
    }

    private static boolean close(float a,float b) { return Math.abs(a-b)<.2f; }
    private static void check(boolean condition,String message) {
        if(!condition) throw new AssertionError(message);
    }
}
