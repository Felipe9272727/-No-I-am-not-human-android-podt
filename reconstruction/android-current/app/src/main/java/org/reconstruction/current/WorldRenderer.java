package org.reconstruction.current;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.GL20;
import com.badlogic.gdx.graphics.Mesh;
import com.badlogic.gdx.graphics.PerspectiveCamera;
import com.badlogic.gdx.graphics.Texture;
import com.badlogic.gdx.graphics.VertexAttribute;
import com.badlogic.gdx.graphics.g3d.Environment;
import com.badlogic.gdx.graphics.g3d.Material;
import com.badlogic.gdx.graphics.g3d.ModelBatch;
import com.badlogic.gdx.graphics.g3d.Renderable;
import com.badlogic.gdx.graphics.g3d.RenderableProvider;
import com.badlogic.gdx.graphics.g3d.Shader;
import com.badlogic.gdx.graphics.g3d.attributes.BlendingAttribute;
import com.badlogic.gdx.graphics.g3d.attributes.ColorAttribute;
import com.badlogic.gdx.graphics.g3d.attributes.DepthTestAttribute;
import com.badlogic.gdx.graphics.g3d.attributes.FloatAttribute;
import com.badlogic.gdx.graphics.g3d.attributes.IntAttribute;
import com.badlogic.gdx.graphics.g3d.attributes.TextureAttribute;
import com.badlogic.gdx.graphics.g3d.environment.DirectionalLight;
import com.badlogic.gdx.graphics.g3d.environment.PointLight;
import com.badlogic.gdx.graphics.g3d.environment.SpotLight;
import com.badlogic.gdx.graphics.g3d.shaders.DefaultShader;
import com.badlogic.gdx.graphics.g3d.utils.DefaultShaderProvider;
import com.badlogic.gdx.math.Matrix4;
import com.badlogic.gdx.math.Vector3;
import com.badlogic.gdx.utils.Array;
import com.badlogic.gdx.utils.Disposable;
import com.badlogic.gdx.utils.GdxRuntimeException;
import com.badlogic.gdx.utils.Pool;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** LibGDX renderer for the statically recovered level-1 Unity scene. */
final class WorldRenderer implements Disposable {
    private static final float EYE_HEIGHT=1.65f, BODY_RADIUS=.28f, LOOK_DEG_PER_PIXEL=.12f, PITCH_LIMIT=80f;
    private static final float MAX_DRAW_DISTANCE=160f;
    private static final long TEXTURE_BUDGET=64L*1024L*1024L;
    private String manifestPath="", manifestDirectory="", appliedManifest="";
    private final List<RenderItem> renderItems=new ArrayList<>();
    private final List<Mesh> meshes=new ArrayList<>();
    private final List<BoxCollider> boxColliders=new ArrayList<>();
    private final Map<Integer,BoxCollider> boxById=new HashMap<>();
    private final List<TriangleCollider> meshColliders=new ArrayList<>();
    private final List<Interaction> interactions=new ArrayList<>();
    private final Map<Integer,Integer> roomByCollider=new HashMap<>();
    private final Map<Integer,String> texturesByIndex=new HashMap<>();
    private final Map<Integer,String> texturesByPathId=new HashMap<>();
    private final Map<String,Sampler> samplers=new HashMap<>();
    private final Map<Integer,MaterialInfo> materials=new HashMap<>();
    private final LinkedHashMap<String,TextureEntry> textureCache=new LinkedHashMap<>(16,.75f,true);
    private final Set<String> visibleTextures=new HashSet<>();
    private ModelBatch modelBatch;
    private Environment environment;
    private PerspectiveCamera camera;
    private final Vector3 player=new Vector3(); // Source Unity eye position, converted to GDX by negating Z.
    private volatile float yaw,pitch;
    private float moveX,moveForward,moveSpeed=2.5f;
    private boolean inputEnabled,worldEnabled=true,loaded,doorWaiting;
    private long poseRevision=Long.MIN_VALUE;
    private String appliedPoseKey="";
    private int frontRayColliderId=2432;
    private volatile String interactionJson="";
    private Interaction publishedInteraction;
    private long navigationRevision, publishedNavigationRevision=Long.MIN_VALUE, interactionSnapshots;
    private long textureBytes;
    private JSONObject latestState;
    private volatile String status = "loading: waiting for world manifest";
    private volatile String renderStage = "world renderer";
    private volatile String diagnostic = "";
    private volatile String glInfo = "GL information unavailable";
    private volatile String warningStatus;
    private boolean unlitFallback;
    private final List<RenderItem> depthWritingVisible=new ArrayList<>(), transparentVisible=new ArrayList<>();
    private long textureLoads, textureEvictions, profileStarted, profileNanos;
    private int profileFrames, visibleDraws, visibleTriangles;
    private volatile int frameRate;
    private volatile String performanceStatus="Measuring renderer…";
    private String doorManifestPath="";
    private DoorMotion doorMotion;
    private volatile int doorRoomMask;
    private volatile DoorRequest doorRequest;
    private volatile boolean resetDoorRequested,presentationPaused;
    private volatile long completedDoorToken;
    private long doorTokenCounter,activeDoorToken;

    void setDoorManifestPath(String path){
        String next=path==null?"":path;if(next.equals(doorManifestPath))return;
        doorManifestPath=next;
        if(loaded)try{loadDoorMotion(new JSONObject(appliedManifest));}catch(JSONException error){recordWarning("load door animation",error);}
    }
    synchronized long beginDoorOpen(int room){
        if(room<0||room>6||(doorRoomMask&(1<<room))==0)return 0;
        long token=++doorTokenCounter;doorRequest=new DoorRequest(room,token);return token;
    }
    boolean isDoorOpenComplete(long token){return token>0&&completedDoorToken>=token;}
    void cancelDoorMotion(){doorRequest=null;resetDoorRequested=true;}
    void setPresentationPaused(boolean paused){presentationPaused=paused;}

    private void loadDoorMotion(JSONObject world){
        doorMotion=null;doorRoomMask=0;
        for(RenderItem item:renderItems)item.door=null;
        if(doorManifestPath.isEmpty())return;
        try{
            JSONObject animation=new JSONObject(Gdx.files.internal(doorManifestPath).readString("UTF-8"));
            doorMotion=new DoorMotion(world,animation);doorRoomMask=doorMotion.roomMask();
            for(RenderItem item:renderItems)item.door=doorMotion.forRenderer(item.sourceRendererId);
        }catch(Exception error){recordWarning("load source door animation",error);}
    }
    private void updateDoorMotion(float delta){
        if(doorMotion==null)return;
        if(resetDoorRequested){resetDoorRequested=false;doorMotion.reset();activeDoorToken=0;}
        DoorRequest request=doorRequest;
        if(request!=null){
            doorRequest=null;activeDoorToken=request.token;
            if(!doorMotion.open(request.room)){completedDoorToken=request.token;activeDoorToken=0;}
        }
        if(!presentationPaused)doorMotion.advance(Math.min(.25f,Math.max(0,delta)));
        for(RenderItem item:renderItems){
            DoorMotion.Door door=item.door;if(door==null)continue;
            if(door.angle==0){item.renderable.worldTransform.set(item.matrix);item.bounds=item.baseBounds;}
            else{
                item.renderable.worldTransform.set(door.delta).mul(item.matrix);
                item.bounds=rotateBounds(door.delta.val,item.baseBounds);
            }
        }
        if(activeDoorToken>0&&!doorMotion.moving()){completedDoorToken=activeDoorToken;activeDoorToken=0;}
    }
    private static Bounds rotateBounds(float[] m,Bounds b){
        float ax=Float.MAX_VALUE,ay=ax,az=ax,bx=-ax,by=-ax,bz=-ax;
        for(int i=0;i<8;i++){
            float x=(i&1)==0?b.minX:b.maxX,y=(i&2)==0?b.minY:b.maxY,z=(i&4)==0?b.minZ:b.maxZ;
            float wx=m[0]*x+m[4]*y+m[8]*z+m[12],wy=m[1]*x+m[5]*y+m[9]*z+m[13],wz=m[2]*x+m[6]*y+m[10]*z+m[14];
            ax=Math.min(ax,wx);ay=Math.min(ay,wy);az=Math.min(az,wz);bx=Math.max(bx,wx);by=Math.max(by,wy);bz=Math.max(bz,wz);
        }
        return new Bounds(ax,ay,az,bx,by,bz);
    }

