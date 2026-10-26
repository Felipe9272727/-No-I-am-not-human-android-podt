package org.reconstruction.current;

import com.badlogic.gdx.math.Matrix4;
import com.badlogic.gdx.math.Vector3;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** GL-thread door poses derived from the authored DoorTrigger hinge hierarchy. */
final class DoorMotion {
    static final class Door {
        final int room, pivotTransform;
        final float px, py, pz, openAngle, duration, closeModifier;
        final List<Integer> renderers = new ArrayList<>();
        final Matrix4 delta = new Matrix4();
        float angle;
        Door(int room, int pivot, float x, float y, float z, float angle, float duration, float close) {
            this.room=room; pivotTransform=pivot; px=x; py=y; pz=-z;
            openAngle=angle; this.duration=duration; closeModifier=close;
        }
        void setAngle(float value) {
            angle=value;
            // Reflecting Unity Z changes the sign of world-space Y rotation.
            delta.idt().translate(px,py,pz).rotate(Vector3.Y,-angle).translate(-px,-py,-pz);
        }
    }
    private final Map<Integer,Door> rooms=new HashMap<>(), renderers=new HashMap<>();
    private Door active;
    private float from,to,elapsed,duration;
    private boolean closing;

    DoorMotion(JSONObject world, JSONObject animation) {
        Map<Integer,JSONObject> transforms=new HashMap<>();
        JSONArray ts=world.optJSONArray("transforms");
        if(ts!=null)for(int i=0;i<ts.length();i++){
            JSONObject t=ts.optJSONObject(i);if(t!=null)transforms.put(t.optInt("path_id",-1),t);
        }
        JSONArray ds=animation.optJSONArray("door_triggers"), rs=world.optJSONArray("renderers");
        if(ds==null || rs==null)return;
        for(int i=0;i<ds.length();i++){
            JSONObject entry=ds.optJSONObject(i), fields=entry==null?null:entry.optJSONObject("serialized_fields");
            JSONObject pivot=entry==null?null:entry.optJSONObject("door_pivot");
            if(fields==null||pivot==null||!entry.optBoolean("enabled",true))continue;
            int pivotId=pivot.optInt("transform_path_id",-1),room=fields.optInt("linked_room_value",-1);
            JSONObject transform=transforms.get(pivotId);
            JSONArray matrix=transform==null?null:transform.optJSONArray("world_matrix_row_major");
            if(room<0||room>6||matrix==null||matrix.length()!=4)continue;
            float seconds=(float)fields.optDouble("duration_seconds",0), modifier=(float)fields.optDouble("close_speed_modifier",1);
            if(!finite(seconds)||seconds<=0||!finite(modifier)||modifier<=0)continue;
            JSONArray row0=matrix.optJSONArray(0),row1=matrix.optJSONArray(1),row2=matrix.optJSONArray(2);
            if(row0==null||row1==null||row2==null)continue;
            Door door=new Door(room,pivotId,(float)row0.optDouble(3,0),
                (float)row1.optDouble(3,0),(float)row2.optDouble(3,0),
                (float)fields.optDouble("open_angle_degrees",0),seconds,modifier);
            for(int r=0;r<rs.length();r++){
                JSONObject renderer=rs.optJSONObject(r);if(renderer==null)continue;
                int tid=renderer.optInt("transform_path_id",-1);
                for(int guard=0;tid>0&&guard<transforms.size();guard++){
                    if(tid==pivotId){int id=renderer.optInt("renderer_path_id",-1);door.renderers.add(id);renderers.put(id,door);break;}
                    JSONObject parent=transforms.get(tid);if(parent==null)break;tid=parent.optInt("parent_path_id",0);
                }
            }
            if(!door.renderers.isEmpty())rooms.put(room,door);
        }
    }
    private static boolean finite(float v){return !Float.isNaN(v)&&!Float.isInfinite(v);}
    int roomMask(){int mask=0;for(int room:rooms.keySet())mask|=1<<room;return mask;}
    Door forRenderer(int id){return renderers.get(id);}
    Door forRoom(int room){return rooms.get(room);}
    boolean open(int room){
        Door door=rooms.get(room);if(door==null)return false;
        reset();active=door;from=0;to=door.openAngle;elapsed=0;duration=door.duration;closing=false;return true;
    }
    void close(){
        if(active==null)return;from=active.angle;to=0;elapsed=0;duration=active.duration/active.closeModifier;closing=true;
    }
    boolean moving(){return active!=null&&elapsed<duration;}
    void advance(float dt){
        if(!moving()||!finite(dt)||dt<=0)return;
        elapsed=Math.min(duration,elapsed+dt);
        active.setAngle(from+(to-from)*ease(elapsed/duration,closing));
    }
    void reset(){for(Door door:rooms.values())door.setAngle(0);active=null;elapsed=duration=0;}
    // DoorTrigger ExtraActionIn uses Ease.OutCubic (9); Out uses InSine (2).
    static float ease(float t,boolean closing){
        t=Math.max(0,Math.min(1,t));
        return closing?(float)(1-Math.cos(t*Math.PI*.5)):1-(1-t)*(1-t)*(1-t);
    }
}
