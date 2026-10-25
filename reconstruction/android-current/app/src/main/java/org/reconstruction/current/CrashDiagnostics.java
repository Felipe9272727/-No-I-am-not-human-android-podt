package org.reconstruction.current;

import android.app.ActivityManager;
import android.app.ApplicationExitInfo;
import android.content.Context;
import android.os.Build;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;
import java.text.DateFormat;
import java.util.Date;
import android.content.SharedPreferences;

/** Private, bounded diagnostics. No network, permissions, or automatic sharing. */
final class CrashDiagnostics {
    private static final String FILE = "last-crash.txt";
    private static volatile String stage = "starting";
    private static boolean installed;
    private static final int LIMIT = 48000;

    static synchronized void install(Context context) {
        if (installed) return;
        installed = true;
        final Context app = context.getApplicationContext();
        final Thread.UncaughtExceptionHandler original = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, failure) -> {
            try {
                StringWriter stack = new StringWriter();
                failure.printStackTrace(new PrintWriter(stack));
                String report = header(app) + "\nCaptured at: " + System.currentTimeMillis() + "\nStage: " + stage + "\nThread: " + thread.getName() + "\n" + stack;
                write(app, report);
            } catch (Throwable ignored) { }
            if (original != null) original.uncaughtException(thread, failure);
            else android.os.Process.killProcess(android.os.Process.myPid());
        });
    }

    static void stage(Context context, String value) {
        if (value.equals(stage)) return;
        stage = value;
        if (Build.VERSION.SDK_INT >= 30) {
            try {
                ActivityManager manager = (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
                byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                manager.setProcessStateSummary(Arrays.copyOf(bytes, Math.min(128, bytes.length)));
            } catch (RuntimeException ignored) { }
        }
    }

    static String header(Context app) {
        String version = "unknown";
        try { version = app.getPackageManager().getPackageInfo(app.getPackageName(), 0).versionName; }
        catch (Exception ignored) { }
        return "NINAH Android preview " + version + "\nDevice: " + Build.MANUFACTURER + " " + Build.MODEL +
            "\nAndroid: " + Build.VERSION.RELEASE + " API " + Build.VERSION.SDK_INT +
            "\nABIs: " + Arrays.toString(Build.SUPPORTED_ABIS);
    }

    static final class History {
        final String text, id;
        final long timestamp;
        final boolean shouldNotify;
        History(String text, String id, long timestamp, boolean notify) {
            this.text=text; this.id=id; this.timestamp=timestamp; this.shouldNotify=notify;
        }
    }

    static History previous(Context app) {
        String captured="";
        long capturedAt=0;
        try (InputStream input=app.openFileInput(FILE); ByteArrayOutputStream output=new ByteArrayOutputStream()) {
            byte[] buffer=new byte[4096]; int count;
            while (output.size()<LIMIT && (count=input.read(buffer))!=-1)
                output.write(buffer,0,Math.min(count,LIMIT-output.size()));
            captured=new String(output.toByteArray(),StandardCharsets.UTF_8);
            capturedAt=app.getFileStreamPath(FILE).lastModified();
        } catch (Exception ignored) { }
        String report=captured, eventId=captured.isEmpty()?"":"java:"+digest(captured);
        long eventTime=capturedAt;
        if (Build.VERSION.SDK_INT>=30) {
            try {
                ActivityManager manager=(ActivityManager)app.getSystemService(Context.ACTIVITY_SERVICE);
                List<ApplicationExitInfo> exits=manager.getHistoricalProcessExitReasons(null,0,10);
                ApplicationExitInfo latest=null;
                for (ApplicationExitInfo exit:exits) {
                    int reason=exit.getReason();
                    if (reason!=ApplicationExitInfo.REASON_CRASH && reason!=ApplicationExitInfo.REASON_CRASH_NATIVE &&
                        reason!=ApplicationExitInfo.REASON_ANR && reason!=ApplicationExitInfo.REASON_LOW_MEMORY &&
                        reason!=ApplicationExitInfo.REASON_SIGNALED) continue;
                    if (latest==null || exit.getTimestamp()>latest.getTimestamp()) latest=exit;
                }
                if (latest!=null && (latest.getTimestamp()>=capturedAt ||
                    CrashHistoryPolicy.matchesJavaCapture(latest.getTimestamp(),latest.getReason()==ApplicationExitInfo.REASON_CRASH,capturedAt))) {
                    int reason=latest.getReason();
                    eventTime=latest.getTimestamp();
                    eventId="android:"+eventTime+":"+reason+":"+latest.getStatus();
                    report="Registro histórico do Android (não é um erro da sessão atual)"+
                        "\nData: "+DateFormat.getDateTimeInstance().format(new Date(eventTime))+
                        "\nTimestamp: "+eventTime+" reason="+reason+" status="+latest.getStatus()+
                        "\n"+latest.getDescription()+"\nPSS/RSS KiB: "+latest.getPss()+"/"+latest.getRss();
                    byte[] summary=latest.getProcessStateSummary();
                    if (summary!=null) report+="\nÚltima etapa registrada: "+new String(summary,StandardCharsets.UTF_8);
                    if (CrashHistoryPolicy.matchesJavaCapture(eventTime,reason==ApplicationExitInfo.REASON_CRASH,capturedAt))
                        report+="\n\nCaptura Java da mesma execução:\n"+captured;
                    if (Build.VERSION.SDK_INT>=31 && reason==ApplicationExitInfo.REASON_CRASH_NATIVE) {
                        try (InputStream trace=latest.getTraceInputStream(); ByteArrayOutputStream output=new ByteArrayOutputStream()) {
                            if (trace!=null) {
                                byte[] buffer=new byte[8192]; int count;
                                while (output.size()<4*1024*1024 && (count=trace.read(buffer))!=-1)
                                    output.write(buffer,0,Math.min(count,4*1024*1024-output.size()));
                                report+=TombstoneSummary.read(output.toByteArray());
                            }
                        } catch (Exception unavailable) { report+="\nNative trace unavailable."; }
                    }
                }
            } catch (RuntimeException ignored) { }
        }
        long installedAt=Long.MAX_VALUE;
        try { installedAt=app.getPackageManager().getPackageInfo(app.getPackageName(),0).lastUpdateTime; }
        catch (Exception ignored) { }
        SharedPreferences notices=app.getSharedPreferences("crash-notices",Context.MODE_PRIVATE);
        return new History(report,eventId,eventTime,CrashHistoryPolicy.shouldNotify(eventTime,installedAt,
            notices.getLong("last-time",0),eventId,notices.getString("last-id","")));
    }

    static void markShown(Context app, History history) {
        app.getSharedPreferences("crash-notices",Context.MODE_PRIVATE).edit()
            .putLong("last-time",history.timestamp).putString("last-id",history.id).apply();
    }

    private static String digest(String value) {
        try {
            byte[] bytes=java.security.MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder result=new StringBuilder();
            for (byte part:bytes) result.append(String.format(java.util.Locale.ROOT,"%02x",part & 255));
            return result.toString();
        } catch (Exception unavailable) { return value; }
    }

    static void write(Context app, String report) throws java.io.IOException {
        String bounded = report.length() > LIMIT ? report.substring(0, LIMIT) + "\n[truncated]" : report;
        try (java.io.FileOutputStream output = app.openFileOutput(FILE, Context.MODE_PRIVATE)) {
            output.write(bounded.getBytes(StandardCharsets.UTF_8));
            output.flush();
            output.getFD().sync();
        }
    }
}
