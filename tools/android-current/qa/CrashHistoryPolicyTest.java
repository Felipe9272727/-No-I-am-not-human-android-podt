package org.reconstruction.current;

public final class CrashHistoryPolicyTest {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    public static void main(String[] args) {
        long old = 1792938886685L;
        check(!CrashHistoryPolicy.shouldNotify(old,old+60000,0,"old",""));
        check(CrashHistoryPolicy.shouldNotify(old+120000,old+60000,old,"new","old"));
        check(!CrashHistoryPolicy.shouldNotify(old+120000,old+60000,old+120000,"new","new"));
        check(!CrashHistoryPolicy.shouldNotify(old,old-1,old+100,"old","new"));
        check(!CrashHistoryPolicy.shouldNotify(0,0,0,"",""));
        check(CrashHistoryPolicy.matchesJavaCapture(old,true,old+5000));
        check(!CrashHistoryPolicy.matchesJavaCapture(old,false,old+5000));
        check(!CrashHistoryPolicy.matchesJavaCapture(old,true,old+20000));
        check(!CrashHistoryPolicy.matchesJavaCapture(old,true,0));
        System.out.println("CrashHistoryPolicyTest passed");
    }
}
