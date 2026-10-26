package org.reconstruction.current;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

/** One private campaign slot, with a synced replacement and the previous good file.
 * The native host owns the snapshot schema and validation. No world/media data is stored here.
 * Called only on the activity's single native worker, never on the render/UI thread.
 */
final class SaveFileStore {
    static final int MAX_BYTES = 4 * 1024 * 1024;
    private final File main, backup, temporary;
    private boolean preserveBackup;

    static final class Candidate {
        final String payload;
        final boolean fromBackup;
        Candidate(String payload, boolean fromBackup) { this.payload=payload; this.fromBackup=fromBackup; }
    }

    SaveFileStore(File directory) {
        main=new File(directory,"campaign-v1.json");
        backup=new File(directory,"campaign-v1.bak");
        temporary=new File(directory,"campaign-v1.tmp");
    }

    boolean exists() { return main.exists() || backup.exists(); }

    void accepted(Candidate candidate) { preserveBackup=candidate.fromBackup; }

    List<Candidate> candidates() {
        List<Candidate> result=new ArrayList<>();
        for (File file : new File[]{main,backup}) {
            try { result.add(new Candidate(read(file),file.equals(backup))); }
            catch (Exception ignored) { /* Try the previous committed file, never an incomplete .tmp. */ }
        }
        return result;
    }

    void write(String payload) throws Exception {
        byte[] payloadBytes=payload.getBytes(StandardCharsets.UTF_8);
        if(payloadBytes.length==0 || payloadBytes.length>MAX_BYTES/2)
            throw new IOException("Estado salvo excede o limite permitido");
        new JSONObject(payload); // Reject truncated/non-object data before touching either committed file.
        JSONObject envelope=new JSONObject();
        envelope.put("format","ninah-android-save"); envelope.put("version",1);
        envelope.put("payload",payload); envelope.put("sha256",digest(payloadBytes));
        byte[] bytes=envelope.toString().getBytes(StandardCharsets.UTF_8);
        if(bytes.length>MAX_BYTES) throw new IOException("Arquivo salvo excede o limite permitido");
        File directory=main.getParentFile();
        if(!directory.isDirectory() && !directory.mkdirs()) throw new IOException("Pasta de saves indisponível");
        try {
            try(FileOutputStream output=new FileOutputStream(temporary)) {
                output.write(bytes); output.flush(); output.getFD().sync();
            }
            boolean goodMain=false;
            try { read(main); goodMain=!preserveBackup; } catch(Exception ignored) { }
            if(goodMain) {
                if(backup.exists() && !backup.delete()) throw new IOException("Não foi possível atualizar a cópia anterior");
                if(!main.renameTo(backup)) throw new IOException("Não foi possível preservar o save anterior");
            } else if(main.exists() && !main.delete()) {
                throw new IOException("Não foi possível substituir o save inválido");
            }
            if(!temporary.renameTo(main)) {
                // The backup remains readable even if restoring its original name fails.
                if(!main.exists() && backup.exists()) backup.renameTo(main);
                throw new IOException("Não foi possível concluir a gravação do save");
            }
            preserveBackup=false;
        } finally {
            if(temporary.exists()) temporary.delete();
        }
    }

    private static String read(File file) throws Exception {
        long length=file.length();
        if(!file.isFile() || length<=0 || length>MAX_BYTES) throw new IOException("Save ausente ou inválido");
        byte[] bytes;
        try(FileInputStream input=new FileInputStream(file);ByteArrayOutputStream output=new ByteArrayOutputStream()) {
            byte[] buffer=new byte[8192];int count,total=0;
            while((count=input.read(buffer))!=-1) {
                total+=count;if(total>MAX_BYTES)throw new IOException("Save excede o limite permitido");
                output.write(buffer,0,count);
            }
            bytes=output.toByteArray();
        }
        JSONObject envelope=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
        if(!"ninah-android-save".equals(envelope.get("format")) ||
           !(envelope.get("version") instanceof Integer) || envelope.getInt("version")!=1 ||
           !(envelope.get("payload") instanceof String) || !(envelope.get("sha256") instanceof String))
            throw new IOException("Formato de save incompatível");
        String payload=envelope.getString("payload");
        if(payload.getBytes(StandardCharsets.UTF_8).length>MAX_BYTES/2 ||
           !digest(payload.getBytes(StandardCharsets.UTF_8)).equals(envelope.getString("sha256")))
            throw new IOException("Save incompleto ou corrompido");
        new JSONObject(payload);
        return payload;
    }

    private static String digest(byte[] bytes) throws Exception {
        StringBuilder hex=new StringBuilder(64);
        for(byte value:MessageDigest.getInstance("SHA-256").digest(bytes)) {
            hex.append(Character.forDigit((value&255)>>>4,16));hex.append(Character.forDigit(value&15,16));
        }
        return hex.toString();
    }
}