    WorldRenderer(String path){setManifestPath(path);}
    void setManifestPath(String path){String p=path==null?"":path;if(p.equals(manifestPath))return;manifestPath=p;int slash=p.lastIndexOf('/');manifestDirectory=slash<0?"":p.substring(0,slash+1);appliedManifest="";loadManifest();}
    void create(){captureGlInfo();renderStage="create ModelBatch";modelBatch=new ModelBatch(new SourceShaderProvider());renderStage="create world camera";camera=new PerspectiveCamera(60,Gdx.graphics.getWidth(),Gdx.graphics.getHeight());camera.near=.1f;camera.far=1000f;loadManifest();}
    int getFrameRate(){return frameRate;}
    String getPerformanceStatus(){return performanceStatus;}
    String getStatus(){return warningStatus==null?status:warningStatus;}
    String getDiagnostic(){String detail=diagnostic;if(detail==null||detail.isEmpty())detail=status;if(unlitFallback)detail="Unlit GLES fallback active after shader compile failure.\n"+detail;return detail+"\n\n"+glInfo+"\nWorld meshes="+meshes.size()+", render items="+renderItems.size()+", mesh colliders="+meshColliders.size()+", texture cache="+textureBytes+" bytes, visible textures="+visibleTextures.size()+"\n"+performanceStatus;}
    void failRender(RuntimeException error){status=errorStatus(renderStage,error);diagnostic=errorDiagnostic(renderStage,error);}
    private void captureGlInfo(){try{java.nio.IntBuffer values=ByteBuffer.allocateDirect(8).order(ByteOrder.nativeOrder()).asIntBuffer();Gdx.gl.glGetIntegerv(GL20.GL_MAX_TEXTURE_SIZE,values);Gdx.gl.glGetIntegerv(GL20.GL_DEPTH_BITS,values.position(1));glInfo="GL vendor="+Gdx.gl.glGetString(GL20.GL_VENDOR)+", renderer="+Gdx.gl.glGetString(GL20.GL_RENDERER)+", version="+Gdx.gl.glGetString(GL20.GL_VERSION)+", maxTextureSize="+values.get(0)+", depthBits="+values.get(1);}catch(RuntimeException error){glInfo="GL information unavailable: "+error.getClass().getSimpleName()+": "+String.valueOf(error.getMessage());}}
    void resize(int w,int h){if(camera==null||w<=0||h<=0)return;camera.viewportWidth=w;camera.viewportHeight=h;camera.update();}

    synchronized void setMoveVector(float x,float y){if(!inputEnabled)return;float n=(float)Math.sqrt(x*x+y*y);if(n>1){x/=n;y/=n;}moveX=finite(x);moveForward=finite(y);}
    synchronized void addLookDelta(float dx,float dy){if(!inputEnabled)return;yaw=wrap(yaw+finite(dx)*LOOK_DEG_PER_PIXEL);pitch=Math.max(-PITCH_LIMIT,Math.min(PITCH_LIMIT,pitch+finite(dy)*LOOK_DEG_PER_PIXEL));}
    synchronized void setInputEnabled(boolean v){inputEnabled=v;if(!v){moveX=0;moveForward=0;}}
    synchronized JSONObject getPose(){JSONObject o=new JSONObject();try{JSONArray p=new JSONArray();p.put(player.x);p.put(player.y);p.put(-player.z);o.put("position",p);o.put("yaw",yaw);o.put("pitch",pitch);}catch(JSONException ignored){}return o;}
    String getInteractionJson(){return interactionJson;}
    JSONObject getInteraction(){String snapshot=interactionJson;if(snapshot.isEmpty())return null;try{return new JSONObject(snapshot);}catch(JSONException invalid){return null;}}

    void applyState(JSONObject state){if(state==null)return;try{latestState=new JSONObject(state.toString());}catch(JSONException ignored){latestState=null;}
        boolean nextWorld="world".equals(state.optString("view_mode","world"));
        if(nextWorld&&!worldEnabled&&doorMotion!=null){doorMotion.close();activeDoorToken=0;}
        worldEnabled=nextWorld;
        if(!"playing".equals(state.optString("phase","")))cancelDoorMotion();
        updateNavigation(state.optJSONObject("world_navigation"));
        JSONObject p=state.optJSONObject("world_pose");if(p==null)return;long revision=p.optLong("revision",0);String key=revision+":"+p.optString("position","")+":"+p.optDouble("yaw",0)+":"+p.optDouble("pitch",0);
        synchronized(this){if(key.equals(appliedPoseKey)||(poseRevision!=Long.MIN_VALUE&&revision==poseRevision))return;JSONArray a=p.optJSONArray("position");if(a!=null&&a.length()>=3)player.set((float)a.optDouble(0,0),(float)a.optDouble(1,0),(float)-a.optDouble(2,0));yaw=finite((float)p.optDouble("yaw",yaw));pitch=Math.max(-PITCH_LIMIT,Math.min(PITCH_LIMIT,finite((float)p.optDouble("pitch",pitch))));poseRevision=revision;appliedPoseKey=key;}}

    private void updateNavigation(JSONObject nav){navigationRevision++;if(nav==null)return;JSONArray doors=nav.optJSONArray("room_doors");if(doors!=null)for(int i=0;i<doors.length();i++){JSONObject d=doors.optJSONObject(i);if(d!=null)roomByCollider.put(d.optInt("collider_path_id",-1),d.optInt("room",-1));}
        JSONObject entrance=nav.optJSONObject("entrance_interaction");if(entrance!=null){frontRayColliderId=entrance.optInt("source_collider_path_id",entrance.optInt("raycast_target_collider_path_id",entrance.optInt("collider_path_id",2432)));if(frontRayColliderId==2412)frontRayColliderId=2432;JSONObject c=latestState==null?null:latestState.optJSONObject("campaign");doorWaiting=c!=null&&c.optBoolean("door_waiting",false);ensureFrontDoor(entrance);}
        for(Interaction t:interactions){Integer room=roomByCollider.get(t.colliderId);try{if(room!=null){t.descriptor.put("action","enter_room");t.descriptor.put("room",room);}else if(t.colliderId==frontRayColliderId){t.descriptor.put("action",doorWaiting?"open_door":"enter_room");t.descriptor.put("room",5);}}catch(JSONException ignored){}}
    }

    void render(float delta) {
        if(!loaded||!worldEnabled||camera==null)return;
        long frameStart=System.nanoTime();
        renderStage="prepare visible meshes";
        updateDoorMotion(delta);
        float x,f;boolean enabled;
        synchronized(this){enabled=inputEnabled&&(doorMotion==null||!doorMotion.moving());x=enabled?moveX:0;f=enabled?moveForward:0;}
        if(enabled)movePlayer(x,f,Math.min(.05f,Math.max(0,delta)));
        updateCamera();camera.update();
        depthWritingVisible.clear();transparentVisible.clear();visibleTextures.clear();
        visibleDraws=visibleTriangles=0;
        for(RenderItem item:renderItems) {
            if(!visible(item.bounds)||!contributes(item.material))continue;
            MaterialInfo info=item.material;
            if(info!=null&&!info.texture.isEmpty()) {
                Texture texture=texture(info.texture);
                if(texture!=null) {
                    if(texture!=item.boundTexture) {
                        TextureAttribute attribute=(TextureAttribute)item.renderable.material.get(TextureAttribute.Diffuse);
                        if(attribute==null){attribute=TextureAttribute.createDiffuse(texture);item.renderable.material.set(attribute);}
                        else attribute.textureDescription.set(texture,texture.getMinFilter(),texture.getMagFilter(),texture.getUWrap(),texture.getVWrap());
                        attribute.scaleU=info.su;attribute.scaleV=info.sv;attribute.offsetU=info.ou;attribute.offsetV=info.ov;
                        item.boundTexture=texture;
                    }
                    visibleTextures.add(info.texture);
                }
            }
            (info==null||info.zWrite?depthWritingVisible:transparentVisible).add(item);
            visibleDraws++;visibleTriangles+=item.count/3;
        }
        renderStage="compile/draw GLES world scene";
        try {drawRenderables(depthWritingVisible);drawRenderables(transparentVisible);}
        catch(RuntimeException error){if(!activateShaderFallback(error))throw error;return;}
        Gdx.gl.glDepthMask(true);Gdx.gl.glDisable(GL20.GL_DEPTH_TEST);
        trimTextures();updateInteraction();
        status=unlitFallback?"warning: using unlit GLES fallback after shader compile failure":warningStatus==null?"ready":warningStatus;
        profileNanos+=System.nanoTime()-frameStart;profileFrames++;
        long now=System.nanoTime();
        if(profileStarted==0)profileStarted=now;
        if(now-profileStarted>=500000000L) {
            frameRate=Gdx.graphics.getFramesPerSecond();
            performanceStatus=String.format(java.util.Locale.ROOT,"FPS=%d render-submit=%.2f ms, surface=%dx%d, draws=%d triangles=%d, texture loads=%d evictions=%d, cached materials=%d interaction snapshots=%d",frameRate,profileNanos/1e6/Math.max(1,profileFrames),Gdx.graphics.getWidth(),Gdx.graphics.getHeight(),visibleDraws,visibleTriangles,textureLoads,textureEvictions,renderItems.size(),interactionSnapshots);
            profileNanos=0;profileFrames=0;profileStarted=now;
        }
    }
    private void drawRenderables(List<RenderItem> items) {
        if(items.isEmpty())return;
        modelBatch.begin(camera);
        for(RenderItem item:items)modelBatch.render(item,unlitFallback?null:environment);
        modelBatch.end();
    }
    static boolean contributes(MaterialInfo info) {
        return info==null||!(info.transparent&&!info.zWrite&&info.color.a<=0f&&info.blendSrc==GL20.GL_SRC_ALPHA&&info.blendDst==GL20.GL_ONE_MINUS_SRC_ALPHA);
    }
    private static Material makeMaterial(MaterialInfo info,Matrix4 matrix) {
        Material material=new Material(ColorAttribute.createDiffuse(info==null?Color.WHITE:info.color));
        if(info!=null) {
            material.set(IntAttribute.createCullFace(cullFaceForTransform(info.cull,determinant3x3(matrix.val))));
            material.set(new DepthTestAttribute(GL20.GL_LEQUAL,0f,1f,info.zWrite));
            if(info.transparent)material.set(new BlendingAttribute(info.blendSrc,info.blendDst,1f));
            if(info.alphaClip)material.set(FloatAttribute.createAlphaTest(info.cutoff));
        }
        return material;
    }
    private boolean activateShaderFallback(RuntimeException error){if(unlitFallback||!(error instanceof GdxRuntimeException))return false;String message=String.valueOf(error.getMessage()).toLowerCase(java.util.Locale.ROOT);if(!message.contains("shader")||!(message.contains("compil")||message.contains("link")))return false;diagnostic=errorDiagnostic("compile/draw GLES world scene; switching to unlit fallback",error);try{if(modelBatch!=null)modelBatch.dispose();}catch(RuntimeException ignored){}modelBatch=new ModelBatch();unlitFallback=true;status="warning: using unlit GLES fallback after shader compile failure";return true;}
    private void updateCamera(){float yr=(float)Math.toRadians(yaw),pr=(float)Math.toRadians(pitch),h=(float)Math.cos(pr);camera.position.set(player);camera.direction.set((float)Math.sin(yr)*h,-(float)Math.sin(pr),-(float)Math.cos(yr)*h).nor();camera.up.set(Vector3.Y);}
    private boolean visible(Bounds b){if(b==null)return true;float dx=b.cx-camera.position.x,dy=b.cy-camera.position.y,dz=b.cz-camera.position.z,reach=MAX_DRAW_DISTANCE+b.radius;if(dx*dx+dy*dy+dz*dz>reach*reach)return false;return camera.frustum.boundsInFrustum(b.cx,b.cy,b.cz,b.hx,b.hy,b.hz);}

