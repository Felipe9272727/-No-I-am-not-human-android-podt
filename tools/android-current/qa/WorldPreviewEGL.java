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
import org.lwjgl.opengl.GL;
import org.reconstruction.current.RoomEngine;

import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.IntBuffer;
import java.nio.file.Files;
import java.nio.file.Path;

/** Direct Mesa EGL pbuffer preview of the Android RoomEngine, without X/GLFW. */
public final class WorldPreviewEGL {
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

    private static void installGdx(GL20 gl) throws Exception {
        Gdx.gl = gl;
        Gdx.gl20 = gl;
        Gdx.gl30 = null;
        Gdx.files = new Lwjgl3Files();
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
                    case "getType": return Application.ApplicationType.Desktop;
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
        GLVersion version = new GLVersion(Application.ApplicationType.Desktop,
                org.lwjgl.opengl.GL11.glGetString(org.lwjgl.opengl.GL11.GL_VERSION),
                org.lwjgl.opengl.GL11.glGetString(org.lwjgl.opengl.GL11.GL_VENDOR),
                org.lwjgl.opengl.GL11.glGetString(org.lwjgl.opengl.GL11.GL_RENDERER));
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
        if (!EGL14.eglBindAPI(EGL14.EGL_OPENGL_API)) throw new IllegalStateException("eglBindAPI(OpenGL) failed");
        IntBuffer attributes = ints(EGL10.EGL_SURFACE_TYPE, EGL10.EGL_PBUFFER_BIT,
                0x3040, 0x0008,
                EGL10.EGL_RED_SIZE, 8, EGL10.EGL_GREEN_SIZE, 8, EGL10.EGL_BLUE_SIZE, 8,
                EGL10.EGL_ALPHA_SIZE, 8, EGL10.EGL_DEPTH_SIZE, 24, EGL10.EGL_STENCIL_SIZE, 8, EGL10.EGL_NONE);
        PointerBuffer configs = BufferUtils.createPointerBuffer(1);
        IntBuffer count = BufferUtils.createIntBuffer(1);
        if (!EGL10.eglChooseConfig(display, attributes, configs, count) || count.get(0) == 0)
            throw new IllegalStateException("No OpenGL pbuffer EGLConfig");
        long config = configs.get(0);
        long surface = EGL10.eglCreatePbufferSurface(display, config,
                ints(EGL10.EGL_WIDTH, WIDTH, EGL10.EGL_HEIGHT, HEIGHT, EGL10.EGL_NONE));
        long context = EGL10.eglCreateContext(display, config, EGL10.EGL_NO_CONTEXT, ints(EGL10.EGL_NONE));
        if (surface == EGL10.EGL_NO_SURFACE || context == EGL10.EGL_NO_CONTEXT
                || !EGL10.eglMakeCurrent(display, surface, surface, context))
            throw new IllegalStateException("Could not make EGL pbuffer current");
        return new long[]{display, surface, context};
    }

    public static void main(String[] args) throws Exception {
        Path assets = Path.of(args.length > 0 ? args[0] : "reconstruction/android-current/app/src/main/assets").toAbsolutePath();
        Path output = Path.of(args.length > 1 ? args[1] : "/tmp/ninah-world-egl.png").toAbsolutePath();
        float yaw = args.length > 2 ? Float.parseFloat(args[2]) : 0f;
        if (!Files.isRegularFile(assets.resolve("presentation/assets.json")))
            throw new IllegalStateException("missing presentation/assets.json in " + assets);
        GdxNativesLoader.load();
        long[] egl = createEglPbuffer();
        GL.createCapabilities();
        Class<?> glClass = Class.forName("com.badlogic.gdx.backends.lwjgl3.Lwjgl3GL20");
        Constructor<?> constructor = glClass.getDeclaredConstructor();
        constructor.setAccessible(true);
        GL20 gl = (GL20)constructor.newInstance();
        installGdx(gl);
        JSONObject assetJson = new JSONObject(new String(Files.readAllBytes(assets.resolve("presentation/assets.json")), StandardCharsets.UTF_8));
        RoomEngine engine = new RoomEngine(assetJson);
        JSONObject state = new JSONObject().put("phase", "playing").put("view_mode", "world").put("room", 5)
                .put("world_pose", new JSONObject().put("revision", 1).put("yaw", yaw));
        engine.setState(state);
        engine.create();
        engine.resize(WIDTH, HEIGHT);
        Gdx.gl.glViewport(0, 0, WIDTH, HEIGHT);
        Gdx.gl.glClearColor(.05f, .05f, .06f, 1f);
        Gdx.gl.glClear(GL20.GL_COLOR_BUFFER_BIT | GL20.GL_DEPTH_BUFFER_BIT);
        engine.render();
        Pixmap pixmap = ScreenUtils.getFrameBufferPixmap(0, 0, WIDTH, HEIGHT);
        PixmapIO.writePNG(new com.badlogic.gdx.files.FileHandle(output.toFile()), pixmap, -1, true);
        pixmap.dispose();
        System.out.println("GL_VERSION=" + org.lwjgl.opengl.GL11.glGetString(org.lwjgl.opengl.GL11.GL_VERSION));
        System.out.println("WORLD_PREVIEW_POSE=" + engine.getPose());
        System.out.println("WORLD_PREVIEW_PNG=" + output);
        engine.dispose();
        EGL10.eglMakeCurrent(egl[0], EGL10.EGL_NO_SURFACE, EGL10.EGL_NO_SURFACE, EGL10.EGL_NO_CONTEXT);
        EGL10.eglDestroyContext(egl[0], egl[2]);
        EGL10.eglDestroySurface(egl[0], egl[1]);
        EGL10.eglTerminate(egl[0]);
    }
}
