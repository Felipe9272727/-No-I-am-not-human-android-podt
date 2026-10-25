import com.badlogic.gdx.ApplicationAdapter;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.backends.lwjgl3.Lwjgl3Application;
import com.badlogic.gdx.backends.lwjgl3.Lwjgl3ApplicationConfiguration;
import com.badlogic.gdx.graphics.Pixmap;
import com.badlogic.gdx.graphics.PixmapIO;
import com.badlogic.gdx.utils.ScreenUtils;
import org.json.JSONObject;
import org.reconstruction.current.RoomEngine;

/** Mesa/Xvfb preview of the real Android RoomEngine and staged source assets. */
public final class WorldPreview extends ApplicationAdapter {
    private final String output;private final float walkSeconds,forward;
    private RoomEngine engine;private long start;private boolean saved;
    private WorldPreview(String o,float s,float f){output=o;walkSeconds=s;forward=f;}
    @Override public void create(){try{JSONObject assets;try{assets=new JSONObject(Gdx.files.internal("presentation/assets.json").readString("UTF-8"));}catch(Exception missing){assets=new JSONObject();}if(!assets.has("world_manifest"))assets.put("world_manifest","world/world_manifest.json");JSONObject state=new JSONObject();state.put("phase","playing");state.put("view_mode","world");state.put("room",5);engine=new RoomEngine(assets);engine.setState(state);engine.create();engine.resize(Gdx.graphics.getWidth(),Gdx.graphics.getHeight());start=System.nanoTime();}catch(Exception e){throw new RuntimeException("World preview initialization failed",e);}}
    @Override public void render(){float elapsed=(System.nanoTime()-start)/1e9f;if(walkSeconds>0&&elapsed>=.8f&&elapsed<.8f+walkSeconds){engine.setInputEnabled(true);engine.setMoveVector(0,forward);}else{engine.setMoveVector(0,0);engine.setInputEnabled(false);}engine.render();if(!saved&&elapsed>Math.max(2.2f,.8f+walkSeconds+.5f)){saved=true;Pixmap p=ScreenUtils.getFrameBufferPixmap(0,0,Gdx.graphics.getWidth(),Gdx.graphics.getHeight());PixmapIO.writePNG(Gdx.files.local(output),p);p.dispose();System.out.println("WORLD_PREVIEW_POSE="+engine.getPose());Gdx.app.exit();}}
    @Override public void resize(int w,int h){if(engine!=null)engine.resize(w,h);}
    @Override public void dispose(){if(engine!=null)engine.dispose();}
    public static void main(String[] args){String output=args.length>0?args[0]:"world-preview.png";float seconds=args.length>1?Float.parseFloat(args[1]):0;float forward=args.length>2?Float.parseFloat(args[2]):1;Lwjgl3ApplicationConfiguration c=new Lwjgl3ApplicationConfiguration();c.setTitle("Recovered level-1 preview");c.setWindowedMode(1280,720);c.useVsync(false);c.setForegroundFPS(60);new Lwjgl3Application(new WorldPreview(output,seconds,forward),c);}
}
