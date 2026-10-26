import com.badlogic.gdx.Application;
import com.badlogic.gdx.ApplicationLogger;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.backends.lwjgl3.Lwjgl3Files;
import com.badlogic.gdx.graphics.GL20;
import com.badlogic.gdx.graphics.Pixmap;
import com.badlogic.gdx.graphics.PixmapIO;
import com.badlogic.gdx.graphics.glutils.GLVersion;
import com.badlogic.gdx.utils.GdxNativesLoader;
import com.badlogic.gdx.utils.ScreenUtils;
import org.json.JSONObject;
import org.lwjgl.BufferUtils;
import org.lwjgl.PointerBuffer;
import org.lwjgl.egl.EGL;
import org.lwjgl.egl.EGL10;
import org.lwjgl.egl.EGL14;
import org.lwjgl.opengles.GLES;
import org.reconstruction.current.RoomEngine;

import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.IntBuffer;
import java.nio.file.Files;
import java.nio.file.Path;

/** Mesa OpenGL ES 2 EGL pbuffer test of the Android RoomEngine, without X/GLFW. */
public final class WorldPreviewGLES {
    private static final int WIDTH = 1280, HEIGHT = 720;

    private static IntBuffer ints(int... values) {
        IntBuffer result = BufferUtils.createIntBuffer(values.length);
        result.put(values).flip();
        return result;
    }

    private static Object primitiveDefault(Class<?> type) {
        if (!type.isPrimitive() || type == void.class) return null;
        if (type == boolean.class) return false;
        if (type == char.class) return '\0';
        if (type == long.class) return 0L;
        if (type == float.class) return 0f;
        if (type == double.class) return 0d;
        return 0;
    }

    private static void installGdx(GL20 gl, Path assets) throws Exception {
        Gdx.gl = gl;
        Gdx.gl20 = gl;
        Gdx.gl30 = null;
        Gdx.files = (com.badlogic.gdx.Files) Proxy.newProxyInstance(com.badlogic.gdx.Files.class.getClassLoader(), new Class<?>[]{com.badlogic.gdx.Files.class}, (proxy, method, args) -> { if ("internal".equals(method.getName())) return new com.badlogic.gdx.files.FileHandle(assets.resolve((String)args[0]).toFile()); return method.invoke(new Lwjgl3Files(), args); });
        ApplicationLogger logger = new ApplicationLogger() {
            public void log(String tag, String message) { System.out.println(tag + ": " + message); }
            public void log(String tag, String message, Throwable ex) { log(tag, message); ex.printStackTrace(); }
            public void error(String tag, String message) { System.err.println(tag + ": " + message); }
            public void error(String tag, String message, Throwable ex) { error(tag, message); ex.printStackTrace(); }
            public void debug(String tag, String message) { System.out.println(tag + ": " + message); }
            public void debug(String tag, String message, Throwable ex) { debug(tag, message); ex.printStackTrace(); }
        };
        Gdx.app = (Application)Proxy.newProxyInstance(Application.class.getClassLoader(), new Class<?>[]{Application.class}, new InvocationHandler() {
            public Object invoke(Object proxy, java.lang.reflect.Method method, Object[] args) {
                switch (method.getName()) {
                    case "getType": return Application.ApplicationType.Android;
                    case "getApplicationLogger": return logger;
                    case "postRunnable": ((Runnable)args[0]).run(); return null;
                    case "log": System.out.println(args[0] + ": " + args[1]); return null;
                    case "error": System.err.println(args[0] + ": " + args[1]); return null;
                    case "debug": System.out.println(args[0] + ": " + args[1]); return null;
                    case "getVersion": return 0;
                    default: return primitiveDefault(method.getReturnType());
                }
            }
        });
        GLVersion version = new GLVersion(Application.ApplicationType.Android,
                org.lwjgl.opengles.GLES20.glGetString(org.lwjgl.opengles.GLES20.GL_VERSION),
                org.lwjgl.opengles.GLES20.glGetString(org.lwjgl.opengles.GLES20.GL_VENDOR),
                org.lwjgl.opengles.GLES20.glGetString(org.lwjgl.opengles.GLES20.GL_RENDERER));
        Gdx.graphics = (com.badlogic.gdx.Graphics)Proxy.newProxyInstance(
                com.badlogic.gdx.Graphics.class.getClassLoader(), new Class<?>[]{com.badlogic.gdx.Graphics.class},
                new InvocationHandler() {
                    public Object invoke(Object proxy, java.lang.reflect.Method method, Object[] args) {
                        switch (method.getName()) {
                            case "getWidth": case "getBackBufferWidth": return WIDTH;
                            case "getHeight": case "getBackBufferHeight": return HEIGHT;
                            case "getDeltaTime": case "getRawDeltaTime": return 1f / 60f;
                            case "getFramesPerSecond": return 60;
                            case "getGL20": return gl;
                            case "getGL30": return null;
                            case "isGL30Available": return false;
                            case "getGLVersion": return version;
                            case "getPpiX": case "getPpiY": return 96f;
                            case "getDensity": return 1f;
                            case "getDisplayMode": case "getPrimaryMonitor": return null;
                            case "supportsExtension": return false;
                            default: return primitiveDefault(method.getReturnType());
                        }
                    }
                });
    }

