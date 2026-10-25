package org.reconstruction.current;

import com.badlogic.gdx.graphics.PerspectiveCamera;
import com.badlogic.gdx.math.Vector3;
import org.json.JSONArray;
import org.json.JSONObject;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;

/** Regression: near source walls/ceiling must survive frustum rejection while turning. */
public final class WorldVisibilityTest {
    public static void main(String[] args) throws Exception {
        com.badlogic.gdx.utils.GdxNativesLoader.load();
        Path assets=Path.of(args.length>0?args[0]:"reconstruction/android-current/app/src/main/assets");
        JSONObject manifest=new JSONObject(Files.readString(assets.resolve("world/world_manifest.json")));
        WorldRenderer renderer=new WorldRenderer("");
        PerspectiveCamera camera=new PerspectiveCamera(60,1280,720);
        camera.near=.1f;camera.far=1000;
        JSONArray cameras=manifest.getJSONArray("cameras");
        for(int i=0;i<cameras.length();i++) {
            JSONObject row=cameras.getJSONObject(i);
            if(!"Main Camera".equals(row.optString("name")))continue;
            JSONArray matrix=row.getJSONArray("world_matrix_row_major");
            camera.position.set((float)matrix.getJSONArray(0).getDouble(3),(float)matrix.getJSONArray(1).getDouble(3),-(float)matrix.getJSONArray(2).getDouble(3));
        }
        Field field=WorldRenderer.class.getDeclaredField("camera");field.setAccessible(true);field.set(renderer,camera);
        Class<?> bounds=Class.forName("org.reconstruction.current.WorldRenderer$Bounds");
        Constructor<?> constructor=bounds.getDeclaredConstructor(float.class,float.class,float.class,float.class,float.class,float.class);constructor.setAccessible(true);
        Method visible=WorldRenderer.class.getDeclaredMethod("visible",bounds);visible.setAccessible(true);
        int checked=0;
        for(int id:new int[]{2129,2124,2133}) {
            JSONObject row=null;JSONArray renderers=manifest.getJSONArray("renderers");
            for(int i=0;i<renderers.length();i++)if(renderers.getJSONObject(i).optInt("renderer_path_id")==id)row=renderers.getJSONObject(i);
            if(row==null)throw new AssertionError("Missing source structural renderer "+id);
            JSONObject world=row.getJSONObject("world_bounds");JSONArray min=world.getJSONArray("min"),max=world.getJSONArray("max");
            Object box=constructor.newInstance((float)min.getDouble(0),(float)min.getDouble(1),-(float)max.getDouble(2),(float)max.getDouble(0),(float)max.getDouble(1),-(float)min.getDouble(2));
            for(int yaw:new int[]{0,90,180,270}) {
                double angle=Math.toRadians(yaw);
                double pitch=Math.toRadians(id==2133?35:0);
                camera.direction.set((float)(Math.sin(angle)*Math.cos(pitch)),-(float)Math.sin(pitch),-(float)(Math.cos(angle)*Math.cos(pitch)));camera.up.set(Vector3.Y);camera.update();
                if(!(Boolean)visible.invoke(renderer,box))throw new AssertionError("Visible source "+row.getString("name")+" renderer="+id+" rejected at yaw="+yaw+"; check full-size vs half-extents API");
                checked++;
            }
        }
        System.out.println("WorldVisibilityTest: PASS ("+checked+" source wall/ceiling/floor camera turns)");
    }
}
