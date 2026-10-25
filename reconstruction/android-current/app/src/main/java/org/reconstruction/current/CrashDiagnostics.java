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
                String report = header(app) + "\nStage: " + stage + "\nThread: " + thread.getName() + "\n" + stack;
                write(app, report);
            } catch (Throwable ignored) { }
            if (original != null) original.uncaughtException(thread, failure);
            else android.os.Process.killProcess(android.os.Process.myPid());
        });
    }

    static void stage(Context context, String value) {
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

    static String previous(Context app) {
        String report = "";
        try (InputStream input = app.openFileInput(FILE); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096]; int count;
            while (output.size() < LIMIT && (count = input.read(buffer)) != -1)
                output.write(buffer, 0, Math.min(count, LIMIT - output.size()));
            report = new String(output.toByteArray(), StandardCharsets.UTF_8);
        } catch (Exception ignored) { }
        if (Build.VERSION.SDK_INT >= 30) {
            try {
                ActivityManager manager = (ActivityManager) app.getSystemService(Context.ACTIVITY_SERVICE);
                List<ApplicationExitInfo> exits = manager.getHistoricalProcessExitReasons(null, 0, 5);
                for (ApplicationExitInfo exit : exits) {
                    int reason = exit.getReason();
                    if (reason != ApplicationExitInfo.REASON_CRASH && reason != ApplicationExitInfo.REASON_CRASH_NATIVE &&
                        reason != ApplicationExitInfo.REASON_ANR && reason != ApplicationExitInfo.REASON_LOW_MEMORY &&
                        reason != ApplicationExitInfo.REASON_SIGNALED) continue;
                    String description = "\nPrevious Android exit at " + exit.getTimestamp() + ": reason=" + reason +
                        " status=" + exit.getStatus() + "\n" + exit.getDescription() +
                        "\nPSS/RSS KiB: " + exit.getPss() + "/" + exit.getRss();
                    byte[] summary = exit.getProcessStateSummary();
                    if (summary != null) description += "\nLast stage: " + new String(summary, StandardCharsets.UTF_8);
                    if (Build.VERSION.SDK_INT >= 31 && reason == ApplicationExitInfo.REASON_CRASH_NATIVE) {
                        try (InputStream trace=exit.getTraceInputStream(); ByteArrayOutputStream output=new ByteArrayOutputStream()) {
                            if (trace != null) {
                                byte[] buffer=new byte[8192]; int count;
                                while (output.size()<4*1024*1024 && (count=trace.read(buffer))!=-1)
                                    output.write(buffer,0,Math.min(count,4*1024*1024-output.size()));
                                description += TombstoneSummary.read(output.toByteArray());
                            }
                        } catch (Exception unavailable) { description += "\nNative trace unavailable."; }
                    }
                    report = (report.isEmpty() ? header(app) : report) + description;
                    break;
                }
            } catch (RuntimeException ignored) { }
        }
        return report;
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