    private static long[] createEglPbuffer() {
        long display = EGL10.eglGetDisplay(0L);
        IntBuffer major = BufferUtils.createIntBuffer(1), minor = BufferUtils.createIntBuffer(1);
        if (!EGL10.eglInitialize(display, major, minor)) throw new IllegalStateException("eglInitialize failed");
        EGL.createDisplayCapabilities(display, major.get(0), minor.get(0));
        if (!EGL14.eglBindAPI(EGL14.EGL_OPENGL_ES_API)) throw new IllegalStateException("eglBindAPI(OpenGL ES) failed");
        IntBuffer attributes = ints(EGL10.EGL_SURFACE_TYPE, EGL10.EGL_PBUFFER_BIT,
                0x3040, 0x0004,
                EGL10.EGL_RED_SIZE, 8, EGL10.EGL_GREEN_SIZE, 8, EGL10.EGL_BLUE_SIZE, 8,
                EGL10.EGL_ALPHA_SIZE, 8, EGL10.EGL_DEPTH_SIZE, 24, EGL10.EGL_STENCIL_SIZE, 8, EGL10.EGL_NONE);
        PointerBuffer configs = BufferUtils.createPointerBuffer(1);
        IntBuffer count = BufferUtils.createIntBuffer(1);
        if (!EGL10.eglChooseConfig(display, attributes, configs, count) || count.get(0) == 0)
            throw new IllegalStateException("No OpenGL ES 2 pbuffer EGLConfig");
        long config = configs.get(0);
        long surface = EGL10.eglCreatePbufferSurface(display, config,
                ints(EGL10.EGL_WIDTH, WIDTH, EGL10.EGL_HEIGHT, HEIGHT, EGL10.EGL_NONE));
        long context = EGL10.eglCreateContext(display, config, EGL10.EGL_NO_CONTEXT, ints(0x3098, 2, EGL10.EGL_NONE));
        if (surface == EGL10.EGL_NO_SURFACE || context == EGL10.EGL_NO_CONTEXT
                || !EGL10.eglMakeCurrent(display, surface, surface, context))
            throw new IllegalStateException("Could not make EGL pbuffer current");
        return new long[]{display, surface, context};
    }

