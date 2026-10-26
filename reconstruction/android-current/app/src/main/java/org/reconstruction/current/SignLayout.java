package org.reconstruction.current;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Source-authored dialogue sign layers. Coordinates use the 1920x1080 canvas. */
final class SignLayout {
    static final int EYE = 0, HANDS = 1, TEETH = 2, PHOTO = 3, ARMPIT = 4, EAR = 5;

    static final class Layer {
        final int imageId; // Unity Image component path ID; dynamic sprite lookup remains runtime-owned.
        final int sourceFileId, sourcePathId, maskImageId;
        final String role, asset;
        final float[] rect; // left, top, right, bottom in reference pixels.
        final boolean preserveAspect;
        final Movement movement;

        Layer(int id, int fileId, int pathId, int maskId, String layerRole, String sourceAsset,
              float[] bounds, boolean preserve, Movement sourceMovement) {
            imageId=id; sourceFileId=fileId; sourcePathId=pathId; maskImageId=maskId;
            role=layerRole; asset=sourceAsset; rect=bounds; preserveAspect=preserve; movement=sourceMovement;
        }

        float[] rectAt(long elapsedMs) {
            if (movement == null) return (float[])rect.clone();
            float progress=movement.progress(elapsedMs);
            float dx=movement.start[0]+(movement.end[0]-movement.start[0])*progress;
            float dy=movement.start[1]+(movement.end[1]-movement.start[1])*progress;
            return new float[]{rect[0]+dx,rect[1]-dy,rect[2]+dx,rect[3]-dy};
        }
    }

    static final class Movement {
        final int contentImageId, easeValue;
        final float[] start, end;
        final float durationSeconds, beforeDelaySeconds;
        final boolean proceduralAnimationSupported;

        Movement(int id, int ease, float[] from, float[] to, float duration, float delay,
                 boolean sourceGeometryCompatible) {
            contentImageId=id; easeValue=ease; start=from; end=to;
            durationSeconds=duration; beforeDelaySeconds=delay;
            proceduralAnimationSupported=sourceGeometryCompatible && (ease == 2 || ease == 9) && duration > 0;
        }

        private float progress(long elapsedMs) {
            if (!proceduralAnimationSupported) throw new IllegalStateException("Unsupported source sign tween ease");
            double t=Math.max(0d,Math.min(1d,(elapsedMs-beforeDelaySeconds*1000d)/(durationSeconds*1000d)));
            if (easeValue == 2) return (float)(1d-Math.cos(t*Math.PI/2d)); // DG.Tweening.Ease.InSine
            return (float)(1d+Math.pow(t-1d,3d)); // DG.Tweening.Ease.OutCubic
        }
    }

    static final class View {
        final int sign;
        final String name;
        final float[] bounds;
        final List<Layer> layers;
        final Movement movement;
        final boolean hideDialogPlate, hideDialogueText;

        View(int signId, String signName, float[] box, List<Layer> sourceLayers,
             Movement sourceMovement, boolean hidePlate, boolean hideText) {
            sign=signId; name=signName; bounds=box;
            layers=Collections.unmodifiableList(sourceLayers);
            movement=sourceMovement; hideDialogPlate=hidePlate; hideDialogueText=hideText;
        }

        long nextRedrawDelayMs(long elapsedMs) {
            if (movement == null || !movement.proceduralAnimationSupported) return 0L;
            long delayEnd=(long)Math.ceil(movement.beforeDelaySeconds*1000d);
            if (elapsedMs < delayEnd) return Math.max(1L,delayEnd-elapsedMs);
            long total=(long)Math.ceil((movement.beforeDelaySeconds+movement.durationSeconds)*1000d);
            return elapsedMs < total ? 16L : 0L;
        }
    }

    private final Map<Integer, View> views;
    private SignLayout(Map<Integer, View> all) { views=Collections.unmodifiableMap(all); }

