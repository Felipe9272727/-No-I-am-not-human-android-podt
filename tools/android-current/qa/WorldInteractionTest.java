package org.reconstruction.current;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.Files;
import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.graphics.PerspectiveCamera;
import com.badlogic.gdx.math.Matrix4;
import com.badlogic.gdx.math.Vector3;
import com.badlogic.gdx.utils.GdxNativesLoader;
import org.json.JSONArray;
import org.json.JSONObject;
import java.lang.reflect.*;
import java.nio.file.Path;
import java.util.List;
import java.util.Random;

/** Compare allocation-free rays to v0.6 and exercise cached action invalidation. */
public final class WorldInteractionTest {
    public static void main(String[] args)throws Exception {
        GdxNativesLoader.load();
        Path root=Path.of("reconstruction/android-current/app/src/main/assets").toAbsolutePath();
        Gdx.files=(Files)Proxy.newProxyInstance(Files.class.getClassLoader(),new Class[]{Files.class},(p,m,a)->{
            if("internal".equals(m.getName()))return new FileHandle(root.resolve((String)a[0]).toFile());
            throw new UnsupportedOperationException(m.getName());
        });
        JSONObject manifest=new JSONObject(java.nio.file.Files.readString(root.resolve("world/world_manifest.json")));
        WorldRenderer renderer=new WorldRenderer("");set(renderer,"manifestDirectory","world/");
        call(renderer,"parseColliders",new Class[]{JSONArray.class,JSONArray.class},manifest.getJSONArray("colliders"),manifest.getJSONArray("meshes"));
        call(renderer,"parseTargets",new Class[]{JSONArray.class,JSONArray.class},manifest.getJSONArray("interaction_targets"),manifest.getJSONArray("named_door_targets"));
        JSONObject nav=new JSONObject().put("room_doors",new JSONArray()).put("entrance_interaction",new JSONObject().put("collider_path_id",2432));
        apply(renderer,nav,true);
        List<?> targets=(List<?>)get(renderer,"interactions");
        Class<?> boxClass=Class.forName("org.reconstruction.current.WorldRenderer$BoxCollider");
        Method ray=WorldRenderer.class.getDeclaredMethod("rayBox",boxClass,Vector3.class,Vector3.class,float.class);ray.setAccessible(true);
        Random random=new Random(72417);Object entrance=null;int cases=0;
        for(Object target:targets) {
            Object box=get(target,"box");if((Integer)get(target,"colliderId")==2432)entrance=box;
            Matrix4 world=new Matrix4((Matrix4)get(box,"inverse")).inv();
            Vector3 center=new Vector3((Float)get(box,"cx"),(Float)get(box,"cy"),(Float)get(box,"cz")).mul(world);
            for(int i=0;i<2000;i++) {
                Vector3 origin=new Vector3(center).add(random.nextFloat()*4-2,random.nextFloat()*4-2,random.nextFloat()*4-2);
                Vector3 direction=i%4==0?new Vector3(1,0,0):new Vector3(random.nextFloat()*2-1,random.nextFloat()*2-1,random.nextFloat()*2-1).nor();
                float max=i%3==0?1f:4f;
                float expected=legacyRay(box,origin,direction,max),actual=(Float)ray.invoke(renderer,box,origin,direction,max);
                if(Float.floatToIntBits(expected)!=Float.floatToIntBits(actual))throw new AssertionError("Ray changed: "+expected+" vs "+actual);
                cases++;
            }
        }
        if(entrance==null)throw new AssertionError("Missing source entrance");
        Matrix4 world=new Matrix4((Matrix4)get(entrance,"inverse")).inv();
        PerspectiveCamera camera=new PerspectiveCamera(60,1280,720);
        camera.position.set((Float)get(entrance,"cx"),(Float)get(entrance,"cy"),(Float)get(entrance,"cz")).mul(world);
        camera.direction.set(0,0,-1);set(renderer,"camera",camera);
        Method update=WorldRenderer.class.getDeclaredMethod("updateInteraction");update.setAccessible(true);update.invoke(renderer);
        String initial=renderer.getInteractionJson();
        if(!"open_door".equals(new JSONObject(initial).getString("action")))throw new AssertionError("Wrong waiting entrance action");
        for(int i=0;i<10000;i++)update.invoke(renderer);
        if(renderer.getInteractionJson()!=initial)throw new AssertionError("Unchanged target was republished");
        renderer.getInteraction().put("action","tampered");
        if(!"open_door".equals(new JSONObject(renderer.getInteractionJson()).getString("action")))throw new AssertionError("Caller mutated published snapshot");
        apply(renderer,nav,false);update.invoke(renderer);
        if(!"enter_room".equals(new JSONObject(renderer.getInteractionJson()).getString("action")))throw new AssertionError("Door action cache remained stale after navigation change");
        camera.position.set(10000,10000,10000);update.invoke(renderer);
        if(!renderer.getInteractionJson().isEmpty()||renderer.getInteraction()!=null)throw new AssertionError("Miss did not clear target");
        System.out.println("WorldInteractionTest: PASS ("+cases+" bit-exact rays; stable snapshot, safe copies, action refresh and miss)");
    }
    private static void apply(WorldRenderer r,JSONObject nav,boolean waiting)throws Exception{r.applyState(new JSONObject().put("view_mode","world").put("world_navigation",nav).put("campaign",new JSONObject().put("door_waiting",waiting)));}
    private static float legacyRay(Object b,Vector3 origin,Vector3 direction,float max)throws Exception {
        Matrix4 inverse=(Matrix4)get(b,"inverse");Vector3 o=new Vector3(origin).mul(inverse),d=new Vector3(direction).rot(inverse);
        float[] a={o.x-(Float)get(b,"cx"),o.y-(Float)get(b,"cy"),o.z-(Float)get(b,"cz")},v={d.x,d.y,d.z},h={(Float)get(b,"hx"),(Float)get(b,"hy"),(Float)get(b,"hz")};
        float lo=0,hi=max;for(int n=0;n<3;n++){if(Math.abs(v[n])<1e-6f){if(a[n]<-h[n]||a[n]>h[n])return -1;continue;}float q=(-h[n]-a[n])/v[n],r=(h[n]-a[n])/v[n];if(q>r){float t=q;q=r;r=t;}lo=Math.max(lo,q);hi=Math.min(hi,r);if(lo>hi)return -1;}return lo<=max?lo:-1;
    }
    private static Object get(Object o,String name)throws Exception{Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(o);}
    private static void set(Object o,String name,Object v)throws Exception{Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);f.set(o,v);}
    private static void call(Object o,String name,Class<?>[] types,Object...args)throws Exception{Method m=o.getClass().getDeclaredMethod(name,types);m.setAccessible(true);m.invoke(o,args);}
}