    private void movePlayer(float x,float f,float dt){if(dt<=0||(x==0&&f==0))return;float r=(float)Math.toRadians(yaw);float dx=((float)Math.cos(r)*x+(float)Math.sin(r)*f)*moveSpeed*dt;float dz=((float)Math.sin(r)*x-(float)Math.cos(r)*f)*moveSpeed*dt;tryMove(dx,0);tryMove(0,dz);}
    private void tryMove(float dx,float dz){float nx=player.x+dx,nz=player.z+dz;if(dx==0&&dz==0)return;float ground=floorY(nx,nz,player.y-EYE_HEIGHT);float ny=Float.isNaN(ground)?player.y:ground+EYE_HEIGHT;if(collides(nx,ny,nz))return;synchronized(this){player.x=nx;player.y=ny;player.z=nz;}}
    private boolean collides(float x,float eye,float z){float feet=eye-EYE_HEIGHT;float[] cy={feet+BODY_RADIUS,feet+EYE_HEIGHT*.5f,eye-BODY_RADIUS};for(BoxCollider b:boxColliders){if(x+BODY_RADIUS<b.bounds.minX||x-BODY_RADIUS>b.bounds.maxX||z+BODY_RADIUS<b.bounds.minZ||z-BODY_RADIUS>b.bounds.maxZ)continue;for(float y:cy){Vector3 q=new Vector3(x,y,z).mul(b.inverse);float r=BODY_RADIUS*b.inverseScale;if(Math.abs(q.x-b.cx)<b.hx+r&&Math.abs(q.y-b.cy)<b.hy+r&&Math.abs(q.z-b.cz)<b.hz+r)return true;}}
        for(TriangleCollider c:meshColliders){Bounds b=c.bounds;if(x+BODY_RADIUS<b.minX||x-BODY_RADIUS>b.maxX||z+BODY_RADIUS<b.minZ||z-BODY_RADIUS>b.maxZ||eye<b.minY-.1f||feet>b.maxY+.1f)continue;for(int i=0;i<c.xyz.length;i+=9){float minX=Math.min(c.xyz[i],Math.min(c.xyz[i+3],c.xyz[i+6]))-BODY_RADIUS,maxX=Math.max(c.xyz[i],Math.max(c.xyz[i+3],c.xyz[i+6]))+BODY_RADIUS,minY=Math.min(c.xyz[i+1],Math.min(c.xyz[i+4],c.xyz[i+7]))-BODY_RADIUS,maxY=Math.max(c.xyz[i+1],Math.max(c.xyz[i+4],c.xyz[i+7]))+BODY_RADIUS,minZ=Math.min(c.xyz[i+2],Math.min(c.xyz[i+5],c.xyz[i+8]))-BODY_RADIUS,maxZ=Math.max(c.xyz[i+2],Math.max(c.xyz[i+5],c.xyz[i+8]))+BODY_RADIUS;if(x<minX||x>maxX||z<minZ||z>maxZ||cy[0]>maxY||cy[2]<minY)continue;for(float y:cy)if(pointTriangle(x,y,z,c.xyz,i)<(BODY_RADIUS-.025f)*(BODY_RADIUS-.025f))return true;}}
        return false;}
    private float floorY(float x,float z,float foot){float best=Float.NEGATIVE_INFINITY;for(TriangleCollider c:meshColliders){Bounds b=c.bounds;if(x<b.minX-.05f||x>b.maxX+.05f||z<b.minZ-.05f||z>b.maxZ+.05f||b.minY>foot+.32f||b.maxY<foot-1.25f)continue;float[] t=c.xyz;for(int i=0;i<t.length;i+=9){float ax=t[i],az=t[i+2],bx=t[i+3],bz=t[i+5],cx=t[i+6],cz=t[i+8],area=(bz-cz)*(ax-cx)+(cx-bx)*(az-cz);if(Math.abs(area)<1e-7f)continue;float wa=((bz-cz)*(x-cx)+(cx-bx)*(z-cz))/area,wb=((cz-az)*(x-cx)+(ax-cx)*(z-cz))/area,wc=1-wa-wb;if(wa<-.001f||wb<-.001f||wc<-.001f)continue;float ay=t[i+1],by=t[i+4],cy=t[i+7],ny=(bz-az)*(cx-ax)-(bx-ax)*(cz-az),len=(float)Math.sqrt(ny*ny);if(len<1e-6f)continue;float y=wa*ay+wb*by+wc*cy;if(Math.abs(ny/len)>.55f&&y<=foot+.32f&&y>=foot-1.25f&&y>best)best=y;}}return best==Float.NEGATIVE_INFINITY?Float.NaN:best;}
    private void updateInteraction() {
        Interaction best=null;float nearest=Float.MAX_VALUE;
        for(Interaction target:interactions){float distance=rayBox(target.box,camera.position,camera.direction,1f);if(distance>=0&&distance<nearest){nearest=distance;best=target;}}
        if(best==publishedInteraction&&navigationRevision==publishedNavigationRevision)return;
        publishedInteraction=best;publishedNavigationRevision=navigationRevision;
        interactionJson=best==null?"":best.descriptor.toString();interactionSnapshots++;
    }
    private float rayBox(BoxCollider box,Vector3 origin,Vector3 direction,float max) {
        float[] m=box.inverse.val;
        float ox=m[0]*origin.x+m[4]*origin.y+m[8]*origin.z+m[12]-box.cx;
        float oy=m[1]*origin.x+m[5]*origin.y+m[9]*origin.z+m[13]-box.cy;
        float oz=m[2]*origin.x+m[6]*origin.y+m[10]*origin.z+m[14]-box.cz;
        float dx=m[0]*direction.x+m[4]*direction.y+m[8]*direction.z;
        float dy=m[1]*direction.x+m[5]*direction.y+m[9]*direction.z;
        float dz=m[2]*direction.x+m[6]*direction.y+m[10]*direction.z;
        float lo=0,hi=max,q,r;
        if(Math.abs(dx)<1e-6f){if(ox < -box.hx||ox>box.hx)return -1;}
        else{q=(-box.hx-ox)/dx;r=(box.hx-ox)/dx;if(q>r){float t=q;q=r;r=t;}lo=Math.max(lo,q);hi=Math.min(hi,r);if(lo>hi)return -1;}
        if(Math.abs(dy)<1e-6f){if(oy < -box.hy||oy>box.hy)return -1;}
        else{q=(-box.hy-oy)/dy;r=(box.hy-oy)/dy;if(q>r){float t=q;q=r;r=t;}lo=Math.max(lo,q);hi=Math.min(hi,r);if(lo>hi)return -1;}
        if(Math.abs(dz)<1e-6f){if(oz < -box.hz||oz>box.hz)return -1;}
        else{q=(-box.hz-oz)/dz;r=(box.hz-oz)/dz;if(q>r){float t=q;q=r;r=t;}lo=Math.max(lo,q);hi=Math.min(hi,r);if(lo>hi)return -1;}
        return lo<=max?lo:-1;
    }

