package org.reconstruction.current;

import com.badlogic.gdx.Files;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.math.Matrix4;
import com.badlogic.gdx.math.Vector3;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.List;

/** CPU-only test of source collider parsing, ray targets and movement in the exported scene. */
public final class WorldGeometryTest {
    public static void main(String[] args) throws Exception {
        File assetRoot=new File(args.length>0?args[0]:"reconstruction/android-current/app/src/main/assets").getCanonicalFile();
        Gdx.files=(Files)Proxy.newProxyInstance(Files.class.getClassLoader(),new Class<?>[]{Files.class},(proxy,method,values)->{
            if("internal".equals(method.getName()))return new FileHandle(new File(assetRoot,(String)values[0]));
            throw new UnsupportedOperationException(method.getName());
        });
        JSONObject manifest=new JSONObject(new String(java.nio.file.Files.readAllBytes(new File(assetRoot,"world/world_manifest.json").toPath()),java.nio.charset.StandardCharsets.UTF_8));
        WorldRenderer renderer=new WorldRenderer("");
        set(renderer,"manifestDirectory","world/");
        verifyRendererParity(manifest);
        verifyMaterialSettings(renderer,manifest);
        call(renderer,"parseColliders",new Class[]{JSONArray.class,JSONArray.class},manifest.optJSONArray("colliders"),manifest.optJSONArray("meshes"));
        verifyObbCollisionAndSupport(manifest);
        call(renderer,"parseTargets",new Class[]{JSONArray.class,JSONArray.class},manifest.optJSONArray("interaction_targets"),manifest.optJSONArray("named_door_targets"));

        JSONArray doors=new JSONArray();int[] colliderIds={2425,2449,2452,2453,2460,2439},rooms={0,1,2,3,4,6};
        for(int i=0;i<colliderIds.length;i++)doors.put(new JSONObject().put("collider_path_id",colliderIds[i]).put("room",rooms[i]));
        JSONObject campaign=new JSONObject().put("door_waiting",true);
        JSONObject nav=new JSONObject().put("room_doors",doors).put("entrance_interaction",new JSONObject().put("collider_path_id",2432));
        JSONObject pose=new JSONObject().put("position",new JSONArray().put(-3.9849998951).put(1.5839999765).put(-6.998000145)).put("yaw",0).put("pitch",0).put("revision",1);
        renderer.applyState(new JSONObject().put("view_mode","world").put("campaign",campaign).put("world_navigation",nav).put("world_pose",pose));

        Field interactionsField=WorldRenderer.class.getDeclaredField("interactions");interactionsField.setAccessible(true);
        @SuppressWarnings("unchecked") List<Object> interactions=(List<Object>)interactionsField.get(renderer);
        Method ray=WorldRenderer.class.getDeclaredMethod("rayBox",Class.forName("org.reconstruction.current.WorldRenderer$BoxCollider"),Vector3.class,Vector3.class,float.class);ray.setAccessible(true);
        for(int id:new int[]{2425,2449,2452,2453,2460,2439,2432}) {
            Object target=null;for(Object item:interactions)if(((Integer)get(item,"colliderId"))==id){target=item;break;}
            if(target==null)throw new AssertionError("Missing source RaycastTarget collider "+id);
            Object box=get(target,"box");Matrix4 inverse=(Matrix4)get(box,"inverse"),world=new Matrix4(inverse).inv();
            float cx=(float)get(box,"cx"),cy=(float)get(box,"cy"),cz=(float)get(box,"cz");
            float[] half={(float)get(box,"hx"),(float)get(box,"hy"),(float)get(box,"hz")};int thin=0;if(half[1]<half[thin])thin=1;if(half[2]<half[thin])thin=2;
            Vector3 normal=new Vector3(thin==0?1:0,thin==1?1:0,thin==2?1:0).rot(world).nor();
            Vector3 center=new Vector3(cx,cy,cz).mul(world),origin=new Vector3(center).mulAdd(normal,1f),direction=new Vector3(normal).scl(-1f);
            float hit=(float)ray.invoke(renderer,box,origin,direction,1f);
            if(hit<0||hit>1f)throw new AssertionError("Source ray missed collider "+id+" at "+center+" (hit="+hit+")");
            JSONObject descriptor=(JSONObject)get(target,"descriptor");
            if(id==2432){if(!"open_door".equals(descriptor.optString("action")))throw new AssertionError("Entrance waiting action: "+descriptor);}
            else {int expected=rooms[indexOf(colliderIds,id)];if(!"enter_room".equals(descriptor.optString("action"))||descriptor.optInt("room",-1)!=expected)throw new AssertionError("Interior door mapping for "+id+": "+descriptor);}
        }

        Method move=WorldRenderer.class.getDeclaredMethod("movePlayer",float.class,float.class,float.class);move.setAccessible(true);
        Vector3 start=getPlayer(renderer);for(int i=0;i<500;i++)move.invoke(renderer,0f,1f,.05f);Vector3 stop=getPlayer(renderer);
        float travelled=stop.dst(start);
        System.out.println("WORLD_GEOMETRY_MOVEMENT start="+start+" stop="+stop+" travelled="+travelled);
        if(travelled<.25f)throw new AssertionError("Player could not move from source camera spawn; likely trapped inside a whole-house bounds collider");
        if(travelled>4f)throw new AssertionError("Player passed the first source doorway wall; expected triangle/OBB collision stop, got "+travelled+" m");
        if(Math.abs(stop.z-4.22954f)>.8f)throw new AssertionError("Player did not stop against the source entrance RaycastTrigger plane: "+stop);
        for(int i=0;i<100;i++)move.invoke(renderer,0f,1f,.05f);
        Vector3 held=getPlayer(renderer);if(held.dst(stop)>.02f)throw new AssertionError("Movement kept crossing the doorway after contact: "+held);
        System.out.println("WorldGeometryTest: PASS (7 source ray targets, room actions, mesh/OBB collision)");
    }
    private static void verifyObbCollisionAndSupport(JSONObject manifest)throws Exception{
        WorldRenderer isolated=new WorldRenderer("");float[] m=new Matrix4().val;m[0]=46.00448f;m[5]=0f;m[6]=-4.290301f;m[9]=2.194689f;m[10]=0f;
        Method make=WorldRenderer.class.getDeclaredMethod("makeBox",float[].class,float.class,float.class,float.class,float.class,float.class,float.class);make.setAccessible(true);
        Object box=make.invoke(isolated,m,0f,0f,0f,.0118425f,.1012477f,.0207781f);
        @SuppressWarnings("unchecked") List<Object> boxes=(List<Object>)get(isolated,"boxColliders");boxes.add(box);
        Matrix4 world=(Matrix4)get(box,"world");Vector3 c=new Vector3(0,0,0).mul(world);float eye=c.y+.825f;
        Method collision=WorldRenderer.class.getDeclaredMethod("collides",float.class,float.class,float.class);collision.setAccessible(true);
        for(float sign:new float[]{-1,1}){
            boolean near=(Boolean)collision.invoke(isolated,c.x+sign*(.0118425f*46.00448f+.1f),eye,c.z);
            boolean far=(Boolean)collision.invoke(isolated,c.x+sign*(.0118425f*46.00448f+.5f),eye,c.z);
            if(!near)throw new AssertionError("OBB should block a 0.1 m side contact");
            if(far)throw new AssertionError("OBB produced a false block 0.5 m beyond its thin face");
        }
        Method support=WorldRenderer.class.getDeclaredMethod("boxSupportY",Class.forName("org.reconstruction.current.WorldRenderer$BoxCollider"),float.class,float.class);support.setAccessible(true);float top=(Float)support.invoke(isolated,box,c.x,c.z);
        if(!Float.isFinite(top))throw new AssertionError("Tilted box top face was not accepted as a support surface");
        Method floor=WorldRenderer.class.getDeclaredMethod("floorY",float.class,float.class,float.class);floor.setAccessible(true);float halfZ=.1012477f*4.290301f;
        for(float sign:new float[]{-1,1}){float approached=(Float)floor.invoke(isolated,c.x,c.z+sign*(halfZ+.1f),top-.1f);if(Math.abs(approached-top)>.001f)throw new AssertionError("Hatch support failed while approaching from side "+sign+" y="+approached+" top="+top);float departed=(Float)floor.invoke(isolated,c.x,c.z-sign*(halfZ+.1f),top-.1f);if(Math.abs(departed-top)>.001f)throw new AssertionError("Hatch support failed while crossing toward opposite side "+sign);}
        if(!Float.isNaN((Float)floor.invoke(isolated,c.x,c.z,top-.33f)))throw new AssertionError("A surface more than the 0.32 m step-up limit was accepted");
        if(!Float.isNaN((Float)floor.invoke(isolated,c.x,c.z+halfZ+.5f,top-.1f)))throw new AssertionError("A hatch face 0.5 m outside its edge supplied support");
        float[] ceilingMatrix=new Matrix4().val;ceilingMatrix[13]=top+1.3f;Object ceiling=make.invoke(isolated,ceilingMatrix,0f,0f,0f,1f,.05f,1f);boxes.add(ceiling);
        if(!(Boolean)collision.invoke(isolated,c.x,top+1.75f,c.z))throw new AssertionError("Headroom collider above the hatch was bypassed");
        JSONObject hatch=null;JSONArray sourceColliders=manifest.optJSONArray("colliders");for(int i=0;i<sourceColliders.length();i++){JSONObject candidate=sourceColliders.optJSONObject(i);if(candidate!=null&&candidate.optInt("path_id",-1)==2407){hatch=candidate;break;}}if(hatch==null)throw new AssertionError("Source hatch collider 2407 missing");JSONArray hatchRows=hatch.optJSONArray("world_matrix_row_major"),size=hatch.optJSONArray("size"),center=hatch.optJSONArray("center");float[] sourceMatrix=new Matrix4().val;for(int r=0;r<4;r++)for(int col=0;col<4;col++){float value=(float)hatchRows.optJSONArray(r).optDouble(col,0);if((r==2)^(col==2))value=-value;sourceMatrix[col*4+r]=value;}Object sourceBox=make.invoke(isolated,sourceMatrix,(float)center.optDouble(0,0),(float)center.optDouble(1,0),(float)center.optDouble(2,0),(float)size.optDouble(0,0)*.5f,(float)size.optDouble(1,0)*.5f,(float)size.optDouble(2,0)*.5f);Vector3 sourceCenter=new Vector3((float)center.optDouble(0,0),(float)center.optDouble(1,0),-(float)center.optDouble(2,0)).mul(new Matrix4(sourceMatrix));if(!Float.isFinite((Float)support.invoke(isolated,sourceBox,sourceCenter.x,sourceCenter.z)))throw new AssertionError("Source hatch collider 2407 has no upward OBB support face");
        verifyHatchWalk(sourceBox,sourceCenter,top,.1012477f*4.290301f);
        JSONArray colliders=manifest.optJSONArray("colliders");int orthogonal=0;for(int i=0;i<colliders.length();i++){JSONObject src=colliders.optJSONObject(i);if(src==null||!"BoxCollider".equals(src.optString("type"))||!src.optBoolean("active_in_hierarchy",false)||!src.optBoolean("enabled",false))continue;JSONArray rows=src.optJSONArray("world_matrix_row_major");if(rows==null)continue;float[][] a=new float[3][3];for(int r=0;r<3;r++)for(int col=0;col<3;col++)a[r][col]=(float)rows.optJSONArray(r).optDouble(col,0)*(r==2?-1:1);for(int u=0;u<3;u++)for(int v=u+1;v<3;v++){double dot=0,lu=0,lv=0;for(int k=0;k<3;k++){dot+=a[k][u]*a[k][v];lu+=a[k][u]*a[k][u];lv+=a[k][v]*a[k][v];}if(Math.abs(dot/Math.sqrt(lu*lv))>1e-5)throw new AssertionError("Active BoxCollider axes are not orthogonal: "+src.optInt("path_id"));}orthogonal++;}
        if(orthogonal==0)throw new AssertionError("No active BoxCollider fixtures found");System.out.println("WORLD_OBB_COLLISION activeOrthogonal="+orthogonal+" thinFaceContact=PASS falseBlock=PASS tiltedSupportBothWays=PASS stepWindow=PASS headroom=PASS");
    }

