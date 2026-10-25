import com.badlogic.gdx.Files;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.graphics.g3d.shaders.DefaultShader;
import com.badlogic.gdx.graphics.g3d.shaders.DepthShader;

import java.lang.reflect.Proxy;

/** Run with a resource-free GDX classes jar and the delivered APK on the classpath. */
public final class ClasspathShaderProbe {
    private static final class ClasspathHandle extends FileHandle {
        ClasspathHandle(String path) { super(path, Files.FileType.Classpath); }
    }
    public static void main(String[] args) {
        Gdx.files=(Files)Proxy.newProxyInstance(Files.class.getClassLoader(),new Class<?>[]{Files.class},(proxy,method,values)->{
            if("classpath".equals(method.getName()))return new ClasspathHandle((String)values[0]);
            throw new UnsupportedOperationException(method.getName());
        });
        String[] shaders={DefaultShader.getDefaultVertexShader(),DefaultShader.getDefaultFragmentShader(),
            DepthShader.getDefaultVertexShader(),DepthShader.getDefaultFragmentShader()};
        for(String shader:shaders)if(!shader.contains("void main"))throw new AssertionError("invalid shader source");
        System.out.println("ClasspathShaderProbe: default/depth vertex and fragment resources loaded from delivered APK");
    }
}