    public static void main(String[] args) throws Exception {
        Path assets = Path.of(args.length > 0 ? args[0] : "reconstruction/android-current/app/src/main/assets").toAbsolutePath();
        Path output = Path.of(args.length > 1 ? args[1] : "/tmp/ninah-world-egl.png").toAbsolutePath();
        float yaw = args.length > 2 ? Float.parseFloat(args[2]) : 0f;
        float pitch = args.length > 4 ? Float.parseFloat(args[4]) : 0f;
        Float x = args.length > 7 ? Float.parseFloat(args[5]) : null;
        Float y = args.length > 7 ? Float.parseFloat(args[6]) : null;
        Float z = args.length > 7 ? Float.parseFloat(args[7]) : null;
        if (!Files.isRegularFile(assets.resolve("presentation/assets.json")))
            throw new IllegalStateException("missing presentation/assets.json in " + assets);
        GdxNativesLoader.load();
        long[] egl = createEglPbuffer();
        GLES.createCapabilities();
        Class<?> glClass = Class.forName("com.badlogic.gdx.backends.lwjgl3.angle.Lwjgl3GLES20");
        Constructor<?> constructor = glClass.getDeclaredConstructor();
        constructor.setAccessible(true);
        GL20 gl = (GL20)constructor.newInstance();
        installGdx(gl, assets);
        JSONObject assetJson = new JSONObject(new String(Files.readAllBytes(assets.resolve("presentation/assets.json")), StandardCharsets.UTF_8));
        RoomEngine engine = new RoomEngine(assetJson);
        JSONObject pose = new JSONObject().put("revision", 1).put("yaw", yaw).put("pitch", pitch);
        if (x != null) pose.put("position", new org.json.JSONArray().put(x).put(y).put(z));
        JSONObject state = new JSONObject().put("phase", "playing").put("view_mode", "world").put("room", 5)
                .put("world_pose", pose);
        engine.setState(state);
        engine.create();
        if(args.length>10 && "ambient-only".equals(args[10])) {
            java.lang.reflect.Field wf=RoomEngine.class.getDeclaredField("worldRenderer");wf.setAccessible(true);Object wr=wf.get(engine);
            java.lang.reflect.Field ef=wr.getClass().getDeclaredField("environment");ef.setAccessible(true);
            com.badlogic.gdx.graphics.g3d.Environment ambientOnly=new com.badlogic.gdx.graphics.g3d.Environment();
            ambientOnly.set(com.badlogic.gdx.graphics.g3d.attributes.ColorAttribute.createAmbientLight(.114f,.125f,.133f,1f));ef.set(wr,ambientOnly);
        }
        engine.resize(WIDTH, HEIGHT);
        if (args.length > 3 && "room-compositions".equals(args[3])) {
            renderRoomCompositions(engine, output);
            engine.dispose();
            EGL10.eglMakeCurrent(egl[0], EGL10.EGL_NO_SURFACE, EGL10.EGL_NO_SURFACE, EGL10.EGL_NO_CONTEXT);
            EGL10.eglDestroyContext(egl[0], egl[2]);
            EGL10.eglDestroySurface(egl[0], egl[1]);
            EGL10.eglTerminate(egl[0]);
            return;
        }
        Gdx.gl.glViewport(0, 0, WIDTH, HEIGHT);
        Gdx.gl.glClearColor(.05f, .05f, .06f, 1f);
        Gdx.gl.glClear(GL20.GL_COLOR_BUFFER_BIT | GL20.GL_DEPTH_BUFFER_BIT);
        boolean inject=args.length>3 && "inject-shader-failure".equals(args[3]);
        if(inject) {
            final boolean[] once={false}; final GL20 delegate=gl;
            GL20 faulty=(GL20)Proxy.newProxyInstance(GL20.class.getClassLoader(),new Class<?>[]{GL20.class},(proxy,method,values)->{
                if(!once[0]&&"glCompileShader".equals(method.getName())) {once[0]=true;throw new com.badlogic.gdx.utils.GdxRuntimeException("shader compilation injected failure");}
                try{return method.invoke(delegate,values);}catch(java.lang.reflect.InvocationTargetException e){throw e.getCause();}
            });
            Gdx.gl=faulty;Gdx.gl20=faulty;
        }
        long measuredNanos=0;int measuredFrames=0;
        for(int i=0;i<120;i++) {
            long frameStart=System.nanoTime();
            engine.render();
            String status=engine.getRendererStatus();
            if(status.startsWith("error:"))throw new IllegalStateException(engine.getRendererDiagnostic());
            int error=gl.glGetError();if(error!=GL20.GL_NO_ERROR)throw new IllegalStateException("GLES error 0x"+Integer.toHexString(error)+" frame "+i);
            if(i>=20){measuredNanos+=System.nanoTime()-frameStart;measuredFrames++;}
        }
        if(inject&&!engine.getRendererDiagnostic().contains("Unlit GLES fallback active"))throw new AssertionError("fallback did not activate");
        if(args.length>8 && "ray-hit".equals(args[8]))printCenterRayHit(engine,assets);
        if(args.length>11 && args[11].startsWith("door-room:"))runDoorMotionSequence(engine,Integer.parseInt(args[11].substring("door-room:".length())),output);
        System.out.println("HOST_RENDER_MEAN_MS="+(measuredNanos/1e6/measuredFrames));
        System.out.println("RENDERER_DIAGNOSTIC="+engine.getRendererDiagnostic());
        Pixmap pixmap = ScreenUtils.getFrameBufferPixmap(0, 0, WIDTH, HEIGHT);
        if(args.length>9 && "expect-ceiling-detail".equals(args[9])) {
            int white=0;java.util.Set<Integer> colors=new java.util.HashSet<>();int samples=0;
            for(int py=HEIGHT/3;py<HEIGHT*2/3;py++)for(int px=WIDTH*5/16;px<WIDTH*11/16;px++){
                int color=pixmap.getPixel(px,py),r=(color>>>24)&255,g=(color>>>16)&255,b=(color>>>8)&255;
                if(r>=250&&g>=250&&b>=250)white++;colors.add(color&0xffffff);samples++;
            }
            double clipped=(double)white/samples;
            System.out.println("CEILING_DETAIL clipped="+clipped+" uniquePixels="+colors.size());
            if(clipped>.20||colors.size()<100)throw new AssertionError("Source ceiling is still clipped white: clipped="+clipped+" uniquePixels="+colors.size());
        }
        PixmapIO.writePNG(new com.badlogic.gdx.files.FileHandle(output.toFile()), pixmap, -1, true);
        pixmap.dispose();
        System.out.println("GL_RENDERER=" + org.lwjgl.opengles.GLES20.glGetString(org.lwjgl.opengles.GLES20.GL_RENDERER));
        System.out.println("GL_VERSION=" + org.lwjgl.opengles.GLES20.glGetString(org.lwjgl.opengles.GLES20.GL_VERSION));
        System.out.println("WORLD_PREVIEW_POSE=" + engine.getPose());
        System.out.println("WORLD_PREVIEW_PNG=" + output);
        engine.dispose();
        EGL10.eglMakeCurrent(egl[0], EGL10.EGL_NO_SURFACE, EGL10.EGL_NO_SURFACE, EGL10.EGL_NO_CONTEXT);
        EGL10.eglDestroyContext(egl[0], egl[2]);
        EGL10.eglDestroySurface(egl[0], egl[1]);
        EGL10.eglTerminate(egl[0]);
    }

