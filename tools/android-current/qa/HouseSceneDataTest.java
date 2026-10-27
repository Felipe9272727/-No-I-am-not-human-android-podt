package org.reconstruction.current;

import org.json.JSONObject;
import org.json.JSONArray;
import java.nio.file.Files;
import java.nio.file.Path;

/** Regressions for source house fixtures mistakenly treated as occupants. */
public final class HouseSceneDataTest {
    public static void main(String[] args) throws Exception {
        Path assets=Path.of(args[0]);
        JSONObject source=new JSONObject(Files.readString(assets.resolve("presentation/ui/tv_source_manifest.json")));
        HouseSceneData scene=HouseSceneData.parse(source);
        JSONObject tv=new JSONObject().put("name","TV").put("room",6).put("pose","FullSize")
                .put("active",false).put("authored_active",true);
        check(scene.actorVisible(tv,6,true),"TV must appear in the empty house independently of visitor roster");
        check(!scene.actorVisible(tv,6,false),"fixture must not leak into a different debug character preview");
        check(!scene.actorVisible(tv,0,true),"TV must not appear in another room");
        tv.put("authored_active",false);
        check(!scene.actorVisible(tv,6,true),"a source-disabled fixture must not be activated");
        JSONObject neighbour=new JSONObject().put("name","Neighbour").put("room",6).put("pose","FullSize")
                .put("active",false).put("authored_active",true);
        check(!scene.actorVisible(neighbour,6,true),"authored visitor placeholders must remain absent before admission");
        neighbour.put("active",true);
        check(scene.actorVisible(neighbour,6,true),"native visitor activation must remain effective");
        JSONObject ui=new JSONObject(Files.readString(assets.resolve("presentation/ui/ui_manifest.json")));
        scene.readPanelGeometry(ui);
        check(scene.dialogueOffset("TV",false)==-958f,"TV line panel must move from serialized X=383 to source X=-575");
        check(scene.dialogueOffset("TV",true)==-960f,"TV options panel must move from serialized X=385 to source X=-575");
        check(scene.dialogueOffset("Neighbour",false)==2f,"ordinary line panel must use runtime X=385");
        check(scene.dialogueOffset("Neighbour",true)==0f,"ordinary options panel must retain source X=385");
        check(Math.abs(scene.dialogueOffsetY(true)+.4092f)<.001f,"options must copy base panel world Y");
        JSONArray components=ui.getJSONArray("components");
        int checked=0;
        for(int i=0;i<components.length();i++) {
            JSONObject item=components.getJSONObject(i);
            if(item.getInt("path_id")!=4637 && item.getInt("path_id")!=4784)continue;
            JSONArray rect=item.getJSONObject("rect_transform").getJSONArray("screen_rect_1920x1080");
            double left=rect.getDouble(0)+scene.dialogueOffset("TV",false),right=left+rect.getDouble(2);
            check(left>=0 && right<960,"the original TV line panel and text must sit on the left, away from presenter");
            checked++;
        }
        check(checked==2,"source TV line panel and text IDs must exist");
        System.out.println("HOUSE_SCENE_SOURCE_FIXTURES_AND_TV_DIALOGUE=PASS");
    }
    private static void check(boolean value,String message) { if(!value)throw new AssertionError(message); }
}
