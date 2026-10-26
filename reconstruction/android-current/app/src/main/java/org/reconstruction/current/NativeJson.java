package org.reconstruction.current;

/** JNI uses modified UTF-8. Send JSON as ASCII escapes so UTF-16 surrogate pairs
 * and embedded nulls reach the C++ JSON parser without an encoding conversion loss.
 */
final class NativeJson {
    static String ascii(String json) {
        StringBuilder result=null;
        for(int i=0;i<json.length();i++) {
            char c=json.charAt(i);
            if(c>127 || c==0) {
                if(result==null){result=new StringBuilder(json.length()+16);result.append(json,0,i);}
                result.append("\\u");
                for(int shift=12;shift>=0;shift-=4)result.append(Character.forDigit((c>>>shift)&15,16));
            } else if(result!=null) result.append(c);
        }
        return result==null?json:result.toString();
    }
}
