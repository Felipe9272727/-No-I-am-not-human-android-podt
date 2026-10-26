package org.reconstruction.current;

import com.badlogic.gdx.math.Vector3;
import com.badlogic.gdx.utils.GdxNativesLoader;
import org.json.JSONObject;
import java.nio.file.Files;
import java.nio.file.Path;

/** Checks the six actual source hinges, source timing/easing and reflected rotation. */
public final class DoorMotionTest {
    private static void near(float got,float want){if(Math.abs(got-want)>0.0002f)throw new AssertionError(got+" != "+want);}
    public static void main(String[] args)throws Exception{
        GdxNativesLoader.load();
        JSONObject world=new JSONObject(Files.readString(Path.of("reconstruction/android-current/app/src/main/assets/world/world_manifest.json")));
        JSONObject source=new JSONObject(Files.readString(Path.of("reconstruction/reverse-animations/animation_manifest.json")));
        DoorMotion motion=new DoorMotion(world,source);
        if(motion.roomMask()!=0b1011111)throw new AssertionError("six source interior doors missing: "+motion.roomMask());
        int[] ids={2141,2080,2186,2149,2167,-1,2089};
        float[] angles={-90,-89,-90,-75,-90,0,-90};
        for(int room=0;room<7;room++){
            if(room==5){if(motion.open(room))throw new AssertionError("unrecovered front-door animation invented");continue;}
            if(!motion.open(room))throw new AssertionError("door missing "+room);
            DoorMotion.Door door=motion.forRoom(room);
            if(door!=motion.forRenderer(ids[room]))throw new AssertionError("wrong hinge/renderer mapping");
            near(door.duration,1);near(door.closeModifier,2);near(door.openAngle,angles[room]);
            motion.advance(.5f);near(door.angle,angles[room]*.875f);
            if(!motion.moving())throw new AssertionError("early completion");
            motion.advance(.5f);near(door.angle,angles[room]);
            if(motion.moving())throw new AssertionError("missing completion");
            Vector3 hinge=new Vector3(door.px,door.py,door.pz);
            Vector3 moved=new Vector3(hinge).mul(door.delta);
            near(moved.x,hinge.x);near(moved.y,hinge.y);near(moved.z,hinge.z);
            Vector3 point=new Vector3(hinge).add(1,0,0).mul(door.delta);
            float radians=(float)Math.toRadians(-angles[room]);
            near(point.x,hinge.x+(float)Math.cos(radians));
            near(point.z,hinge.z-(float)Math.sin(radians));
            motion.close();motion.advance(.25f);
            near(door.angle,angles[room]*(float)Math.cos(Math.PI/4));
            motion.advance(.25f);near(door.angle,0);
            if(motion.moving())throw new AssertionError("close did not complete after 0.5s");
            motion.open(room);motion.advance(.25f);motion.reset();near(door.angle,0);
        }
        System.out.println("PASS DoorMotionTest: six authored hinges, Y reflection, OutCubic/InSine and 1s/0.5s timing");
    }
}
