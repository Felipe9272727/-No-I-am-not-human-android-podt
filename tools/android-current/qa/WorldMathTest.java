package org.reconstruction.current;

import org.json.JSONArray;
import org.json.JSONObject;

import java.lang.reflect.Method;

/** Pure Java sign/pose checks for the source-coordinate joystick mapping. */
public final class WorldMathTest {
    public static void main(String[] args) throws Exception {
        WorldRenderer world=new WorldRenderer("");
        JSONObject pose=new JSONObject();pose.put("position",new JSONArray().put(0).put(0).put(0));pose.put("yaw",0);pose.put("pitch",0);pose.put("revision",1);
        JSONObject state=new JSONObject();state.put("view_mode","world");state.put("world_pose",pose);world.applyState(state);world.setInputEnabled(true);
        Method move=WorldRenderer.class.getDeclaredMethod("movePlayer",float.class,float.class,float.class);move.setAccessible(true);
        move.invoke(world,0f,1f,.1f);
        JSONObject after=world.getPose();
        if(Math.abs(after.getJSONArray("position").getDouble(2)-.25)>1e-4)throw new AssertionError("Forward must increase source Unity +Z: "+after);
        state.getJSONObject("world_pose").put("position",new JSONArray().put(0).put(0).put(0)).put("yaw",0).put("revision",2);world.applyState(state);
        move.invoke(world,1f,0f,.1f);
        after=world.getPose();if(Math.abs(after.getJSONArray("position").getDouble(0)-.25)>1e-4)throw new AssertionError("Right must increase source Unity +X: "+after);
        state.getJSONObject("world_pose").put("position",new JSONArray().put(0).put(0).put(0)).put("yaw",90).put("revision",3);world.applyState(state);
        move.invoke(world,0f,1f,.1f);
        after=world.getPose();if(Math.abs(after.getJSONArray("position").getDouble(0)-.25)>1e-4)throw new AssertionError("Yaw right then forward must increase source +X: "+after);
        state.getJSONObject("world_pose").put("yaw",0).put("revision",4);world.applyState(state);world.addLookDelta(0,10000);
        after=world.getPose();if(after.getDouble("pitch")!=80d)throw new AssertionError("Pitch must clamp to source ±80°: "+after);
        float[] uv=WorldRenderer.unityUvTransform(2f,3f,.1f,.2f);
        float sourceV=.25f,sourceSample=sourceV*3f+.2f,gdxSample=sourceV*uv[1]+uv[3];
        if(Math.abs(gdxSample-(1f-sourceSample))>1e-6f)throw new AssertionError("Unity bottom-origin UV and top-origin PNG conversion failed");
        System.out.println("WorldMathTest: PASS");
    }
}