    private void loadManifest(){if(manifestPath.isEmpty()||Gdx.files==null)return;String json;status="loading: read world manifest";renderStage=status;try{json=Gdx.files.internal(manifestPath).readString("UTF-8");}catch(Exception e){status=errorStatus("read world manifest",e);diagnostic=errorDiagnostic("read world manifest",e);return;}if(json.equals(appliedManifest)){if(camera!=null)try{applyCameraClip(findCamera(new JSONObject(json).optJSONArray("cameras")));}catch(JSONException ignored){}return;}appliedManifest=json;clearScene();warningStatus=null;diagnostic="";try{status="loading: parse world scene";renderStage=status;JSONObject root=new JSONObject(json);parseTextures(root.optJSONArray("textures"));parseMaterials(root.optJSONArray("materials"));parseLighting(root.optJSONArray("lights"),root.optJSONArray("render_settings"));JSONArray meshArray=root.optJSONArray("meshes");status="loading: allocate source meshes";renderStage=status;parseRenderers(root.optJSONArray("renderers"),meshArray);status="loading: build collision geometry";renderStage=status;parseColliders(root.optJSONArray("colliders"),meshArray);parseTargets(root.optJSONArray("interaction_targets"),root.optJSONArray("named_door_targets"));JSONObject cam=findCamera(root.optJSONArray("cameras"));applyCameraClip(cam);if(poseRevision==Long.MIN_VALUE&&cam!=null)setCameraPose(cam);moveSpeed=(float)root.optDouble("player_movement_speed_mps",2.5);if(latestState!=null)updateNavigation(latestState.optJSONObject("world_navigation"));loaded=true;loadDoorMotion(root);status=warningStatus==null?"ready":warningStatus;}catch(Exception e){clearScene();loaded=false;status=errorStatus("load world manifest",e);diagnostic=errorDiagnostic("load world manifest",e);}}
    private void applyCameraClip(JSONObject source){if(camera==null||source==null)return;camera.near=(float)source.optDouble("near_clip",.1);camera.far=(float)source.optDouble("far_clip",1000);if(camera.near<=0||camera.far<=camera.near){camera.near=.1f;camera.far=1000f;}}
    private void parseTextures(JSONArray a){if(a==null)return;for(int i=0;i<a.length();i++){JSONObject t=a.optJSONObject(i),ref=t==null?null:t.optJSONObject("source_ref");if(ref==null)continue;String path=resolve(t.optString("android_asset",t.optString("asset","")));texturesByIndex.put(i,path);texturesByPathId.put(ref.optInt("path_id",-1),path);JSONObject s=t.optJSONObject("sampler");if(s!=null)samplers.put(path,new Sampler(s.optInt("filter_mode",1),s.optInt("wrap_u",0),s.optInt("wrap_v",0),s.optInt("aniso",1)));}}
    private void parseMaterials(JSONArray a){if(a==null)return;for(int i=0;i<a.length();i++){JSONObject m=a.optJSONObject(i);if(m==null)continue;JSONArray c=m.optJSONArray("color");Color color=new Color((float)(c==null?1:c.optDouble(0,1)),(float)(c==null?1:c.optDouble(1,1)),(float)(c==null?1:c.optDouble(2,1)),(float)(c==null?1:c.optDouble(3,1)));JSONObject fp=m.optJSONObject("float_properties");int cull=fp==null?2:fp.optInt("_Cull",2);boolean trans=(fp!=null&&fp.optDouble("_Surface",0)>.5)||(fp!=null&&((int)fp.optDouble("_SrcBlend",1)!=1||(int)fp.optDouble("_DstBlend",0)!=0))||color.a<.999f;int src=blendFactor(fp==null?(trans?5:1):fp.optInt("_SrcBlend",trans?5:1)),dst=blendFactor(fp==null?(trans?10:0):fp.optInt("_DstBlend",trans?10:0));if(src==GL20.GL_ONE&&dst==GL20.GL_ONE_MINUS_SRC_ALPHA)src=GL20.GL_SRC_ALPHA;String path="";float[] uv=unityUvTransform(1,1,0,0);JSONObject chosen=preferredDiffuseTexture(m.optJSONArray("texture_refs"));if(chosen!=null){path=texturesByIndex.getOrDefault(chosen.optInt("texture_index",-1),"");if(path.isEmpty()){JSONObject ref=chosen.optJSONObject("ref");if(ref!=null)path=texturesByPathId.getOrDefault(ref.optInt("path_id",-1),"");}float[] s=vec2(chosen.optJSONArray("scale"),1,1),o=vec2(chosen.optJSONArray("offset"),0,0);uv=unityUvTransform(s[0],s[1],o[0],o[1]);}boolean zWrite=fp==null?!trans:fp.optDouble("_ZWrite",!trans?1:0)>.5;boolean alphaClip=fp!=null&&fp.optDouble("_AlphaClip",0)>.5;float cutoff=fp==null?.5f:(float)fp.optDouble("_Cutoff",.5);materials.put(i,new MaterialInfo(color,path,uv,cull,trans,src,dst,zWrite,alphaClip,cutoff));}}
    private static JSONObject preferredDiffuseTexture(JSONArray refs){if(refs==null||refs.length()==0)return null;JSONObject fallback=null;for(int i=0;i<refs.length();i++){JSONObject r=refs.optJSONObject(i);if(r==null)continue;String p=r.optString("property","").toLowerCase(java.util.Locale.ROOT);if(p.equals("_basemap")||p.equals("_maintex")||p.contains("albedo")||p.contains("basecolor"))return r;if(p.contains("normal")||p.contains("bump")||p.contains("refraction")||p.contains("height")||p.contains("parallax"))continue;if(fallback==null)fallback=r;}return fallback;}
    private static int blendFactor(int unity){switch(unity){case 0:return GL20.GL_ZERO;case 1:return GL20.GL_ONE;case 2:return GL20.GL_DST_COLOR;case 3:return GL20.GL_SRC_COLOR;case 4:return GL20.GL_ONE_MINUS_DST_COLOR;case 5:return GL20.GL_SRC_ALPHA;case 6:return GL20.GL_ONE_MINUS_SRC_COLOR;case 7:return GL20.GL_DST_ALPHA;case 8:return GL20.GL_ONE_MINUS_DST_ALPHA;case 9:return GL20.GL_SRC_ALPHA_SATURATE;case 10:return GL20.GL_ONE_MINUS_SRC_ALPHA;default:return GL20.GL_ONE;}}
    static float determinant3x3(float[] m){return m[0]*(m[5]*m[10]-m[9]*m[6])-m[4]*(m[1]*m[10]-m[9]*m[2])+m[8]*(m[1]*m[6]-m[5]*m[2]);}
    /** Unity material Cull is 0=off, 1=front, 2=back; GL uses different constants. */
    static int cullFaceForTransform(int unityCull,float determinant){int cull=unityCull==0?GL20.GL_NONE:unityCull==1?GL20.GL_FRONT:GL20.GL_BACK;if(cull==GL20.GL_NONE||determinant>=0)return cull;return cull==GL20.GL_FRONT?GL20.GL_BACK:GL20.GL_FRONT;}
    private void parseLighting(JSONArray lights,JSONArray settings){environment=new Environment();JSONObject s=settings==null?null:settings.optJSONObject(0);JSONArray ambient=s==null?null:s.optJSONArray("ambient_equator_color");environment.set(ColorAttribute.createAmbientLight((float)(ambient==null?.13:ambient.optDouble(0,.13)),(float)(ambient==null?.14:ambient.optDouble(1,.14)),(float)(ambient==null?.15:ambient.optDouble(2,.15)),1));if(lights==null)return;for(int i=0;i<lights.length();i++){JSONObject l=lights.optJSONObject(i);if(l==null||!l.optBoolean("active_in_hierarchy",false)||!l.optBoolean("enabled",false))continue;JSONArray color=l.optJSONArray("color"),m=l.optJSONArray("world_matrix_row_major");if(color==null||m==null)continue;float r=(float)color.optDouble(0,1),g=(float)color.optDouble(1,1),b=(float)color.optDouble(2,1),intensity=(float)l.optDouble("intensity",1),range=Math.max(.01f,(float)l.optDouble("range",10));float x=(float)m.optJSONArray(0).optDouble(3,0),y=(float)m.optJSONArray(1).optDouble(3,0),z=(float)-m.optJSONArray(2).optDouble(3,0);Vector3 pos=new Vector3(x,y,z),dir=new Vector3(-(float)m.optJSONArray(0).optDouble(2,0),-(float)m.optJSONArray(1).optDouble(2,0),(float)m.optJSONArray(2).optDouble(2,0)).nor();int type=l.optInt("type",2);if(type==1)environment.add(new DirectionalLight().set(r*intensity,g*intensity,b*intensity,dir));else if(type==0){float angle=(float)l.optDouble("spot_angle",45);if(angle>=170)environment.add(new RangedPointLight().set(new Color(r,g,b,1),pos,intensity,range));else{float inner=(float)l.optDouble("inner_spot_angle",angle*.5f),cutoff=Math.max(1,Math.min(90,angle*.5f));environment.add(new RangedSpotLight().set(new Color(r,g,b,1),pos,dir,intensity,cutoff,1,range,inner*.5f));}}else environment.add(new RangedPointLight().set(new Color(r,g,b,1),pos,intensity,range));}}

