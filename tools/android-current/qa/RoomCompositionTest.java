package org.reconstruction.current;

import org.json.JSONObject;
import java.nio.file.Files;
import java.nio.file.Path;

/** Regression: rooms keep source order and do not reveal roster-controlled cards. */
public final class RoomCompositionTest {
    public static void main(String[] args) throws Exception {
        Path root = Path.of("reconstruction/android-current/app/src/main/assets");
        JSONObject presentation = new JSONObject(Files.readString(root.resolve("presentation/assets.json")));
        RoomComposition composition = RoomComposition.parse(new JSONObject(Files.readString(root.resolve(presentation.getString("room_layers_manifest")))));
        for (int room = 0; room < 7; room++) {
            RoomComposition.Scene scene = composition.room(room);
            if (scene == null || scene.layers.isEmpty()) throw new AssertionError("Missing authored room " + room);
            int previous = -1;
            for (RoomComposition.Layer layer : scene.layers) {
                if (layer.order < previous) throw new AssertionError("Unsorted room " + room);
                if (!Files.isRegularFile(root.resolve(layer.asset))) throw new AssertionError("Missing room sprite " + layer.asset);
                previous = layer.order;
            }
        }
        // Entry sky is authored behind the transparent porch, not a single flattened background.
        RoomComposition.Scene entrance = composition.room(5);
        if (entrance.layers.size() < 2) throw new AssertionError("Entry sky/porch layers were lost");
        if (composition.room(7) != null) throw new AssertionError("Invented eighth room");
        if (composition.room(0).actorOrder(-1) != Integer.MAX_VALUE) throw new AssertionError("Unknown roster slot");
        RoomComposition invalid = RoomComposition.parse(new JSONObject("{\"schema_version\":1,\"rooms\":[{\"id\":0,\"layers\":[{\"asset\":\"../outside.png\",\"rect\":[0,0,1,1]}]}]}"));
        if (invalid.room(0) != null) throw new AssertionError("Unsafe room sprite path accepted");
        System.out.println("RoomCompositionTest passed: seven authored room views; source ordering, assets and path validation");
    }
}
