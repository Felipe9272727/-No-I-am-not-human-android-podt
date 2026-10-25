package org.reconstruction.current;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;

/** Fixture represents the public Android tombstone schema, including unrelated fields. */
public final class TombstoneSummaryTest {
    private static byte[] varint(long value) {
        ByteArrayOutputStream out=new ByteArrayOutputStream();
        do { int part=(int)(value&127);value>>>=7;out.write(part|(value==0?0:128)); } while(value!=0);
        return out.toByteArray();
    }
    private static byte[] join(byte[]... parts) {
        ByteArrayOutputStream out=new ByteArrayOutputStream();
        for(byte[] part:parts)out.write(part,0,part.length);
        return out.toByteArray();
    }
    private static byte[] number(int field,long value) {return join(varint(field*8),varint(value));}
    private static byte[] message(int field,byte[] value) {return join(varint(field*8+2),varint(value.length),value);}
    private static byte[] string(int field,String value) {return message(field,value.getBytes(StandardCharsets.UTF_8));}
    private static void require(boolean condition,String detail) {if(!condition)throw new AssertionError(detail);}
    public static void main(String[] args) {
        byte[] frame=join(number(1,0x12ab),string(4,"glDrawElements"),number(5,16),string(6,"/vendor/lib64/egl/libGLESv2_adreno.so"),string(8,"build123"));
        byte[] target=join(number(1,4321),string(2,"GLThread 7"),message(4,frame));
        byte[] unrelated=join(number(1,1234),string(2,"main"),message(4,string(6,"unrelated.so")));
        byte[] fixture=join(number(6,4321),message(10,join(number(1,11),string(2,"SIGSEGV"),string(4,"SEGV_MAPERR"),number(9,0xdeadbeefL))),
            string(14,"example abort"),message(15,string(1,"example cause")),
            message(16,join(number(1,1234),message(2,unrelated))),message(16,join(number(1,4321),message(2,target))),string(999,"unknown field"));
        String result=TombstoneSummary.read(fixture);
        require(result.contains("SIGSEGV SEGV_MAPERR address=0xdeadbeef"),result);
        require(result.contains("Thread 4321: GLThread 7"),result);
        require(result.contains("#0 pc 12ab /vendor/lib64/egl/libGLESv2_adreno.so glDrawElements+16 build=build123"),result);
        require(result.contains("example cause")&&!result.contains("unrelated.so"),result);
        for(byte[] malformed:new byte[][]{{0},{(byte)128},{10,127},{11},{10,(byte)255,(byte)255,(byte)255,(byte)255,127}})
            require(TombstoneSummary.read(malformed).contains("unavailable or truncated"),"malformed message escaped bounds");
        System.out.println("Tombstone summary: signal, crashing-thread selection, backtrace, unknown fields and malformed input passed");
    }
}