    private void parseRenderers(JSONArray renderers,JSONArray meshArray){if(renderers==null||meshArray==null)return;Map<Integer,MeshData> cache=new HashMap<>();for(int i=0;i<renderers.length();i++){JSONObject r=renderers.optJSONObject(i);if(r==null||!r.optBoolean("active_in_hierarchy",false)||!r.optBoolean("enabled",true))continue;int mi=r.optInt("mesh_index",-1);JSONObject info=meshArray.optJSONObject(mi);if(info==null)continue;MeshData data=cache.get(mi);if(data==null){data=loadMesh(info);if(data==null)continue;cache.put(mi,data);}float[] mat=matrix(r.optJSONArray("world_matrix_row_major"));Matrix4 transform=new Matrix4(mat);Bounds bounds=transformBounds(mat,data.bounds);JSONArray subs=info.optJSONArray("submeshes"),mats=r.optJSONArray("material_indices");int subCount=subs==null?1:subs.length();for(int si=0;si<subCount;si++){JSONObject sub=subs==null?null:subs.optJSONObject(si);int start=sub==null?0:sub.optInt("index_start",0),count=sub==null?info.optInt("index_count",0):sub.optInt("index_count",0),mi2=mats==null||mats.length()==0?-1:mats.optInt(Math.min(si,mats.length()-1),-1);MaterialInfo material=materials.get(mi2);int cursor=0;for(Mesh mesh:data.chunks){int n=mesh.getNumIndices(),lo=Math.max(start,cursor),hi=Math.min(start+count,cursor+n);if(hi>lo)renderItems.add(new RenderItem("world-"+i+"-"+si,r.optInt("renderer_path_id",-1),mesh,lo-cursor,hi-lo,transform,material,bounds));cursor+=n;}}}}
    private MeshData loadMesh(JSONObject info){try{String path=resolve(info.optString("android_asset",info.optString("mesh_asset","")));int vc=info.optInt("android_vertex_count",info.optInt("vertex_count",0)),ic=info.optInt("android_index_count",info.optInt("index_count",0));if(path.isEmpty()||vc<=0||vc>1000000||ic<3||ic>3000000||ic%3!=0)return null;byte[] bytes=Gdx.files.internal(path).readBytes();if(bytes.length!=vc*32+ic*4)return null;ByteBuffer b=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);float[] v=new float[vc*8];float ax=Float.MAX_VALUE,ay=ax,az=ax,bx=-ax,by=-ax,bz=-ax;for(int i=0;i<vc;i++){int j=i*8;float x=b.getFloat(),y=b.getFloat(),z=b.getFloat(),nx=b.getFloat(),ny=b.getFloat(),nz=b.getFloat(),u=b.getFloat(),w=b.getFloat();v[j]=x;v[j+1]=y;v[j+2]=-z;v[j+3]=nx;v[j+4]=ny;v[j+5]=-nz;v[j+6]=u;v[j+7]=w;ax=Math.min(ax,x);ay=Math.min(ay,y);az=Math.min(az,z);bx=Math.max(bx,x);by=Math.max(by,y);bz=Math.max(bz,z);}b.position(vc*32);int[] idx=new int[ic];for(int i=0;i<ic;i++){idx[i]=b.getInt();if(idx[i]<0||idx[i]>=vc)return null;}List<Mesh> chunks=new ArrayList<>();
        // Retain shared indices from the lossless C++ optimizer. Re-expanding
        // every triangle here would discard vertex-cache reuse on the GPU.
        if(vc<=65535){short[] shared=new short[ic];for(int i=0;i<ic;i+=3){shared[i]=(short)idx[i];shared[i+1]=(short)idx[i+2];shared[i+2]=(short)idx[i+1];}Mesh mesh=new Mesh(true,vc,ic,VertexAttribute.Position(),VertexAttribute.Normal(),VertexAttribute.TexCoords(0));mesh.setVertices(v);mesh.setIndices(shared);chunks.add(mesh);meshes.add(mesh);}
        else for(int first=0;first<ic;){int n=Math.min(65532,ic-first);n-=n%3;float[] cv=new float[n*8];short[] ci=new short[n];for(int i=0;i<n;i++){int k=i%3==1?i+1:i%3==2?i-1:i;System.arraycopy(v,idx[first+k]*8,cv,i*8,8);ci[i]=(short)i;}Mesh m=new Mesh(true,n,n,VertexAttribute.Position(),VertexAttribute.Normal(),VertexAttribute.TexCoords(0));m.setVertices(cv);m.setIndices(ci);chunks.add(m);meshes.add(m);first+=n;}return new MeshData(chunks,new float[]{(ax+bx)*.5f,(ay+by)*.5f,(az+bz)*.5f,(bx-ax)*.5f,(by-ay)*.5f,(bz-az)*.5f});}catch(Exception error){recordWarning("load render mesh "+info.optString("name","?"),error);return null;}}

    private void parseColliders(JSONArray source,JSONArray meshArray){if(source==null)return;for(int i=0;i<source.length();i++){JSONObject c=source.optJSONObject(i);if(c==null||!c.optBoolean("active_in_hierarchy",false)||!c.optBoolean("enabled",false))continue;String type=c.optString("type","");if("BoxCollider".equals(type)){JSONArray s=c.optJSONArray("size"),v=c.optJSONArray("center");if(s==null)continue;float[] m=matrix(c.optJSONArray("world_matrix_row_major"));float cx=(float)(v==null?0:v.optDouble(0,0)),cy=(float)(v==null?0:v.optDouble(1,0)),cz=(float)(v==null?0:v.optDouble(2,0)),hx=(float)s.optDouble(0,0)*.5f,hy=(float)s.optDouble(1,0)*.5f,hz=(float)s.optDouble(2,0)*.5f;BoxCollider box=makeBox(m,cx,cy,cz,hx,hy,hz);int id=c.optInt("path_id",-1);boxById.put(id,box);if(!c.optBoolean("is_trigger",false))boxColliders.add(box);}else if("MeshCollider".equals(type)&&!c.optBoolean("is_trigger",false)){int ix=c.optInt("mesh_asset_index",-1);JSONObject info=ix>=0&&meshArray!=null&&ix<meshArray.length()?meshArray.optJSONObject(ix):null;if(info==null){JSONObject ref=c.optJSONObject("mesh_ref");if(ref!=null&&meshArray!=null)for(int j=0;j<meshArray.length();j++){JSONObject q=meshArray.optJSONObject(j),r=q==null?null:q.optJSONObject("source_ref");if(r!=null&&r.optInt("path_id",-1)==ref.optInt("path_id",-2)&&r.optInt("file_id",-1)==ref.optInt("file_id",-2)){info=q;break;}}}if(info!=null){TriangleCollider t=loadColliderMesh(info,matrix(c.optJSONArray("world_matrix_row_major")));if(t!=null)meshColliders.add(t);}}}}
    private BoxCollider makeBox(float[] m,float cx,float cy,float cz,float hx,float hy,float hz){Bounds bounds=transformBounds(m,new float[]{cx,cy,cz,hx,hy,hz});Matrix4 inverse=new Matrix4(m).inv();float sx=(float)Math.sqrt(inverse.val[0]*inverse.val[0]+inverse.val[1]*inverse.val[1]+inverse.val[2]*inverse.val[2]),sy=(float)Math.sqrt(inverse.val[4]*inverse.val[4]+inverse.val[5]*inverse.val[5]+inverse.val[6]*inverse.val[6]),sz=(float)Math.sqrt(inverse.val[8]*inverse.val[8]+inverse.val[9]*inverse.val[9]+inverse.val[10]*inverse.val[10]);return new BoxCollider(inverse,cx,cy,-cz,hx,hy,hz,Math.max(sx,Math.max(sy,sz)),bounds);}
    private TriangleCollider loadColliderMesh(JSONObject info,float[] mat){try{String path=resolve(info.optString("android_asset",info.optString("mesh_asset","")));int vc=info.optInt("android_vertex_count",info.optInt("vertex_count",0)),ic=info.optInt("android_index_count",info.optInt("index_count",0));if(path.isEmpty()||vc<=0||ic<3||ic>3000000)return null;byte[] bytes=Gdx.files.internal(path).readBytes();if(bytes.length!=vc*32+ic*4)return null;ByteBuffer b=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);float[] v=new float[vc*3];for(int i=0;i<vc;i++){float x=b.getFloat(),y=b.getFloat(),z=-b.getFloat();v[i*3]=x;v[i*3+1]=y;v[i*3+2]=z;b.position(b.position()+20);}b.position(vc*32);float[] tri=new float[ic*3];float ax=Float.MAX_VALUE,ay=ax,az=ax,bx=-ax,by=-ax,bz=-ax;for(int i=0;i<ic;i++){int ix=b.getInt();if(ix<0||ix>=vc)return null;float x=v[ix*3],y=v[ix*3+1],z=v[ix*3+2],wx=mat[0]*x+mat[4]*y+mat[8]*z+mat[12],wy=mat[1]*x+mat[5]*y+mat[9]*z+mat[13],wz=mat[2]*x+mat[6]*y+mat[10]*z+mat[14];tri[i*3]=wx;tri[i*3+1]=wy;tri[i*3+2]=wz;ax=Math.min(ax,wx);ay=Math.min(ay,wy);az=Math.min(az,wz);bx=Math.max(bx,wx);by=Math.max(by,wy);bz=Math.max(bz,wz);}return new TriangleCollider(tri,new Bounds(ax,ay,az,bx,by,bz));}catch(Exception error){recordWarning("load collision mesh "+info.optString("name","?"),error);return null;}}

    private void parseTargets(JSONArray source,JSONArray named){if(source==null)return;for(int i=0;i<source.length();i++){JSONObject target=source.optJSONObject(i);if(target==null)continue;BoxCollider box=null;int collider=-1;if(named!=null)for(int j=0;j<named.length();j++){JSONObject door=named.optJSONObject(j);if(door==null||!target.optString("label","").equals(door.optString("name","")))continue;JSONArray cs=door.optJSONArray("colliders");if(cs!=null)for(int k=0;k<cs.length();k++){JSONObject c=cs.optJSONObject(k);if(c!=null&&"RaycastTarget".equals(c.optString("name"))){collider=c.optInt("path_id",-1);box=boxById.get(collider);break;}}break;}if(box==null){JSONArray ids=target.optJSONArray("collider_path_ids");if(ids!=null)for(int j=0;j<ids.length();j++){collider=ids.optInt(j,-1);box=boxById.get(collider);if(box!=null)break;}}if(box==null||(!"door".equals(target.optString("kind"))&&collider!=2432))continue;JSONObject d=new JSONObject();try{d.put("kind",target.optString("kind","door"));d.put("id",target.optInt("id",-1));d.put("collider_id",collider);d.put("label",target.optString("label",""));}catch(JSONException ignored){}interactions.add(new Interaction(collider,box,d));}}
    private void ensureFrontDoor(JSONObject entrance){BoxCollider b=boxById.get(frontRayColliderId);if(b==null)return;for(Interaction i:interactions)if(i.colliderId==frontRayColliderId)return;JSONObject d=new JSONObject();try{d.put("kind","door");d.put("id",frontRayColliderId);d.put("collider_id",frontRayColliderId);d.put("label",entrance==null?"Peephole":entrance.optString("name","Peephole"));d.put("room",5);d.put("action",doorWaiting?"open_door":"enter_room");}catch(JSONException ignored){}interactions.add(new Interaction(frontRayColliderId,b,d));}
    private JSONObject findCamera(JSONArray a){if(a==null)return null;for(int i=0;i<a.length();i++){JSONObject c=a.optJSONObject(i);if(c!=null&&c.optBoolean("active_in_hierarchy",false)&&c.optBoolean("enabled",false)&&"Main Camera".equals(c.optString("name")))return c;}return null;}
    private void setCameraPose(JSONObject c){JSONArray m=c.optJSONArray("world_matrix_row_major");if(m==null)return;synchronized(this){player.set((float)m.optJSONArray(0).optDouble(3,0),(float)m.optJSONArray(1).optDouble(3,0),(float)-m.optJSONArray(2).optDouble(3,0));yaw=0;pitch=0;}}
    private Texture texture(String path){TextureEntry e=textureCache.get(path);if(e!=null)return e.texture;try{FileHandle f=Gdx.files.internal(path);byte[] head=new byte[24];int read=0;try(java.io.InputStream input=f.read()){while(read<24){int n=input.read(head,read,24-read);if(n<0)break;read+=n;}}if(read<24||head[0]!=(byte)137||head[1]!='P'||head[2]!='N'||head[3]!='G')return null;int w=be(head,16),h=be(head,20);if(w>2048||h>2048)return null;Sampler s=samplers.get(path);boolean mipmaps=s!=null&&s.filter==2;Texture t=new Texture(f,mipmaps);Texture.TextureFilter min=s!=null&&s.filter==0?Texture.TextureFilter.Nearest:mipmaps?Texture.TextureFilter.MipMapLinearLinear:Texture.TextureFilter.Linear;Texture.TextureFilter mag=s!=null&&s.filter==0?Texture.TextureFilter.Nearest:Texture.TextureFilter.Linear;t.setFilter(min,mag);t.setWrap(wrap(s==null?0:s.u),wrap(s==null?0:s.v));if(s!=null&&s.aniso>1)t.setAnisotropicFilter(s.aniso);long bytes=textureBytes(t.getWidth(),t.getHeight(),mipmaps);textureCache.put(path,new TextureEntry(t,bytes));textureBytes+=bytes;textureLoads++;return t;}catch(Exception error){recordWarning("load texture "+path,error);return null;}}
    private static long textureBytes(int width,int height,boolean mipmaps){long total=0;int w=width,h=height;do{total+=(long)w*h*4;if(!mipmaps||(w==1&&h==1))break;w=Math.max(1,w/2);h=Math.max(1,h/2);}while(true);return total;}
    private void trimTextures(){if(textureBytes<=TEXTURE_BUDGET)return;Iterator<Map.Entry<String,TextureEntry>> it=textureCache.entrySet().iterator();while(textureBytes>TEXTURE_BUDGET&&it.hasNext()){Map.Entry<String,TextureEntry> e=it.next();if(visibleTextures.contains(e.getKey()))continue;textureBytes-=e.getValue().bytes;e.getValue().texture.dispose();textureEvictions++;it.remove();}}
    private void clearScene(){for(Mesh m:meshes)try{m.dispose();}catch(Exception ignored){}for(TextureEntry t:textureCache.values())try{t.texture.dispose();}catch(Exception ignored){}meshes.clear();textureCache.clear();textureBytes=0;renderItems.clear();doorMotion=null;doorRoomMask=0;doorRequest=null;activeDoorToken=0;boxColliders.clear();boxById.clear();meshColliders.clear();interactions.clear();interactionJson="";publishedInteraction=null;publishedNavigationRevision=Long.MIN_VALUE;interactionSnapshots=0;roomByCollider.clear();materials.clear();texturesByIndex.clear();texturesByPathId.clear();samplers.clear();depthWritingVisible.clear();transparentVisible.clear();profileStarted=profileNanos=textureLoads=textureEvictions=0;profileFrames=0;loaded=false;}
    private String resolve(String p){if(p==null||p.isEmpty()||p.startsWith("/")||p.contains(".."))return "";return p.startsWith(manifestDirectory)||manifestDirectory.isEmpty()?p:manifestDirectory+p;}
    private static float[] matrix(JSONArray rows){float[] m=new Matrix4().val;if(rows==null||rows.length()!=4)return m;for(int r=0;r<4;r++){JSONArray row=rows.optJSONArray(r);if(row==null)return m;for(int c=0;c<4;c++){float v=(float)row.optDouble(c,0);if((r==2)^(c==2))v=-v;m[c*4+r]=v;}}return m;}
    private static Bounds transformBounds(float[] m,float[] b){float ax=Float.MAX_VALUE,ay=ax,az=ax,bx=-ax,by=-ax,bz=-ax;for(int mask=0;mask<8;mask++){float x=b[0]+((mask&1)==0?-b[3]:b[3]),y=b[1]+((mask&2)==0?-b[4]:b[4]),z=-(b[2]+((mask&4)==0?-b[5]:b[5]));float wx=m[0]*x+m[4]*y+m[8]*z+m[12],wy=m[1]*x+m[5]*y+m[9]*z+m[13],wz=m[2]*x+m[6]*y+m[10]*z+m[14];ax=Math.min(ax,wx);ay=Math.min(ay,wy);az=Math.min(az,wz);bx=Math.max(bx,wx);by=Math.max(by,wy);bz=Math.max(bz,wz);}return new Bounds(ax,ay,az,bx,by,bz);}
    private static float pointTriangle(float px,float py,float pz,float[] t,int o){float ax=t[o],ay=t[o+1],az=t[o+2],bx=t[o+3],by=t[o+4],bz=t[o+5],cx=t[o+6],cy=t[o+7],cz=t[o+8];float abx=bx-ax,aby=by-ay,abz=bz-az,acx=cx-ax,acy=cy-ay,acz=cz-az,apx=px-ax,apy=py-ay,apz=pz-az,d1=abx*apx+aby*apy+abz*apz,d2=acx*apx+acy*apy+acz*apz;float qx,qy,qz;if(d1<=0&&d2<=0){qx=ax;qy=ay;qz=az;}else{float bpx=px-bx,bpy=py-by,bpz=pz-bz,d3=abx*bpx+aby*bpy+abz*bpz,d4=acx*bpx+acy*bpy+acz*bpz;if(d3>=0&&d4<=d3){qx=bx;qy=by;qz=bz;}else{float vc=d1*d4-d3*d2;if(vc<=0&&d1>=0&&d3<=0){float v=d1/(d1-d3);qx=ax+v*abx;qy=ay+v*aby;qz=az+v*abz;}else{float cpx=px-cx,cpy=py-cy,cpz=pz-cz,d5=abx*cpx+aby*cpy+abz*cpz,d6=acx*cpx+acy*cpy+acz*cpz;if(d6>=0&&d5<=d6){qx=cx;qy=cy;qz=cz;}else{float vb=d5*d2-d1*d6;if(vb<=0&&d2>=0&&d6<=0){float w=d2/(d2-d6);qx=ax+w*acx;qy=ay+w*acy;qz=az+w*acz;}else{float va=d3*d6-d5*d4;if(va<=0&&(d4-d3)>=0&&(d5-d6)>=0){float w=(d4-d3)/((d4-d3)+(d5-d6));qx=bx+w*(cx-bx);qy=by+w*(cy-by);qz=bz+w*(cz-bz);}else{float inv=1/(va+vb+vc),v=vb*inv,w=vc*inv;qx=ax+abx*v+acx*w;qy=ay+aby*v+acy*w;qz=az+abz*v+acz*w;}}}}}}float dx=px-qx,dy=py-qy,dz=pz-qz;return dx*dx+dy*dy+dz*dz;}
    private static float[] vec2(JSONArray a,float x,float y){return new float[]{a==null?x:(float)a.optDouble(0,x),a==null?y:(float)a.optDouble(1,y)};}
    private static String errorStatus(String stage,Throwable error){String value=error.getClass().getSimpleName()+": "+String.valueOf(error.getMessage());value=value.replace('\n',' ').replace('\r',' ').trim();if(value.length()>160)value=value.substring(0,157)+"...";return "error: "+stage+": "+value;}
    private String errorDiagnostic(String stage,Throwable error){StringWriter trace=new StringWriter();error.printStackTrace(new PrintWriter(trace));return "Renderer failure at "+stage+"\n"+glInfo+"\n\n"+trace;}
    private void recordWarning(String stage,Throwable error){if(warningStatus==null){warningStatus=errorStatus(stage,error);diagnostic=errorDiagnostic(stage,error);}}
    static float[] unityUvTransform(float scaleU,float scaleV,float offsetU,float offsetV){return new float[]{scaleU,-scaleV,offsetU,1f-offsetV};}
    private static int be(byte[] a,int i){return(a[i]&255)<<24|(a[i+1]&255)<<16|(a[i+2]&255)<<8|(a[i+3]&255);}
    private static Texture.TextureWrap wrap(int x){return x==1?Texture.TextureWrap.ClampToEdge:x==2?Texture.TextureWrap.MirroredRepeat:Texture.TextureWrap.Repeat;}
    private static float finite(float x){return Float.isNaN(x)||Float.isInfinite(x)?0:x;}private static float wrap(float v){v%=360;if(v>180)v-=360;if(v< -180)v+=360;return v;}
    @Override public void dispose(){clearScene();if(modelBatch!=null)modelBatch.dispose();}
    private static final class RangedPointLight extends PointLight {
        float range;
        RangedPointLight set(Color color,Vector3 position,float intensity,float range){super.set(color,position,intensity);this.range=range;return this;}
    }
    private static final class RangedSpotLight extends SpotLight {
        float range,innerCos,outerCos;
        RangedSpotLight set(Color color,Vector3 position,Vector3 direction,float intensity,float cutoff,float exponent,float range,float innerCutoff){
            super.set(color,position,direction,intensity,cutoff,exponent);this.range=range;innerCos=(float)Math.cos(Math.toRadians(innerCutoff));outerCos=(float)Math.cos(Math.toRadians(cutoff));return this;
        }
    }
    /** Uses the source project's sRGB/Linear path and its active URP Neutral volume curve. */
    private static final class SourceShaderProvider extends DefaultShaderProvider {
        private final DefaultShader.Config config;
        private final String vertex,fragment;
        SourceShaderProvider(){
            config=new DefaultShader.Config();
            config.numSpotLights=8;
            vertex=sourceVertex(DefaultShader.getDefaultVertexShader());
            fragment=sourceFragment(DefaultShader.getDefaultFragmentShader());
        }
        @Override protected Shader createShader(Renderable renderable){
            return new SourceDefaultShader(renderable,config,DefaultShader.createPrefix(renderable,config),vertex,fragment);
        }
        private static String sourceVertex(String original){
            String declaration="uniform PointLight u_pointLights[numPointLights];";
            String loop="vec3 value = u_pointLights[i].color * (NdotL / (1.0 + dist2));";
            if(!original.contains(declaration)||!original.contains(loop))throw new GdxRuntimeException("GDX point-light shader layout changed");
            // Unity Graphics URP/ShaderLibrary/RealtimeLights.hlsl: inverse-square attenuation with its smooth range window.
            String vertex=original.replace(declaration,declaration+"\nuniform float u_pointLightRanges[numPointLights];")
                .replace(loop,"float rangeSq = max(u_pointLightRanges[i] * u_pointLightRanges[i], 0.0001);\n"
                    +"\t\t\t\tfloat rangeFactor = clamp(1.0 - (dist2 / rangeSq) * (dist2 / rangeSq), 0.0, 1.0);\n"
                    +"\t\t\t\trangeFactor *= rangeFactor;\n"
                    +"\t\t\t\tvec3 value = u_pointLights[i].color * (NdotL * rangeFactor / max(dist2, 0.0001));");
            String pointStruct="#endif // numPointLights";
            if(!vertex.contains(pointStruct))throw new GdxRuntimeException("GDX point-light block changed");
            int pointEnd=vertex.indexOf(pointStruct);
            vertex=vertex.substring(0,pointEnd)+"#endif // numPointLights\n"
                +"#if numSpotLights > 0\nstruct SpotLight { vec3 color; vec3 position; vec3 direction; float cutoffAngle; float exponent; };\n"
                +"uniform SpotLight u_spotLights[numSpotLights];\nuniform float u_spotLightRanges[numSpotLights];\n"
                +"uniform float u_spotLightInnerCos[numSpotLights];\nuniform float u_spotLightOuterCos[numSpotLights];\n#endif // numSpotLights"+vertex.substring(pointEnd+pointStruct.length());
            String lightEnd="\t#endif // lightingFlag\n}";int end=vertex.lastIndexOf(lightEnd);
            if(end<0)throw new GdxRuntimeException("GDX lighting block changed");
            String spotLoop="""
                #if (numSpotLights > 0) && defined(normalFlag)
                    for (int i = 0; i < numSpotLights; i++) {
                        vec3 lightDir = u_spotLights[i].position - pos.xyz;
                        float dist2 = dot(lightDir, lightDir);
                        lightDir *= inversesqrt(max(dist2, 0.0001));
                        float NdotL = clamp(dot(normal, lightDir), 0.0, 1.0);
                        float rangeSq = max(u_spotLightRanges[i] * u_spotLightRanges[i], 0.0001);
                        float rangeFactor = clamp(1.0 - (dist2 / rangeSq) * (dist2 / rangeSq), 0.0, 1.0);
                        rangeFactor *= rangeFactor;
                        float SdotL = dot(-lightDir, u_spotLights[i].direction);
                        float spotFactor = clamp((SdotL - u_spotLightOuterCos[i]) / max(u_spotLightInnerCos[i] - u_spotLightOuterCos[i], 0.0001), 0.0, 1.0);
                        spotFactor *= spotFactor;
                        vec3 value = u_spotLights[i].color * (NdotL * rangeFactor * spotFactor / max(dist2, 0.0001));
                        v_lightDiffuse += value;
                    }
                #endif // numSpotLights
                """;
            return vertex.substring(0,end)+spotLoop+vertex.substring(end);
        }
        private static String sourceFragment(String original){
            String main="void main() {",afterDiffuse="\n\t#if defined(emissiveTextureFlag)";
            String alpha="\n\t#ifdef blendedFlag\n\t\tgl_FragColor.a = diffuse.a * v_opacity;";
            if(!original.contains(main)||!original.contains(afterDiffuse)||!original.contains(alpha))throw new GdxRuntimeException("GDX fragment shader layout changed");
            // sRGB transfer and NeutralCurve constants follow Unity Graphics Core/ShaderLibrary/Color.hlsl.
            String functions="""
                float sourceSrgbToLinearChannel(float c) {
                    c = max(c, 0.0);
                    return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4);
                }
                vec3 sourceSrgbToLinear(vec3 c) {
                    return vec3(sourceSrgbToLinearChannel(c.r), sourceSrgbToLinearChannel(c.g), sourceSrgbToLinearChannel(c.b));
                }
                float sourceLinearToSrgbChannel(float c) {
                    c = max(c, 0.0);
                    return c <= 0.0031308 ? 12.92 * c : 1.055 * pow(c, 0.416666667) - 0.055;
                }
                vec3 sourceLinearToSrgb(vec3 c) {
                    return vec3(sourceLinearToSrgbChannel(c.r), sourceLinearToSrgbChannel(c.g), sourceLinearToSrgbChannel(c.b));
                }
                vec3 sourceNeutralCurve(vec3 x) {
                    const float a = 0.2, b = 0.29, c = 0.24, d = 0.272, e = 0.02, f = 0.3;
                    return ((x * (a * x + c * b) + d * e) / (x * (a * x + b) + d * f)) - e / f;
                }
                vec3 sourceNeutralTonemap(vec3 x) {
                    x = max(vec3(0.0), x);
                    vec3 whiteScale = vec3(1.0) / sourceNeutralCurve(vec3(5.3));
                    return sourceNeutralCurve(x * whiteScale) * whiteScale;
                }
                """;
            return original.replace(main,functions+"\n"+main)
                .replace(afterDiffuse,"\n\tdiffuse.rgb = sourceSrgbToLinear(diffuse.rgb);\n"+afterDiffuse)
                .replace(alpha,"\n\tgl_FragColor.rgb = sourceLinearToSrgb(sourceNeutralTonemap(gl_FragColor.rgb));"+alpha);
        }
    }
    private static final class SourceDefaultShader extends DefaultShader {
        private final int[] pointRangeLocations,spotRangeLocations,spotInnerCosLocations,spotOuterCosLocations;
        private final float[] lastPointRanges,lastSpotRanges,lastSpotInnerCos,lastSpotOuterCos;
        SourceDefaultShader(Renderable renderable,DefaultShader.Config config,String prefix,String vertex,String fragment){
            super(renderable,config,prefix,vertex,fragment);
            pointRangeLocations=uniformLocations("u_pointLightRanges[",config.numPointLights);
            spotRangeLocations=uniformLocations("u_spotLightRanges[",config.numSpotLights);
            spotInnerCosLocations=uniformLocations("u_spotLightInnerCos[",config.numSpotLights);
            spotOuterCosLocations=uniformLocations("u_spotLightOuterCos[",config.numSpotLights);
            lastPointRanges=uninitialized(config.numPointLights);lastSpotRanges=uninitialized(config.numSpotLights);
            lastSpotInnerCos=uninitialized(config.numSpotLights);lastSpotOuterCos=uninitialized(config.numSpotLights);
        }
        private int[] uniformLocations(String prefix,int count){int[] locations=new int[count];for(int i=0;i<count;i++)locations[i]=program.fetchUniformLocation(prefix+i+"]",false);return locations;}
        private static float[] uninitialized(int size){float[] values=new float[size];java.util.Arrays.fill(values,Float.NaN);return values;}
        private void setIfChanged(int location,float value,float[] cached,int index){if(location<0||Float.floatToIntBits(value)==Float.floatToIntBits(cached[index]))return;program.setUniformf(location,value);cached[index]=value;}
        @Override protected void bindLights(Renderable renderable,com.badlogic.gdx.graphics.g3d.Attributes attributes){
            super.bindLights(renderable,attributes);
            com.badlogic.gdx.graphics.g3d.attributes.PointLightsAttribute pointAttribute=(com.badlogic.gdx.graphics.g3d.attributes.PointLightsAttribute)attributes.get(com.badlogic.gdx.graphics.g3d.attributes.PointLightsAttribute.Type);
            com.badlogic.gdx.graphics.g3d.attributes.SpotLightsAttribute spotAttribute=(com.badlogic.gdx.graphics.g3d.attributes.SpotLightsAttribute)attributes.get(com.badlogic.gdx.graphics.g3d.attributes.SpotLightsAttribute.Type);
            com.badlogic.gdx.utils.Array<PointLight> sourcePoints=pointAttribute==null?null:pointAttribute.lights;
            com.badlogic.gdx.utils.Array<SpotLight> sourceSpots=spotAttribute==null?null:spotAttribute.lights;
            int pointCount=Math.min(sourcePoints==null?0:sourcePoints.size,pointRangeLocations.length);
            for(int i=0;i<pointCount;i++){
                PointLight light=sourcePoints.get(i);float range=light instanceof RangedPointLight?((RangedPointLight)light).range:10000f;
                setIfChanged(pointRangeLocations[i],range,lastPointRanges,i);
            }
            int spotCount=Math.min(sourceSpots==null?0:sourceSpots.size,spotRangeLocations.length);
            for(int i=0;i<spotCount;i++){
                SpotLight light=sourceSpots.get(i);float range=light instanceof RangedSpotLight?((RangedSpotLight)light).range:10000f;
                float inner=light instanceof RangedSpotLight?((RangedSpotLight)light).innerCos:(float)Math.cos(Math.toRadians(light.cutoffAngle*.9));
                float outer=light instanceof RangedSpotLight?((RangedSpotLight)light).outerCos:(float)Math.cos(Math.toRadians(light.cutoffAngle));
                setIfChanged(spotRangeLocations[i],range,lastSpotRanges,i);
                setIfChanged(spotInnerCosLocations[i],inner,lastSpotInnerCos,i);
                setIfChanged(spotOuterCosLocations[i],outer,lastSpotOuterCos,i);
            }
        }
    }
    private static final class Bounds{final float minX,minY,minZ,maxX,maxY,maxZ,cx,cy,cz,hx,hy,hz,radius;Bounds(float a,float b,float c,float d,float e,float f){minX=a;minY=b;minZ=c;maxX=d;maxY=e;maxZ=f;cx=(a+d)*.5f;cy=(b+e)*.5f;cz=(c+f)*.5f;hx=(d-a)*.5f;hy=(e-b)*.5f;hz=(f-c)*.5f;radius=(float)Math.sqrt(hx*hx+hy*hy+hz*hz);}}
    private static final class MeshData{final List<Mesh> chunks;final float[] bounds;MeshData(List<Mesh>a,float[]b){chunks=a;bounds=b;}}
    private static final class RenderItem implements RenderableProvider {
        final String id;final Mesh mesh;final int sourceRendererId,offset,count;final Matrix4 matrix;final MaterialInfo material;final Bounds baseBounds;Bounds bounds;DoorMotion.Door door;
        final Renderable renderable=new Renderable();Texture boundTexture;
        RenderItem(String i,int sourceId,Mesh m,int o,int c,Matrix4 x,MaterialInfo f,Bounds b){id=i;sourceRendererId=sourceId;mesh=m;offset=o;count=c;matrix=x;material=f;bounds=baseBounds=b;renderable.meshPart.set(i,m,o,c,GL20.GL_TRIANGLES);renderable.worldTransform.set(x);renderable.material=makeMaterial(f,x);}
        @Override public void getRenderables(Array<Renderable> output,Pool<Renderable> pool){output.add(pool.obtain().set(renderable));}
    }
    private static final class DoorRequest{final int room;final long token;DoorRequest(int r,long t){room=r;token=t;}}
    private static final class MaterialInfo{final Color color;final String texture;final float su,sv,ou,ov,cutoff;final int cull,blendSrc,blendDst;final boolean transparent,zWrite,alphaClip;MaterialInfo(Color c,String t,float[] uv,int x,boolean a,int src,int dst,boolean zw,boolean clip,float cut){color=c;texture=t;su=uv[0];sv=uv[1];ou=uv[2];ov=uv[3];cull=x;transparent=a;blendSrc=src;blendDst=dst;zWrite=zw;alphaClip=clip;cutoff=cut;}}
    private static final class Sampler{final int filter,u,v,aniso;Sampler(int f,int a,int b,int n){filter=f;u=a;v=b;aniso=n;}}
    private static final class TextureEntry{final Texture texture;final long bytes;TextureEntry(Texture t,long b){texture=t;bytes=b;}}
    private static final class BoxCollider{final Matrix4 inverse;final float cx,cy,cz,hx,hy,hz,inverseScale;final Bounds bounds;BoxCollider(Matrix4 m,float x,float y,float z,float a,float b,float c,float s,Bounds q){inverse=m;cx=x;cy=y;cz=z;hx=a;hy=b;hz=c;inverseScale=s;bounds=q;}}
    private static final class TriangleCollider{final float[] xyz;final Bounds bounds;TriangleCollider(float[] x,Bounds b){xyz=x;bounds=b;}}
    private static final class Interaction{final int colliderId;final BoxCollider box;final JSONObject descriptor;Interaction(int i,BoxCollider b,JSONObject d){colliderId=i;box=b;descriptor=d;}}
}
