package org.reconstruction.current;

public final class RenderResolutionTest {
    public static void main(String[] args) {
        int[][] screens={{2712,1220},{2400,1080},{1920,1080},{1280,720},{854,480}};
        for(int[] screen:screens)for(int mode=0;mode<3;mode++) {
            int[] result=RenderResolution.target(screen[0],screen[1],mode);
            if(result[0]>screen[0]||result[1]>screen[1]||result[0]<=0||result[1]<=0)throw new AssertionError("Upscaled or invalid render surface");
            if(Math.abs((double)result[0]/result[1]-(double)screen[0]/screen[1])>.01)throw new AssertionError("Render surface distorts display aspect");
            if(mode==2&&(result[0]!=screen[0]||result[1]!=screen[1]))throw new AssertionError("Native mode changed resolution");
        }
        int[] balanced=RenderResolution.target(2712,1220,0),light=RenderResolution.target(2712,1220,1);
        if(balanced[0]>1600||balanced[1]>720||light[0]>1200||light[1]>540)throw new AssertionError("Profile exceeded pixel cap");
        if((long)balanced[0]*balanced[1]>2712L*1220*.36)throw new AssertionError("Balanced profile did not reduce native pixel work");
        System.out.println("RenderResolutionTest: PASS (5 display sizes, 3 modes; balanced "+balanced[0]+"x"+balanced[1]+", light "+light[0]+"x"+light[1]+")");
    }
}