    static SignLayout parse(JSONObject config, JSONObject uiManifest) throws Exception {
        if (config == null || config.optInt("schema_version", -1) != 1)
            throw new IllegalArgumentException("Unsupported sign layout schema");
        if (uiManifest == null) throw new IllegalArgumentException("Missing UI manifest");
        JSONArray uiItems = uiManifest.optJSONObject("scenes") == null ? null
            : uiManifest.optJSONObject("scenes").optJSONArray("dialogue");
        if (uiItems == null) throw new IllegalArgumentException("UI manifest has no dialogue scene");
        Map<Integer, JSONObject> uiById = new HashMap<>();
        for (int i=0; i<uiItems.length(); i++) {
            JSONObject item=uiItems.optJSONObject(i);
            if (item != null) uiById.put(item.optInt("path_id", -1), item);
        }
        JSONObject sourceView=config.optJSONObject("view");
        JSONObject textContainer=sourceView == null ? null : sourceView.optJSONObject("text_container");
        boolean hidePlate=textContainer != null && textContainer.optBoolean("hide_during_sign", false);
        JSONArray sourceSigns=config.optJSONArray("signs");
        if (sourceSigns == null || sourceSigns.length() != 6)
            throw new IllegalArgumentException("Expected six source sign layouts");
        Map<Integer, View> result=new HashMap<>();
        for (int i=0; i<sourceSigns.length(); i++) {
            JSONObject sign=sourceSigns.getJSONObject(i);
            int signId=sign.getInt("enum_value");
            Movement movement=null;
            JSONObject move=sign.optJSONObject("movement");
            if (move != null) {
                JSONArray a=move.optJSONArray("start_position"), b=move.optJSONArray("end_position");
                if (a == null || b == null || a.length() < 3 || b.length() < 3)
                    throw new IllegalArgumentException("Incomplete sign movement metadata: " + sign.optString("name"));
                JSONArray parentScale=move.optJSONArray("parent_local_scale"), baseline=move.optJSONArray("content_local_position");
                boolean geometryCompatible="Transform.localPosition".equals(move.optString("coordinate_space"))
                    && move.optInt("canvas_path_id", -1) == 3101
                    && parentScale != null && parentScale.length() >= 2
                    && Math.abs(parentScale.optDouble(0,0)-1d)<.00001 && Math.abs(parentScale.optDouble(1,0)-1d)<.00001
                    && baseline != null && baseline.length() >= 2
                    && Math.abs(baseline.optDouble(0,0))<.00001 && Math.abs(baseline.optDouble(1,0))<.00001;
                movement=new Movement(move.optJSONObject("content_image").optInt("path_id", -1),
                    move.optInt("ease_value", -1), vector(a), vector(b),
                    (float)move.optDouble("duration_seconds", 0), (float)move.optDouble("before_delay_seconds", 0),
                    geometryCompatible);
            }
            JSONArray sourceLayers=sign.optJSONArray("layers_back_to_front");
            if (sourceLayers == null) throw new IllegalArgumentException("Missing sign layers: " + sign.optString("name"));
            List<Layer> layers=new ArrayList<>();
            for (int j=0; j<sourceLayers.length(); j++) {
                JSONObject source=sourceLayers.getJSONObject(j);
                int imageId=source.getInt("image_id");
                JSONObject uiItem=uiById.get(imageId);
                if (uiItem == null || !"UnityEngine.UI.Image".equals(uiItem.optString("class")))
                    throw new IllegalArgumentException("Sign layer is not a source Image component: " + imageId);
                JSONObject rectTransform=uiItem.optJSONObject("rect_transform");
                JSONArray rawRect=rectTransform == null ? null : rectTransform.optJSONArray("screen_rect_1920x1080");
                if (rawRect == null || rawRect.length() < 4)
                    throw new IllegalArgumentException("Source Image has no screen rectangle: " + imageId);
                JSONObject image=uiItem.optJSONObject("image");
                JSONObject sprite=source.optJSONObject("source_image");
                int sourceFile=sprite == null ? -1 : sprite.optInt("file_id", -1);
                int sourcePath=sprite == null ? -1 : sprite.optInt("path_id", -1);
                float left=(float)rawRect.optDouble(0,0), top=(float)rawRect.optDouble(1,0);
                float right=left+(float)rawRect.optDouble(2,0), bottom=top+(float)rawRect.optDouble(3,0);
                JSONArray rect=source.optJSONArray("screen_rect_1920x1080");
                if (rect == null || rect.length() < 4) throw new IllegalArgumentException("Missing exported source rect: " + imageId);
                for (int k=0; k<4; k++) if (Math.abs(rect.optDouble(k,0)-rawRect.optDouble(k,0)) > .02)
                    throw new IllegalArgumentException("Source rect mismatch for Image " + imageId);
                Movement layerMovement=movement != null && imageId == movement.contentImageId ? movement : null;
                layers.add(new Layer(imageId, sourceFile, sourcePath, source.optInt("mask_image_id", -1),
                    source.optString("role", "static"), uiItem.optString("asset", ""),
                    new float[]{left,top,right,bottom}, image != null && image.optBoolean("preserve_aspect", false), layerMovement));
            }
            JSONArray sourceBounds=sign.optJSONArray("bounds");
            float[] bounds=sourceBounds == null ? new float[]{0,0,0,0} : new float[]{
                (float)sourceBounds.optDouble(0,0), (float)sourceBounds.optDouble(1,0),
                (float)(sourceBounds.optDouble(0,0)+sourceBounds.optDouble(2,0)),
                (float)(sourceBounds.optDouble(1,0)+sourceBounds.optDouble(3,0))};
            if (result.put(signId, new View(signId, sign.optString("name"), bounds, layers, movement,
                    hidePlate, sign.optBoolean("hide_dialogue_text", false))) != null)
                throw new IllegalArgumentException("Duplicate sign enum: " + signId);
        }
        for (int id=EYE; id<=EAR; id++) if (!result.containsKey(id))
            throw new IllegalArgumentException("Missing sign enum: " + id);
        return new SignLayout(result);
    }

    View view(int sign) { return views.get(sign); }
    View view(String name) {
        if (name == null) return null;
        for (View view : views.values()) if (view.name.equalsIgnoreCase(name)) return view;
        return null;
    }

    private static float[] vector(JSONArray values) {
        return new float[]{(float)values.optDouble(0,0),(float)values.optDouble(1,0),(float)values.optDouble(2,0)};
    }
}
