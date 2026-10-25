package org.reconstruction.current;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/** Reads only the crashing thread, signal and cause from Android's tombstone protobuf.
 * Field numbers: https://android.googlesource.com/platform/system/core/+/refs/heads/main/debuggerd/proto/tombstone.proto
 * Does not include register/memory dumps, file descriptors or other app logs. */
final class TombstoneSummary {
    static String read(byte[] bytes) {
        try {
            Message root = new Message(bytes, 0, bytes.length);
            long tid = root.number(6);
            StringBuilder text = new StringBuilder("\nNative crash:\n");
            Message signal = root.first(10);
            if (signal != null) text.append(signal.string(2)).append(" ").append(signal.string(4))
                .append(" address=0x").append(Long.toHexString(signal.number(9))).append('\n');
            String abort = root.string(14);
            if (!abort.isEmpty()) text.append("Abort: ").append(abort).append('\n');
            for (Message cause : root.children(15)) text.append("Cause: ").append(cause.string(1)).append('\n');
            for (Message entry : root.children(16)) {
                if (entry.number(1) != tid) continue;
                Message thread = entry.first(2);
                if (thread == null) break;
                text.append("Thread ").append(tid).append(": ").append(thread.string(2)).append('\n');
                int index = 0;
                for (Message frame : thread.children(4)) {
                    text.append('#').append(index++).append(" pc ").append(Long.toHexString(frame.number(1)))
                        .append(' ').append(frame.string(6)).append(' ').append(frame.string(4))
                        .append('+').append(frame.number(5)).append(" build=").append(frame.string(8)).append('\n');
                    if (index >= 48) break;
                }
                break;
            }
            return text.toString();
        } catch (IllegalArgumentException invalid) {
            return "\nNative trace was unavailable or truncated.\n";
        }
    }

    private static final class Message {
        final byte[] data; final int start, end;
        Message(byte[] data, int start, int end) { this.data=data; this.start=start; this.end=end; }
        long number(int field) {
            Reader reader = new Reader(this);
            while (reader.next()) if (reader.field == field && reader.wire == 0) return reader.value;
            return 0;
        }
        String string(int field) {
            Message value = first(field);
            if (value == null) return "";
            int size = Math.min(2048, value.end-value.start);
            return new String(data, value.start, size, StandardCharsets.UTF_8).replace('\0','?');
        }
        Message first(int field) {
            Reader reader = new Reader(this);
            while (reader.next()) if (reader.field == field && reader.wire == 2)
                return new Message(data, reader.begin, reader.limit);
            return null;
        }
        List<Message> children(int field) {
            List<Message> values = new ArrayList<>(); Reader reader = new Reader(this);
            while (reader.next()) if (reader.field == field && reader.wire == 2) {
                values.add(new Message(data, reader.begin, reader.limit));
                if (values.size() >= 256) break;
            }
            return values;
        }
    }

    private static final class Reader {
        final Message message; int pos, field, wire, begin, limit, count; long value;
        Reader(Message message) { this.message=message; pos=message.start; }
        long varint() {
            long value=0;
            for (int shift=0;shift<64;shift+=7) {
                if (pos>=message.end) throw new IllegalArgumentException("truncated varint");
                int b=message.data[pos++]&255;
                if (shift==63 && (b&254)!=0) throw new IllegalArgumentException("varint overflow");
                value|=(long)(b&127)<<shift;
                if ((b&128)==0) return value;
            }
            throw new IllegalArgumentException("varint overflow");
        }
        boolean next() {
            if (pos==message.end) return false;
            if (++count>100000) throw new IllegalArgumentException("too many fields");
            long tag=varint(); field=(int)(tag>>>3); wire=(int)(tag&7);
            if (field<=0) throw new IllegalArgumentException("invalid field");
            begin=pos; value=0;
            if (wire==0) value=varint();
            else if (wire==1) skip(8);
            else if (wire==5) skip(4);
            else if (wire==2) { long size=varint(); begin=pos; if (size<0 || size>message.end-pos) throw new IllegalArgumentException("truncated message"); skip((int)size); }
            else throw new IllegalArgumentException("unsupported wire type");
            limit=pos; return true;
        }
        void skip(int size) { if (size>message.end-pos) throw new IllegalArgumentException("truncated field"); pos+=size; }
    }
}
