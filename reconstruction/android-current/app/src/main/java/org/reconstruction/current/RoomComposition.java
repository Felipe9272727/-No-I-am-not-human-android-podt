package org.reconstruction.current;

import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Authored canvas layers, independent of the native roster and campaign state. */
final class RoomComposition {
    private final Map<Integer, Scene> rooms = new HashMap<>();

    static RoomComposition parse(JSONObject manifest) {
        RoomComposition result = new RoomComposition();
        if (manifest == null || manifest.optInt("schema_version") != 1) return result;
        JSONArray rows = manifest.optJSONArray("rooms");
        if (rows == null) return result;
        for (int i = 0; i < rows.length(); i++) {
            JSONObject row = rows.optJSONObject(i);
            if (row == null) continue;
            int id = row.optInt("id", -1);
            if (id < 0 || id > 6 || result.rooms.containsKey(id)) continue;
            Scene scene = new Scene();
            JSONArray layers = row.optJSONArray("layers");
            if (layers != null) for (int j = 0; j < layers.length(); j++) {
                JSONObject layer = layers.optJSONObject(j);
                if (layer == null) continue;
                String asset = layer.optString("asset");
                JSONArray rect = layer.optJSONArray("rect");
                if (asset.isEmpty() || asset.startsWith("/") || asset.contains("..") || rect == null || rect.length() != 4) continue;
                float x = number(rect, 0, Float.NaN), y = number(rect, 1, Float.NaN);
                float w = number(rect, 2, Float.NaN), h = number(rect, 3, Float.NaN);
                if (!finite(x) || !finite(y) || !finite(w) || !finite(h) || w <= 0 || h <= 0) continue;
                JSONArray color = layer.optJSONArray("color");
                scene.layers.add(new Layer(asset, x, y, w, h, layer.optInt("draw_order", j),
                        channel(color, 0), channel(color, 1), channel(color, 2), channel(color, 3),
                        layer.optBoolean("preserve_aspect", true)));
            }
            Collections.sort(scene.layers, new Comparator<Layer>() {
                @Override public int compare(Layer a, Layer b) { return Integer.compare(a.order, b.order); }
            });
            JSONArray orders = row.optJSONArray("character_orders");
            if (orders != null) for (int j = 0; j < orders.length(); j++) {
                JSONObject order = orders.optJSONObject(j);
                if (order != null && order.optInt("character_order", -1) >= 0)
                    scene.actorOrders.put(order.optInt("character_order"), order.optInt("draw_order"));
            }
            if (!scene.layers.isEmpty()) result.rooms.put(id, scene);
        }
        return result;
    }

    Scene room(int id) { return rooms.get(id); }

    private static float number(JSONArray values, int index, float fallback) {
        return values == null ? fallback : (float)values.optDouble(index, fallback);
    }
    private static float channel(JSONArray values, int index) {
        float value = number(values, index, 1f);
        return finite(value) ? Math.max(0f, Math.min(1f, value)) : 1f;
    }
    private static boolean finite(float value) { return !Float.isNaN(value) && !Float.isInfinite(value); }

    static final class Scene {
        final List<Layer> layers = new ArrayList<>();
        final Map<Integer, Integer> actorOrders = new HashMap<>();
        int actorOrder(int sourceOrder) {
            Integer order = actorOrders.get(sourceOrder);
            return order == null ? Integer.MAX_VALUE : order;
        }
    }

    static final class Layer {
        final String asset;
        final float x, top, width, height, r, g, b, a;
        final int order;
        final boolean preserveAspect;
        Layer(String asset, float x, float top, float width, float height, int order,
                float r, float g, float b, float a, boolean preserveAspect) {
            this.asset = asset; this.x = x; this.top = top; this.width = width; this.height = height;
            this.order = order; this.r = r; this.g = g; this.b = b; this.a = a;
            this.preserveAspect = preserveAspect;
        }
    }
}
