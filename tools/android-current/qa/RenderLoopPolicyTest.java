package org.reconstruction.current;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.Graphics;
import org.json.JSONObject;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;

/** A sleeping GL surface must wake for new state and animate only scene phases. */
public final class RenderLoopPolicyTest {
    public static void main(String[] args)throws Exception {
        final boolean[] continuous={true};final int[] requests={0};
        Gdx.graphics=(Graphics)Proxy.newProxyInstance(Graphics.class.getClassLoader(),new Class[]{Graphics.class},(p,m,a)->{
            if(m.getName().equals("setContinuousRendering")){continuous[0]=(Boolean)a[0];return null;}
            if(m.getName().equals("requestRendering")){requests[0]++;return null;}
            if(m.getReturnType()==boolean.class)return false;
            if(m.getReturnType()==int.class)return 0;
            if(m.getReturnType()==float.class)return 0f;
            if(m.getReturnType()==long.class)return 0L;
            return null;
        });
        RoomEngine engine=new RoomEngine();
        Method apply=RoomEngine.class.getDeclaredMethod("applyPendingState");apply.setAccessible(true);
        String[] phases={"menu","intro","playing","tools","boundary","playing","menu"};
        for(String phase:phases) {
            int previous=requests[0];engine.setState(new JSONObject().put("phase",phase));
            if(requests[0]!=previous+1)throw new AssertionError("State did not wake GL surface");
            apply.invoke(engine);
            if(continuous[0]!=(phase.equals("playing")||phase.equals("tools")))throw new AssertionError("Wrong GL loop in "+phase);
        }
        System.out.println("RenderLoopPolicyTest: PASS (scene animation and idle wake/sleep transitions)");
    }
}
