package org.reconstruction.current;

import org.json.JSONArray;
import org.json.JSONObject;
import java.util.HashMap;
import java.util.Map;

/** Runtime rules recovered from source room initialization and DialogViewData. */
final class HouseSceneData {
    private final Map<String, Fixture> fixtures = new HashMap<>();
    private float usualPanelX, tvPanelX;
    private float linePanelX, optionsPanelX;
    private float optionsOffsetY;
    private boolean hasDialogueLayout;

    static HouseSceneData parse(JSONObject source) {
        HouseSceneData result = new HouseSceneData();
        if (source == null || source.optInt("schema_version") != 1) return result;
        JSONObject runtime = source.optJSONObject("runtime");
        if (runtime == null) return result;
        JSONArray rows = runtime.optJSONArray("fixed_room_actors");
        if (rows != null) for (int i = 0; i < rows.length(); i++) {
            JSONObject row = rows.optJSONObject(i);
            if (row == null || !row.optBoolean("authored_active_self", false)) continue;
            String name = row.optString("name", "");
            int room = row.optInt("room", -1);
            String pose = row.optString("initial_pose_name", "");
            if (name.isEmpty() || room < 0 || room > 6 || pose.isEmpty() || result.fixtures.containsKey(name)) continue;
            result.fixtures.put(name, new Fixture(room, pose));
        }
        JSONObject dialogue = runtime.optJSONObject("dialogue");
        if (dialogue != null && dialogue.optBoolean("portrait_before_text", false)) {
            float normal = (float) dialogue.optDouble("default_panel_x", Double.NaN);
            float television = (float) dialogue.optDouble("tv_panel_x", Double.NaN);
            if (!Float.isNaN(normal) && !Float.isInfinite(normal)
                    && !Float.isNaN(television) && !Float.isInfinite(television)) {
                result.usualPanelX = normal;
                result.tvPanelX = television;
                result.linePanelX = normal;
                result.optionsPanelX = normal;
                result.hasDialogueLayout = true;
            }
        }
        return result;
    }

    void readPanelGeometry(JSONObject ui) {
        if (!hasDialogueLayout || ui == null) return;
        JSONArray rows = ui.optJSONArray("components");
        JSONArray line = null, options = null;
        if (rows != null) for (int i = 0; i < rows.length(); i++) {
            JSONObject row=rows.optJSONObject(i);
            if(row==null)continue;
            JSONObject transform=row.optJSONObject("rect_transform");
            JSONArray rect=transform==null?null:transform.optJSONArray("screen_rect_1920x1080");
            if(rect==null || rect.length()!=4)continue;
            if(row.optInt("path_id")==4637)line=rect;
            if(row.optInt("path_id")==4472)options=rect;
        }
        if(line==null || options==null)return;
        linePanelX=(float)(line.optDouble(0)+line.optDouble(2)*.5-960.0);
        optionsPanelX=(float)(options.optDouble(0)+options.optDouble(2)*.5-960.0);
        // DialogView.StartDialog copies the moved base panel's world position
        // to the options panel, including its slightly different serialized Y.
        optionsOffsetY=(float)(line.optDouble(1)+line.optDouble(3)*.5
                - options.optDouble(1)-options.optDouble(3)*.5);
    }

    boolean actorVisible(JSONObject actor, int selectedRoom, boolean playing) {
        if (actor == null || actor.optInt("room", -1) != selectedRoom) return false;
        if (actor.optBoolean("active", false)) return true;
        Fixture fixture = fixtures.get(actor.optString("name", ""));
        return playing && fixture != null && fixture.room == selectedRoom
                && actor.optBoolean("authored_active", false)
                && fixture.pose.equals(actor.optString("pose", ""));
    }

    float dialogueOffset(String companion, boolean options) {
        if (!hasDialogueLayout) return 0f;
        float target="TV".equals(companion)?tvPanelX:usualPanelX;
        return target-(options?optionsPanelX:linePanelX);
    }

    float dialogueOffsetY(boolean options) { return options?optionsOffsetY:0f; }

    private static final class Fixture {
        final int room;
        final String pose;
        Fixture(int room, String pose) { this.room = room; this.pose = pose; }
    }
}
