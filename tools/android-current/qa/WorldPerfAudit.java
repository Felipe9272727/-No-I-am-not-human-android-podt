package org.reconstruction.current;

import com.badlogic.gdx.Files;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.graphics.PerspectiveCamera;
import com.badlogic.gdx.math.Matrix4;
import com.badlogic.gdx.math.Vector3;
import com.badlogic.gdx.utils.GdxNativesLoader;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.lang.management.ManagementFactory;
import java.lang.reflect.Field;
import java.lang.reflect.Proxy;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.util.List;

/** Isolated host microbenchmark for steady collision and interaction work; not a device FPS test. */
public final class WorldPerfAudit {
    private static final long THREAD_ID=Thread.currentThread().getId();
    private static final com.sun.management.ThreadMXBean ALLOC=(com.sun.management.ThreadMXBean)ManagementFactory.getThreadMXBean();
    public static void main(String[] args)throws Throwable{
        GdxNativesLoader.load();
        File assetRoot=new File(args.length>0?args[0]:"reconstruction/android-current/app/src/main/assets").getCanonicalFile();
        Gdx.files=(Files)Proxy.newProxyInstance(Files.class.getClassLoader(),new Class<?>[]{Files.class},(proxy,method,values)->{
            if("internal".equals(method.getName()))return new FileHandle(new File(assetRoot,(String)values[0]));
            throw new UnsupportedOperationException(method.getName());
        });
        JSONObject manifest=new JSONObject(new String(java.nio.file.Files.readAllBytes(new File(assetRoot,"world/world_manifest.json").toPath()),java.nio.charset.StandardCharsets.UTF_8));
        WorldRenderer renderer=new WorldRenderer("");set(renderer,"manifestDirectory","world/");
        call(renderer,"parseColliders",new Class[]{JSONArray.class,JSONArray.class},manifest.optJSONArray("colliders"),manifest.optJSONArray("meshes"));
        call(renderer,"parseTargets",new Class[]{JSONArray.class,JSONArray.class},manifest.optJSONArray("interaction_targets"),manifest.optJSONArray("named_door_targets"));
        JSONArray doors=new JSONArray();int[] ids={2425,2449,2452,2453,2460,2439},rooms={0,1,2,3,4,6};for(int i=0;i<ids.length;i++)doors.put(new JSONObject().put("collider_path_id",ids[i]).put("room",rooms[i]));
        JSONObject nav=new JSONObject().put("room_doors",doors).put("entrance_interaction",new JSONObject().put("collider_path_id",2432));
        JSONObject pose=new JSONObject().put("position",new JSONArray().put(-3.985).put(1.584).put(-6.998)).put("yaw",0).put("pitch",0).put("revision",1);
        renderer.applyState(new JSONObject().put("view_mode","world").put("world_navigation",nav).put("world_pose",pose));
        PerspectiveCamera camera=new PerspectiveCamera(60,800,600);camera.position.set(-3.985f,1.584f,6.998f);camera.direction.set(0,0,-1);camera.up.set(Vector3.Y);set(renderer,"camera",camera);
        MethodHandle floor=method("floorY",MethodType.methodType(float.class,float.class,float.class,float.class));
        MethodHandle collides=method("collides",MethodType.methodType(boolean.class,float.class,float.class,float.class));
        MethodHandle move=method("movePlayer",MethodType.methodType(void.class,float.class,float.class,float.class));
        MethodHandle interaction=method("updateInteraction",MethodType.methodType(void.class));
        reportCandidates(renderer,-3.985f,1.584f,6.998f);
        int warm=30000,loops=100000;float x=-3.985f,z=6.998f,foot=1.584f-1.65f;
        for(int i=0;i<warm;i++){sink+=(int)((float)floor.invokeExact(renderer,x,z,foot));sink^=(boolean)collides.invokeExact(renderer,x,1.584f,z)?1:0;}
        bench("floorY_spawn",loops,()->{for(int i=0;i<loops;i++)sink+=(float)floor.invokeExact(renderer,x,z,foot);});
        bench("collides_spawn",loops,()->{for(int i=0;i<loops;i++)sink^=(boolean)collides.invokeExact(renderer,x,1.584f,z)?1:0;});
        bench("movePlayer_idle",loops,()->{for(int i=0;i<loops;i++)move.invokeExact(renderer,0f,0f,.016f);});
        // Walk until source collision stops the player, then hold movement at contact.
        for(int i=0;i<200;i++)move.invokeExact(renderer,0f,1f,.016f);
        Vector3 player=(Vector3)get(renderer,"player");System.out.println("PLAYER_AT_CONTACT="+player);reportCandidates(renderer,player.x,player.y,player.z);
        bench("movePlayer_at_contact",loops,()->{for(int i=0;i<loops;i++){move.invokeExact(renderer,0f,1f,.016f);renderer.addLookDelta(.2f,0f);}});
        camera.position.set(-3.985f,1.584f,6.998f);camera.direction.set(0,0,-1);camera.update();
        for(int i=0;i<warm;i++)interaction.invokeExact(renderer);
        bench("updateInteraction_spawn_miss",loops,()->{for(int i=0;i<loops;i++)interaction.invokeExact(renderer);});
        Object first=first(get(renderer,"interactions"));Object box=get(first,"box");Matrix4 inverse=(Matrix4)get(box,"inverse"),world=new Matrix4(inverse).inv();Vector3 center=new Vector3((float)get(box,"cx"),(float)get(box,"cy"),(float)get(box,"cz")).mul(world);camera.position.set(center);camera.direction.set(0,0,-1);camera.update();
        for(int i=0;i<warm;i++)interaction.invokeExact(renderer);
        bench("updateInteraction_inside_box",loops,()->{for(int i=0;i<loops;i++)interaction.invokeExact(renderer);});
        System.out.println("SINK="+sink);
    }
    private interface Task{void run()throws Throwable;}
    private static volatile int sink;
    private static void bench(String label,int loops,Task task)throws Throwable{long bytes0=ALLOC.getThreadAllocatedBytes(THREAD_ID),t0=System.nanoTime();task.run();long elapsed=System.nanoTime()-t0,bytes=ALLOC.getThreadAllocatedBytes(THREAD_ID)-bytes0;System.out.printf(java.util.Locale.ROOT,"%s loops=%d ns/op=%.1f alloc_B/op=%.1f total_ms=%.2f allocated_MB=%.2f%n",label,loops,(double)elapsed/loops,(double)bytes/loops,elapsed/1e6,bytes/1048576.0);}
    private static MethodHandle method(String name,MethodType type)throws Exception{return MethodHandles.privateLookupIn(WorldRenderer.class,MethodHandles.lookup()).findVirtual(WorldRenderer.class,name,type);}
    private static void reportCandidates(WorldRenderer r,float x,float eye,float z)throws Exception{
        List<?> boxes=(List<?>)get(r,"boxColliders"),meshes=(List<?>)get(r,"meshColliders");int boxCandidate=0,floorMeshes=0,floorTris=0,collisionMeshes=0,collisionTris=0,totalTris=0;
        float feet=eye-1.65f;for(Object b:boxes){Object q=get(b,"bounds");if(x+.28f>=(float)get(q,"minX")&&x-.28f<=(float)get(q,"maxX")&&z+.28f>=(float)get(q,"minZ")&&z-.28f<=(float)get(q,"maxZ"))boxCandidate++;}
        for(Object c:meshes){Object q=get(c,"bounds");float[] tri=(float[])get(c,"xyz");int n=tri.length/9;totalTris+=n;
            if(x>=((float)get(q,"minX"))-.05f&&x<=((float)get(q,"maxX"))+.05f&&z>=((float)get(q,"minZ"))-.05f&&z<=((float)get(q,"maxZ"))+.05f&&((float)get(q,"minY"))<=feet+.32f&&((float)get(q,"maxY"))>=feet-1.25f){floorMeshes++;floorTris+=n;}
            if(x+.28f>=(float)get(q,"minX")&&x-.28f<=(float)get(q,"maxX")&&z+.28f>=(float)get(q,"minZ")&&z-.28f<=(float)get(q,"maxZ")&&eye>=((float)get(q,"minY"))-.1f&&feet<=((float)get(q,"maxY"))+.1f){collisionMeshes++;collisionTris+=n;}
        }
        System.out.println("COLLISION_CANDIDATES boxes="+boxCandidate+" meshColliders="+meshes.size()+" meshTrianglesTotal="+totalTris+" floorY_meshes="+floorMeshes+" floorY_triangles_scanned="+floorTris+" collides_meshes="+collisionMeshes+" collides_triangles_scanned="+collisionTris);
        System.out.println("INTERACTION_TARGETS="+((List<?>)get(r,"interactions")).size()+" (ray query per target; allocation measured below)");
    }
    private static Object first(Object list)throws Exception{return ((List<?>)list).get(0);}
    private static Object get(Object o,String name)throws Exception{Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(o);}
    private static void set(Object o,String name,Object value)throws Exception{Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);f.set(o,value);}
    private static void call(Object o,String name,Class<?>[] types,Object...args)throws Exception{var m=WorldRenderer.class.getDeclaredMethod(name,types);m.setAccessible(true);m.invoke(o,args);}
}
