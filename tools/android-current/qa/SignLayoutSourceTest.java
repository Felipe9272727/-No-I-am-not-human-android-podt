package org.reconstruction.current;

import java.nio.file.Files;
import java.nio.file.Path;
import org.json.JSONObject;

/** Exercise the real exported layout and staged UI, including the Android load contract. */
public final class SignLayoutSourceTest {
    static void require(boolean value,String message){if(!value)throw new AssertionError(message);}
    static void near(float actual,float expected,String message){require(Math.abs(actual-expected)<.03f,message+": "+actual+" != "+expected);}
    public static void main(String[] args) throws Exception {
        require(args.length==2,"sign config and UI paths required");
        JSONObject config=new JSONObject(Files.readString(Path.of(args[0])));
        JSONObject ui=new JSONObject(Files.readString(Path.of(args[1])));
        SignLayout layout=SignLayout.parse(config,ui);
        int[][] images={{4518,4760,4428},{4527,5178,4393},{4444,5094},{4600},{4536,4618},{4977,4469}};
        int layers=0;
        for(int kind=0;kind<6;kind++) {
            SignLayout.View view=layout.view(kind);require(view!=null,"missing source sign");
            require(view.hideDialogPlate,"source DialogContent Color.clear is required");
            require(view.hideDialogueText==(kind==SignLayout.PHOTO),"only source photo hides normal body text");
            require(view.layers.size()==images[kind].length,"unexpected source layer count");
            for(int j=0;j<view.layers.size();j++) {
                SignLayout.Layer layer=view.layers.get(j);layers++;
                require(layer.imageId==images[kind][j],"source sibling draw order changed");
                require(layer.sourceFileId>0&&layer.sourcePathId>0,"source sprite reference missing");
                require(layer.rect[2]>layer.rect[0]&&layer.rect[3]>layer.rect[1],"empty Image rectangle");
            }
        }
        require(layers==13,"expected 13 original Image layers");
        SignLayout.Layer hands=layout.view(SignLayout.HANDS).layers.get(1);
        require(hands.maskImageId==4527,"hands must be clipped by the original Mask image");
        near(hands.rectAt(0)[1],630.5715f,"hands start below mask");
        near(hands.rectAt(667)[1],230.5715f,"hands recovered endpoint");
        SignLayout.Layer photo=layout.view(SignLayout.PHOTO).layers.get(0);
        near(photo.rectAt(0)[1],1202f,"photo start before delay");
        near(photo.rectAt(1999)[1],1202f,"photo remains below viewport during delay");
        near(photo.rectAt(2500)[1],239.5f,"photo source OutCubic midpoint");
        near(photo.rectAt(3000)[1],102f,"photo recovered endpoint");
        require(layout.view(SignLayout.PHOTO).nextRedrawDelayMs(0)==2000,"avoid redrawing an unchanged delayed photo");
        require(layout.view(SignLayout.PHOTO).nextRedrawDelayMs(3000)==0,"finished move needs no redraw");
        System.out.println("SignLayoutSourceTest: six source views, 13 ordered layers, mask, typed sprite references and authored tween timing passed");
    }
}
