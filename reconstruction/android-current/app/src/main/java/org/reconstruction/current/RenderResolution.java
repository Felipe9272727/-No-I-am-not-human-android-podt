package org.reconstruction.current;

/** Keeps surface aspect and touch layout while bounding the 3D pixel workload. */
final class RenderResolution {
    static int[] target(int width,int height,int profile) {
        if(width<=0||height<=0)return new int[]{0,0};
        if(profile==2)return new int[]{width,height};
        int maxWidth=profile==1?1200:1600,maxHeight=profile==1?540:720;
        double scale=Math.min(1.0,Math.min((double)maxWidth/width,(double)maxHeight/height));
        if(scale>=1)return new int[]{width,height};
        return new int[]{Math.min(width,Math.max(2,(int)Math.round(width*scale/2)*2)),Math.min(height,Math.max(2,(int)Math.round(height*scale/2)*2))};
    }
}