    private static void verifyHatchWalk(Object sourceBox,Vector3 center,float top,float halfZ)throws Exception{
        for(float side:new float[]{-1,1}){WorldRenderer walk=new WorldRenderer("");@SuppressWarnings("unchecked") List<Object> boxes=(List<Object>)get(walk,"boxColliders");boxes.add(sourceBox);
            float floor=top-.035f,extent=3f;float[] xyz={center.x-extent,floor,center.z-extent,center.x+extent,floor,center.z-extent,center.x+extent,floor,center.z+extent,center.x-extent,floor,center.z-extent,center.x+extent,floor,center.z+extent,center.x-extent,floor,center.z+extent};
            Class<?> boundsType=Class.forName("org.reconstruction.current.WorldRenderer$Bounds");java.lang.reflect.Constructor<?> bc=boundsType.getDeclaredConstructor(float.class,float.class,float.class,float.class,float.class,float.class);bc.setAccessible(true);Object bounds=bc.newInstance(center.x-extent,floor,center.z-extent,center.x+extent,floor,center.z+extent);
            Class<?> triangleType=Class.forName("org.reconstruction.current.WorldRenderer$TriangleCollider");java.lang.reflect.Constructor<?> tc=triangleType.getDeclaredConstructor(float[].class,boundsType);tc.setAccessible(true);@SuppressWarnings("unchecked") List<Object> triangles=(List<Object>)get(walk,"meshColliders");triangles.add(tc.newInstance(xyz,bounds));
            set(walk,"player",new Vector3(center.x,floor+1.65f,center.z+side*(halfZ+1f)));Method tryMove=WorldRenderer.class.getDeclaredMethod("tryMove",float.class,float.class);tryMove.setAccessible(true);for(int i=0,steps=(int)Math.ceil(2f*(halfZ+1f)/.05f);i<steps;i++)tryMove.invoke(walk,0f,-side*.05f);
            Vector3 end=getPlayer(walk);float expectedZ=center.z-side*(halfZ+1f);if(Math.abs(end.z-expectedZ)>.12f)throw new AssertionError("Player failed to cross source hatch 2407 from side "+side+": "+end);
            if(Math.abs((end.y-1.65f)-floor)>.01f)throw new AssertionError("Player did not descend to the mesh floor after crossing hatch from side "+side+": "+end);
        }
    }
    private static void verifyRendererParity(JSONObject manifest)throws Exception{
        JSONArray renderers=manifest.optJSONArray("renderers");int active=0,negative=0;for(int i=0;i<renderers.length();i++){JSONObject r=renderers.optJSONObject(i);if(r==null||!r.optBoolean("active_in_hierarchy",false)||!r.optBoolean("enabled",true))continue;active++;JSONArray rows=r.optJSONArray("world_matrix_row_major");float[] m=new float[16];for(int y=0;y<4;y++)for(int x=0;x<4;x++)m[x*4+y]=(float)rows.optJSONArray(y).optDouble(x,0);if(WorldRenderer.determinant3x3(m)<0)negative++;}
        if(active!=109||negative!=33)throw new AssertionError("Unexpected active renderer determinant population: active="+active+" reflected="+negative);
        float[] reflected={-1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};if(WorldRenderer.determinant3x3(reflected)>=0)throw new AssertionError("Negative determinant fixture was not detected");// Feed serialized Unity enum values, as parseMaterials/render actually do.
        int[] unityCull={0,1,2};int[] positive={com.badlogic.gdx.graphics.GL20.GL_NONE,com.badlogic.gdx.graphics.GL20.GL_FRONT,com.badlogic.gdx.graphics.GL20.GL_BACK};int[] negativeFaces={com.badlogic.gdx.graphics.GL20.GL_NONE,com.badlogic.gdx.graphics.GL20.GL_BACK,com.badlogic.gdx.graphics.GL20.GL_FRONT};
        for(int i=0;i<unityCull.length;i++)if(WorldRenderer.cullFaceForTransform(unityCull[i],1)!=positive[i]||WorldRenderer.cullFaceForTransform(unityCull[i],-1)!=negativeFaces[i])throw new AssertionError("Unity Cull enum "+unityCull[i]+" was not converted to GL before transform parity");
        System.out.println("WORLD_RENDERER_PARITY active="+active+" reflected="+negative+" determinant=PASS");
    }
    private static void verifyMaterialSettings(WorldRenderer renderer,JSONObject manifest)throws Exception{
        Field byIndex=WorldRenderer.class.getDeclaredField("texturesByIndex");byIndex.setAccessible(true);@SuppressWarnings("unchecked") java.util.Map<Integer,String> paths=(java.util.Map<Integer,String>)byIndex.get(renderer);paths.put(7,"diffuse.png");paths.put(8,"normal.png");
        JSONArray refs=new JSONArray().put(new JSONObject().put("property","_BumpMap").put("texture_index",8)).put(new JSONObject().put("property","_BaseMap").put("texture_index",7).put("scale",new JSONArray().put(2).put(3)));
        JSONObject fixture=new JSONObject().put("color",new JSONArray().put(1).put(1).put(1).put(1)).put("float_properties",new JSONObject().put("_Cull",2).put("_Surface",1).put("_SrcBlend",1).put("_DstBlend",10).put("_ZWrite",0).put("_AlphaClip",1).put("_Cutoff",.35)).put("texture_refs",refs);
        JSONObject alphaZero=new JSONObject().put("color",new JSONArray().put(1).put(1).put(1).put(0));JSONObject normalOnly=new JSONObject().put("texture_refs",new JSONArray().put(new JSONObject().put("property","_BumpMap").put("texture_index",8)));
        call(renderer,"parseMaterials",new Class[]{JSONArray.class},new JSONArray().put(fixture).put(alphaZero).put(normalOnly));Field f=WorldRenderer.class.getDeclaredField("materials");f.setAccessible(true);Object material=((java.util.Map<?,?>)f.get(renderer)).get(0);if(material==null)throw new AssertionError("Material parser dropped synthetic fixture");
        if(WorldRenderer.cullFaceForTransform((Integer)get(material,"cull"),1)!=com.badlogic.gdx.graphics.GL20.GL_BACK)throw new AssertionError("Parsed Unity Cull=2 did not reach GL_BACK");
        if(!"diffuse.png".equals(get(material,"texture")))throw new AssertionError("Diffuse map selection chose a non-albedo texture");if(!((Boolean)get(material,"transparent"))||((Boolean)get(material,"zWrite")))throw new AssertionError("Unity blend/ZWrite settings were not retained");if(!((Boolean)get(material,"alphaClip"))||Math.abs((Float)get(material,"cutoff")-.35f)>.001f)throw new AssertionError("Unity alpha clip settings were not retained");if((Integer)get(material,"blendSrc")!=com.badlogic.gdx.graphics.GL20.GL_SRC_ALPHA||(Integer)get(material,"blendDst")!=com.badlogic.gdx.graphics.GL20.GL_ONE_MINUS_SRC_ALPHA)throw new AssertionError("Premultiplied blend pair was not mapped to straight-alpha factors");Object invisible=((java.util.Map<?,?>)f.get(renderer)).get(1);if((Boolean)get(invisible,"zWrite")||(Integer)get(invisible,"blendSrc")!=com.badlogic.gdx.graphics.GL20.GL_SRC_ALPHA||(Integer)get(invisible,"blendDst")!=com.badlogic.gdx.graphics.GL20.GL_ONE_MINUS_SRC_ALPHA)throw new AssertionError("Alpha-zero material without float properties can still write depth or uses opaque blending");Object normal=((java.util.Map<?,?>)f.get(renderer)).get(2);if(!((String)get(normal,"texture")).isEmpty())throw new AssertionError("Normal-only texture was selected as diffuse");
        int[] counts=new int[3];JSONArray source=manifest.optJSONArray("materials");for(int i=0;i<source.length();i++){JSONObject m=source.optJSONObject(i),p=m==null?null:m.optJSONObject("float_properties");if(p!=null){if(p.optDouble("_ZWrite",1)<.5)counts[0]++;if(p.optDouble("_AlphaClip",0)>.5)counts[1]++;if(p.optDouble("_Surface",0)>.5)counts[2]++;}}
        System.out.println("WORLD_MATERIAL_SOURCE zwriteOff="+counts[0]+" alphaClip="+counts[1]+" transparentSurface="+counts[2]+" fixture=PASS");
    }
    private static int indexOf(int[] values,int x){for(int i=0;i<values.length;i++)if(values[i]==x)return i;throw new AssertionError();}
    private static Vector3 getPlayer(Object renderer)throws Exception{Field f=WorldRenderer.class.getDeclaredField("player");f.setAccessible(true);return new Vector3((Vector3)f.get(renderer));}
    private static Object get(Object object,String name)throws Exception{Field f=object.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(object);}
    private static void set(Object object,String name,Object value)throws Exception{Field f=object.getClass().getDeclaredField(name);f.setAccessible(true);f.set(object,value);}
    private static void call(Object object,String name,Class<?>[] types,Object...args)throws Exception{Method m=WorldRenderer.class.getDeclaredMethod(name,types);m.setAccessible(true);m.invoke(object,args);}
}