    private static void renderRoomCompositions(RoomEngine engine, Path output) throws Exception {
        Path directory = output.getParent();
        Files.createDirectories(directory);
        for (int room = 0; room < 7; room++) {
            engine.setState(new JSONObject().put("phase", "playing").put("view_mode", "room").put("room", room));
            engine.render();
            if (engine.getRendererStatus().startsWith("error:")) throw new IllegalStateException(engine.getRendererDiagnostic());
            int error = Gdx.gl.glGetError();
            if (error != GL20.GL_NO_ERROR) throw new IllegalStateException("Room GLES error: " + error);
            Pixmap pixmap = ScreenUtils.getFrameBufferPixmap(0, 0, WIDTH, HEIGHT);
            PixmapIO.writePNG(new com.badlogic.gdx.files.FileHandle(directory.resolve("room-" + room + ".png").toFile()), pixmap, -1, true);
            pixmap.dispose();
        }
        System.out.println("ROOM_COMPOSITIONS=7; original static layers, empty campaign roster");
    }

    /** Optional CPU ray probe reports the first source mesh/material at screen center. */
    private static void printCenterRayHit(RoomEngine engine,Path assets)throws Exception {
        java.lang.reflect.Field worldField=RoomEngine.class.getDeclaredField("worldRenderer");worldField.setAccessible(true);
        Object world=worldField.get(engine);Class<?> wc=world.getClass();
        java.lang.reflect.Field itemsField=wc.getDeclaredField("renderItems");itemsField.setAccessible(true);
        java.util.List<?> items=(java.util.List<?>)itemsField.get(world);
        java.lang.reflect.Field poseField=wc.getDeclaredField("player");poseField.setAccessible(true);
        com.badlogic.gdx.math.Vector3 origin=new com.badlogic.gdx.math.Vector3((com.badlogic.gdx.math.Vector3)poseField.get(world));
        java.lang.reflect.Field yawField=wc.getDeclaredField("yaw"),pitchField=wc.getDeclaredField("pitch");yawField.setAccessible(true);pitchField.setAccessible(true);
        float yaw=(float)yawField.get(world),pitch=(float)pitchField.get(world),yr=(float)Math.toRadians(yaw),pr=(float)Math.toRadians(pitch),h=(float)Math.cos(pr);
        com.badlogic.gdx.math.Vector3 dir=new com.badlogic.gdx.math.Vector3((float)Math.sin(yr)*h,-(float)Math.sin(pr),-(float)Math.cos(yr)*h).nor();
        org.json.JSONArray renderers=new org.json.JSONObject(Files.readString(assets.resolve("world/world_manifest.json"))).getJSONArray("renderers");
        java.util.Map<Object,float[]> vertices=new java.util.IdentityHashMap<>();java.util.Map<Object,short[]> indices=new java.util.IdentityHashMap<>();
        float nearest=Float.POSITIVE_INFINITY;String report="none";
        for(Object item:items){Class<?> c=item.getClass();java.lang.reflect.Field meshF=c.getDeclaredField("mesh"),matrixF=c.getDeclaredField("matrix"),offsetF=c.getDeclaredField("offset"),countF=c.getDeclaredField("count"),idF=c.getDeclaredField("id");for(java.lang.reflect.Field f:new java.lang.reflect.Field[]{meshF,matrixF,offsetF,countF,idF})f.setAccessible(true);
            Object mesh=meshF.get(item);float[] v=vertices.get(mesh);short[] ix=indices.get(mesh);
            if(v==null){com.badlogic.gdx.graphics.Mesh m=(com.badlogic.gdx.graphics.Mesh)mesh;v=new float[m.getNumVertices()*8];ix=new short[m.getNumIndices()];m.getVertices(v);m.getIndices(ix);vertices.put(mesh,v);indices.put(mesh,ix);}
            com.badlogic.gdx.math.Matrix4 matrix=(com.badlogic.gdx.math.Matrix4)matrixF.get(item);int offset=offsetF.getInt(item),count=countF.getInt(item);String id=(String)idF.get(item);int rendererIndex=Integer.parseInt(id.split("-")[1]);
            for(int k=offset;k<offset+count;k+=3){int ia=ix[k]&0xffff,ib=ix[k+1]&0xffff,ic=ix[k+2]&0xffff;com.badlogic.gdx.math.Vector3 a=new com.badlogic.gdx.math.Vector3(v[ia*8],v[ia*8+1],v[ia*8+2]).mul(matrix),b=new com.badlogic.gdx.math.Vector3(v[ib*8],v[ib*8+1],v[ib*8+2]).mul(matrix),cpos=new com.badlogic.gdx.math.Vector3(v[ic*8],v[ic*8+1],v[ic*8+2]).mul(matrix);float t=rayTriangle(origin,dir,a,b,cpos);if(t>=0&&t<nearest){nearest=t;org.json.JSONObject row=renderers.getJSONObject(rendererIndex);report="renderer="+row.optInt("renderer_path_id",-1)+" name="+row.optString("name")+" materials="+row.optJSONArray("material_indices")+" distance="+t;}}
        }
        System.out.println("CENTER_RAY_HIT="+report);
    }
    private static float rayTriangle(com.badlogic.gdx.math.Vector3 origin,com.badlogic.gdx.math.Vector3 dir,com.badlogic.gdx.math.Vector3 a,com.badlogic.gdx.math.Vector3 b,com.badlogic.gdx.math.Vector3 c){
        com.badlogic.gdx.math.Vector3 e1=new com.badlogic.gdx.math.Vector3(b).sub(a),e2=new com.badlogic.gdx.math.Vector3(c).sub(a),p=new com.badlogic.gdx.math.Vector3(dir).crs(e2);float det=e1.dot(p);if(Math.abs(det)<1e-7f)return -1;float inv=1f/det;com.badlogic.gdx.math.Vector3 s=new com.badlogic.gdx.math.Vector3(origin).sub(a);float u=s.dot(p)*inv;if(u<0||u>1)return -1;com.badlogic.gdx.math.Vector3 q=new com.badlogic.gdx.math.Vector3(s).crs(e1);float v=dir.dot(q)*inv;if(v<0||u+v>1)return -1;float t=e2.dot(q)*inv;return t>=0?t:-1;
    }
    private static void runDoorMotionSequence(RoomEngine engine,int room,Path output)throws Exception {
        if(room!=0)throw new IllegalArgumentException("Host visual door fixture currently targets source Kitchen room 0");
        Path dir=output.toAbsolutePath().getParent();java.nio.file.Files.createDirectories(dir);
        java.util.Map<String,Object> fixture=doorFixture(engine,2141);
        if(fixture==null)throw new AssertionError("Kitchen renderer 2141 is missing from render items");
        Pixmap before=ScreenUtils.getFrameBufferPixmap(0,0,WIDTH,HEIGHT);
        PixmapIO.writePNG(new com.badlogic.gdx.files.FileHandle(dir.resolve("door-room-0-before.png").toFile()),before,-1,true);
        long token=engine.beginDoorOpen(room);if(token<=0)throw new AssertionError("Kitchen DoorTrigger was not accepted");
        for(int i=0;i<30;i++)engine.render();
        fixture=doorFixture(engine,2141);float midAngle=(Float)fixture.get("angle");boolean completedMid=engine.isDoorOpenComplete(token);
        float pivotDrift=(Float)fixture.get("pivotDrift");
        Pixmap mid=ScreenUtils.getFrameBufferPixmap(0,0,WIDTH,HEIGHT);
        PixmapIO.writePNG(new com.badlogic.gdx.files.FileHandle(dir.resolve("door-room-0-mid.png").toFile()),mid,-1,true);
        if(Math.abs(midAngle)<1||completedMid||pivotDrift>.001f)throw new AssertionError("Kitchen door midpoint invalid angle="+midAngle+" complete="+completedMid+" pivotDrift="+pivotDrift);
        engine.setPresentationPaused(true);float pausedAt=(Float)doorFixture(engine,2141).get("angle");
        for(int i=0;i<15;i++)engine.render();float pausedEnd=(Float)doorFixture(engine,2141).get("angle");
        if(Math.abs(pausedEnd-pausedAt)>.0001f||engine.isDoorOpenComplete(token))throw new AssertionError("Door moved or completed while presentation was paused");
        engine.setPresentationPaused(false);
        // Allow one frame past the remaining authored half-second for float rounding.
        for(int i=0;i<31;i++)engine.render();
        if(!engine.isDoorOpenComplete(token))throw new AssertionError("Door open completion token did not complete at source duration");
        fixture=doorFixture(engine,2141);float fullAngle=(Float)fixture.get("angle");pivotDrift=(Float)fixture.get("pivotDrift");
        Pixmap full=ScreenUtils.getFrameBufferPixmap(0,0,WIDTH,HEIGHT);
        PixmapIO.writePNG(new com.badlogic.gdx.files.FileHandle(dir.resolve("door-room-0-open.png").toFile()),full,-1,true);
        int changedPixels=changedPixels(before,full,8);
        if(Math.abs(Math.abs(fullAngle)-90f)>.1f||pivotDrift>.001f||changedPixels<50)throw new AssertionError("Open door visual/pivot mismatch angle="+fullAngle+" pivotDrift="+pivotDrift+" changedPixels="+changedPixels);
        long cancelToken=engine.beginDoorOpen(room);for(int i=0;i<10;i++)engine.render();engine.cancelDoorMotion();engine.render();
        float cancelAngle=(Float)doorFixture(engine,2141).get("angle");boolean canceledCompleted=engine.isDoorOpenComplete(cancelToken);
        if(Math.abs(cancelAngle)>.0001f||canceledCompleted)throw new AssertionError("Cancel did not reset an in-flight door: angle="+cancelAngle+" completed="+canceledCompleted);
        long closeToken=engine.beginDoorOpen(room);for(int i=0;i<61;i++)engine.render();
        if(!engine.isDoorOpenComplete(closeToken))throw new AssertionError("Door did not reopen before close regression");
        engine.setState(new JSONObject().put("phase","playing").put("view_mode","room").put("room",room));engine.render();
        engine.setState(new JSONObject().put("phase","playing").put("view_mode","world").put("room",room));
        for(int i=0;i<31;i++)engine.render();
        float closedAngle=(Float)doorFixture(engine,2141).get("angle");
        if(Math.abs(closedAngle)>.0001f)throw new AssertionError("Door did not finish its source-speed close: angle="+closedAngle);
        System.out.println("DOOR_GLES={\"room\":"+room+",\"renderer\":2141,\"token\":"+token+",\"midAngle\":"+midAngle+",\"openAngle\":"+fullAngle+",\"openComplete\":true,\"pauseFrozen\":true,\"cancelAngle\":"+cancelAngle+",\"cancelComplete\":"+canceledCompleted+",\"closedAngle\":"+closedAngle+",\"hingeDrift\":"+pivotDrift+",\"changedPixels\":"+changedPixels+"}");
        before.dispose();mid.dispose();full.dispose();
    }
    private static java.util.Map<String,Object> doorFixture(RoomEngine engine,int sourceRenderer)throws Exception {
        java.lang.reflect.Field worldField=RoomEngine.class.getDeclaredField("worldRenderer");worldField.setAccessible(true);Object world=worldField.get(engine);
        java.lang.reflect.Field itemsField=world.getClass().getDeclaredField("renderItems");itemsField.setAccessible(true);
        for(Object item:(java.util.List<?>)itemsField.get(world)){
            Class<?> type=item.getClass();java.lang.reflect.Field id=type.getDeclaredField("sourceRendererId");id.setAccessible(true);if(id.getInt(item)!=sourceRenderer)continue;
            java.lang.reflect.Field doorField=type.getDeclaredField("door");doorField.setAccessible(true);Object door=doorField.get(item);if(door==null)throw new AssertionError("Kitchen render item is not attached to a DoorTrigger");
            java.lang.reflect.Field angle=door.getClass().getDeclaredField("angle"),delta=door.getClass().getDeclaredField("delta"),px=door.getClass().getDeclaredField("px"),py=door.getClass().getDeclaredField("py"),pz=door.getClass().getDeclaredField("pz");
            for(java.lang.reflect.Field f:new java.lang.reflect.Field[]{angle,delta,px,py,pz})f.setAccessible(true);
            com.badlogic.gdx.math.Vector3 pivot=new com.badlogic.gdx.math.Vector3(px.getFloat(door),py.getFloat(door),pz.getFloat(door));
            float drift=pivot.dst(new com.badlogic.gdx.math.Vector3(pivot).mul((com.badlogic.gdx.math.Matrix4)delta.get(door)));
            java.util.Map<String,Object> values=new java.util.HashMap<>();values.put("angle",angle.getFloat(door));values.put("pivotDrift",drift);return values;
        }
        return null;
    }
    private static int changedPixels(Pixmap a,Pixmap b,int threshold){int changed=0;for(int y=0;y<a.getHeight();y++)for(int x=0;x<a.getWidth();x++){int p=a.getPixel(x,y),q=b.getPixel(x,y);int dr=Math.abs(((p>>>24)&255)-((q>>>24)&255)),dg=Math.abs(((p>>>16)&255)-((q>>>16)&255)),db=Math.abs(((p>>>8)&255)-((q>>>8)&255));if(Math.max(dr,Math.max(dg,db))>threshold)changed++;}return changed;}
}
