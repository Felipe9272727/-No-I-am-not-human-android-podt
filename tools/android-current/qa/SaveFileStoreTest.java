package org.reconstruction.current;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.json.JSONObject;

/** Host filesystem fault cases; native schema/VM roundtrips have separate C++ tests. */
public final class SaveFileStoreTest {
    private static void require(boolean condition,String message) {
        if(!condition)throw new AssertionError(message);
    }
    public static void main(String[] args) throws Exception {
        Path root=Files.createTempDirectory("ninah-save-qa-");
        try {
            File folder=root.resolve("saves").toFile();SaveFileStore store=new SaveFileStore(folder);
            require(!store.exists()&&store.candidates().isEmpty(),"fresh install has no slot");
            String first="{\"schema\":1,\"day\":0,\"line\":\"Olá gato 🐈\"}";
            String transport=NativeJson.ascii(first);
            require(transport.chars().allMatch(c->c>0&&c<128),"JNI JSON transport is ASCII");
            require(new JSONObject(transport).getString("line").equals("Olá gato 🐈"),"JNI escapes preserve surrogate pairs and accents");
            String second="{\"schema\":1,\"day\":1,\"pending\":true}";
            store.write(first);
            SaveFileStore restarted=new SaveFileStore(folder);
            require(restarted.candidates().size()==1&&restarted.candidates().get(0).payload.equals(first),"fresh process reads UTF-8 payload");
            restarted.write(second);
            List<SaveFileStore.Candidate> entries=new SaveFileStore(folder).candidates();
            require(entries.size()==2&&entries.get(0).payload.equals(second)&&!entries.get(0).fromBackup,"newest is first");
            require(entries.get(1).payload.equals(first)&&entries.get(1).fromBackup,"previous good file preserved");
            // Native schema validation may reject a file whose transport checksum is valid.
            restarted.accepted(entries.get(1));restarted.write(second);
            require(restarted.candidates().get(1).payload.equals(first),"native-rejected primary cannot overwrite accepted backup");
            Path main=folder.toPath().resolve("campaign-v1.json"),backup=folder.toPath().resolve("campaign-v1.bak");
            // Simulate a killed writer; incomplete .tmp is never offered to the native importer.
            Files.write(folder.toPath().resolve("campaign-v1.tmp"),"{broken".getBytes(StandardCharsets.UTF_8));
            require(new SaveFileStore(folder).candidates().get(0).payload.equals(second),"orphan temporary ignored");
            byte[] good=Files.readAllBytes(main);
            String tampered=new String(good,StandardCharsets.UTF_8).replace("pending","tampered");
            Files.write(main,tampered.getBytes(StandardCharsets.UTF_8));
            entries=new SaveFileStore(folder).candidates();
            require(entries.size()==1&&entries.get(0).payload.equals(first)&&entries.get(0).fromBackup,"checksum mismatch recovers backup");
            store.write(second);
            require(new SaveFileStore(folder).candidates().size()==2,"save after recovery keeps good backup");
            require(new SaveFileStore(folder).candidates().get(1).payload.equals(first),"invalid primary cannot replace good backup");
            Files.delete(main); // Crash between primary->backup and temporary->primary.
            require(new SaveFileStore(folder).candidates().get(0).payload.equals(first),"rename interruption recovers committed backup");
            store.write(second);good=Files.readAllBytes(main);
            boolean rejected=false;try{store.write("{truncated");}catch(Exception expected){rejected=true;}
            require(rejected&&java.util.Arrays.equals(good,Files.readAllBytes(main)),"bad payload leaves committed file untouched");
            rejected=false;try{store.write("x".repeat(SaveFileStore.MAX_BYTES));}catch(Exception expected){rejected=true;}
            require(rejected&&java.util.Arrays.equals(good,Files.readAllBytes(main)),"oversized payload leaves committed file untouched");
            Files.delete(backup);Files.createDirectory(backup);Files.write(backup.resolve("blocker"),new byte[]{1});
            rejected=false;try{store.write(first);}catch(Exception expected){rejected=true;}
            require(rejected&&java.util.Arrays.equals(good,Files.readAllBytes(main)),"failed backup replacement preserves committed primary");
            Files.delete(backup.resolve("blocker"));Files.delete(backup);
            Files.write(main,new byte[]{'{'});Files.write(backup,new byte[]{'{'});
            require(store.exists()&&store.candidates().isEmpty(),"corrupt slots remain in place for recovery");
            System.out.println("SaveFileStoreTest: fresh process, UTF-8, synced replacement, checksum, backup, interrupted-write and size-limit checks passed");
        } finally {
            try(java.util.stream.Stream<Path> paths=Files.walk(root)) {
                paths.sorted(java.util.Comparator.reverseOrder()).forEach(path->{try{Files.delete(path);}catch(Exception ignored){}});
            }
        }
    }
}
