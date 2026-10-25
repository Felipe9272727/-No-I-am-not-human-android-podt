package org.reconstruction.viewer;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/** Recovery prototype for browsing original assets and running recovered Yarn dialogue nodes. */
public final class MainActivity extends Activity {
    static { System.loadLibrary("recovery_viewer"); }

    private static final String[] LOCALES = {"Português (Brasil)", "English"};
    private static final String[] LOCALE_FILES = {
        "localization/portuguese_brazil_pt-br_.json", "localization/english_en_.json"
    };
    // This curated entry list opens real recovered nodes. Child branches are reached through
    // the original Yarn options instead of being presented as invented scene transitions.
    private static final String[] START_NODES = {
        "phone_neighbour_day2", "Neighbour_Asking_3", "tv_1_necessary",
        "Intro_1", "Intro_2", "Intro_3", "Intro_4", "Intro_5"
    };
    private static final String[] START_LABELS = {
        "Conversa com o vizinho · dia 2", "Conversa com o vizinho · trecho 3", "Notícia na TV",
        "Introdução · trecho 1", "Introdução · trecho 2", "Introdução · trecho 3",
        "Introdução · trecho 4", "Introdução · trecho 5"
    };
    private static final String[] IMAGES = {
        "Bathroom_background.png", "Bedroom_background.png", "Kitchen_background.png",
        "Livingroom1_background.png", "Livingroom2_background.png", "Utilityroom_background.png",
        "TV.png", "TV_1.png", "mainMenu_bg.png", "char1.png", "peepholeOverlay.png",
        "fake_bald_1_0.png", "fake_cold_1_0.png", "fake_cold_kill_0.png", "fake_doctor_1_0.png",
        "fake_esenin_1_0.png", "fake_rocker_1_0.png", "fake_tough_1_0.png", "fake_tourist_1_0.png",
        "fake_tv_ballet_0.png", "fake_tv_fire_0.png", "fake_tv_firstday_0.png", "fake_tv_noise_0.png",
        "fake_tv_weather1_0.png", "Fake_collection_window_film_0.png", "mainmenu_eyes_0.png",
        "mainmenu_light_0.png", "mainmenu_mask_0.png", "mainmenu_teeth_0.png"
    };

    private static native String nativeLoadCatalog(String sourceJson);
    private static native String nativeLoadProgram(String sourceJson);
    private static native String nativeCatalogPage(String table, int offset, int limit);
    private static native String nativeStartNode(String node);
    private static native String nativeAdvance();
    private static native String nativeSelectOption(int index);

    private final int ink = Color.rgb(235, 229, 214);
    private Spinner localeSpinner, sceneSpinner, tableSpinner;
    private LinearLayout body, optionsBox;
    private ImageView imageView;
    private TextView imageCaption, catalogStatus, dialogueText, dialogueStatus;
    private Button advanceButton;
    private String[] tables = new String[0];
    private int page = 0, imageIndex = 0;
    private volatile boolean ready = false;
    private boolean suppressSceneSelection = false, loadingLocale = false;
    private StringBuilder transcript = new StringBuilder();

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LOW_PROFILE);
        getWindow().getDecorView().setBackgroundColor(Color.rgb(22, 23, 26));

        ScrollView scroll = new ScrollView(this);
        body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(dp(18), dp(16), dp(18), dp(28));
        scroll.addView(body); setContentView(scroll);

        TextView title = text("NÃO, NÃO SOU UM HUMANO", 20, true); body.addView(title);
        TextView notice = text("Protótipo com trechos recuperados; o fluxo completo do jogo ainda não foi reconstruído.", 14, false);
        notice.setTextColor(Color.rgb(232, 173, 115)); body.addView(notice, gap(6));

        body.addView(text("Diálogo recuperado", 18, true), gap(18));
        localeSpinner = new Spinner(this); localeSpinner.setAdapter(adapter(LOCALES)); body.addView(localeSpinner);
        sceneSpinner = new Spinner(this); sceneSpinner.setAdapter(adapter(START_LABELS)); body.addView(sceneSpinner, gap(4));
        dialogueText = text("Carregando trechos recuperados…", 17, false);
        dialogueText.setPadding(dp(12), dp(12), dp(12), dp(12));
        dialogueText.setBackgroundColor(Color.rgb(34, 35, 39)); body.addView(dialogueText, gap(8));
        optionsBox = new LinearLayout(this); optionsBox.setOrientation(LinearLayout.VERTICAL); body.addView(optionsBox, gap(4));
        advanceButton = button("Continuar"); advanceButton.setVisibility(View.GONE);
        advanceButton.setOnClickListener(v -> renderEvent(nativeAdvance(), false)); body.addView(advanceButton, gap(4));
        dialogueStatus = text("Os comandos recuperados são exibidos como texto e não são executados.", 12, false);
        dialogueStatus.setTextColor(Color.rgb(170, 165, 155)); body.addView(dialogueStatus, gap(4));

        body.addView(text("Arte recuperada", 18, true), gap(22));
        imageCaption = text("", 13, false); body.addView(imageCaption);
        imageView = new ImageView(this); imageView.setAdjustViewBounds(true); imageView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        body.addView(imageView, new LinearLayout.LayoutParams(-1, dp(260)));
        LinearLayout imageNav = row();
        Button imagePrev = button("Imagem anterior"), imageNext = button("Próxima imagem");
        imagePrev.setOnClickListener(v -> showImage(-1)); imageNext.setOnClickListener(v -> showImage(1));
        imageNav.addView(imagePrev, weight()); imageNav.addView(imageNext, weight()); body.addView(imageNav, gap(4));
        showImage(0);

        body.addView(text("Catálogo de textos", 18, true), gap(22));
        tableSpinner = new Spinner(this); body.addView(tableSpinner);
        LinearLayout pageNav = row();
        Button prev = button("Página anterior"), next = button("Próxima página");
        prev.setOnClickListener(v -> { page = Math.max(0, page - 1); renderPage(); });
        next.setOnClickListener(v -> { page++; renderPage(); });
        pageNav.addView(prev, weight()); pageNav.addView(next, weight()); body.addView(pageNav, gap(4));
        catalogStatus = text("Carregando textos recuperados…", 13, false); body.addView(catalogStatus, gap(6));

        tableSpinner.setOnItemSelectedListener(new SimpleSelect(() -> { page = 0; renderPage(); }));
        localeSpinner.setOnItemSelectedListener(new SimpleSelect(() -> {
            if (ready && !loadingLocale) loadLocale(localeSpinner.getSelectedItemPosition());
        }));
        sceneSpinner.setOnItemSelectedListener(new SimpleSelect(() -> {
            if (ready && !suppressSceneSelection) startSelectedNode();
        }));
        bootRuntime();
    }

    private void bootRuntime() {
        new Thread(() -> {
            try {
                String locale = readAsset(LOCALE_FILES[0]);
                JSONArray names = new JSONArray(nativeLoadCatalog(locale));
                JSONObject loaded = new JSONObject(nativeLoadProgram(readAsset("narrative/program.json")));
                if (!loaded.optBoolean("ok", false)) throw new IllegalStateException("program load failed");
                runOnUiThread(() -> {
                    tables = jsonStrings(names); tableSpinner.setAdapter(adapter(tables));
                    suppressSceneSelection = true; sceneSpinner.setSelection(0); suppressSceneSelection = false;
                    ready = true; renderPage(); startSelectedNode();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    dialogueText.setText("Não foi possível carregar os trechos recuperados.");
                    dialogueStatus.setText("O catálogo de imagens continua disponível.");
                    catalogStatus.setText("Catálogo indisponível.");
                });
            }
        }, "recovery-viewer-load").start();
    }

    private void loadLocale(int index) {
        if (index < 0 || index >= LOCALE_FILES.length) return;
        loadingLocale = true;
        dialogueStatus.setText("Carregando idioma…");
        new Thread(() -> {
            try {
                JSONArray names = new JSONArray(nativeLoadCatalog(readAsset(LOCALE_FILES[index])));
                runOnUiThread(() -> {
                    tables = jsonStrings(names); tableSpinner.setAdapter(adapter(tables)); page = 0;
                    loadingLocale = false; startSelectedNode();
                });
            } catch (Exception e) {
                runOnUiThread(() -> { loadingLocale = false; dialogueStatus.setText("Não foi possível carregar este idioma."); });
            }
        }, "recovery-viewer-locale").start();
    }

    private String[] jsonStrings(JSONArray values) {
        String[] result = new String[values.length()];
        for (int i = 0; i < values.length(); i++) result[i] = values.optString(i);
        return result;
    }

    private void startSelectedNode() {
        int index = Math.max(0, sceneSpinner.getSelectedItemPosition());
        transcript = new StringBuilder();
        dialogueStatus.setText("Trecho recuperado: " + START_LABELS[index]);
        renderEvent(nativeStartNode(START_NODES[index]), true);
    }

    private void renderEvent(String raw, boolean clear) {
        if (clear) transcript.setLength(0);
        try {
            JSONObject event = new JSONObject(raw); String type = event.optString("type", "error");
            optionsBox.removeAllViews();
            if (type.equals("line")) {
                appendTranscript(event.optString("text", ""));
                advanceButton.setText("Continuar"); advanceButton.setVisibility(View.VISIBLE);
                dialogueStatus.setText("Toque em continuar para avançar no trecho recuperado.");
            } else if (type.equals("options")) {
                JSONArray choices = event.optJSONArray("options");
                advanceButton.setVisibility(View.GONE);
                if (choices == null || choices.length() == 0) {
                    dialogueStatus.setText("Este trecho não contém opções recuperadas."); return;
                }
                for (int i = 0; i < choices.length(); i++) {
                    final int choiceIndex = i; JSONObject choice = choices.getJSONObject(i);
                    Button option = button(choice.optString("text", "Opção"));
                    option.setEnabled(choice.optBoolean("enabled", true));
                    option.setOnClickListener(v -> renderEvent(nativeSelectOption(choiceIndex), false));
                    optionsBox.addView(option, gap(3));
                }
                dialogueStatus.setText("Escolha uma opção do diálogo recuperado.");
            } else if (type.equals("command")) {
                appendTranscript("[Comando recuperado: " + event.optString("text", "") + "]");
                advanceButton.setText("Continuar"); advanceButton.setVisibility(View.VISIBLE);
                dialogueStatus.setText("Comando mostrado como referência; nenhuma ação do jogo foi executada.");
            } else if (type.equals("stopped")) {
                advanceButton.setVisibility(View.GONE);
                if (transcript.length() == 0) appendTranscript("Fim deste trecho recuperado.");
                dialogueStatus.setText("Trecho concluído. Escolha outro trecho no menu acima.");
            } else {
                advanceButton.setVisibility(View.GONE);
                appendTranscript("Este trecho depende de lógica do jogo ainda não recuperada.");
                dialogueStatus.setText("Escolha outro trecho recuperado no menu acima.");
            }
        } catch (Exception e) {
            advanceButton.setVisibility(View.GONE);
            dialogueText.setText("Não foi possível mostrar este trecho recuperado.");
        }
    }

    private void appendTranscript(String line) {
        if (transcript.length() > 0) transcript.append("\n\n");
        transcript.append(line); dialogueText.setText(transcript.toString());
    }

    private void renderPage() {
        if (!ready || tables.length == 0 || tableSpinner.getSelectedItem() == null) return;
        String table = tableSpinner.getSelectedItem().toString();
        try {
            JSONArray entries = new JSONArray(nativeCatalogPage(table, page * 40, 40));
            catalogStatus.setText(entries.length() == 0
                ? table + " · não há itens nesta página"
                : table + " · itens " + (page * 40 + 1) + "–" + (page * 40 + entries.length()));
            while (body.getChildCount() > 0 && body.getChildAt(body.getChildCount() - 1).getTag() != null)
                body.removeViewAt(body.getChildCount() - 1);
            for (int i = 0; i < entries.length(); i++) {
                TextView line = text(entries.getString(i), 14, false);
                line.setTag("catalog-row"); line.setPadding(dp(10), dp(8), dp(10), dp(8));
                line.setBackgroundColor(i % 2 == 0 ? Color.rgb(34, 35, 39) : Color.rgb(28, 29, 33));
                body.addView(line, gap(1));
            }
            if (entries.length() == 0) {
                TextView empty = text("Não há itens nesta tabela recuperada.", 14, false);
                empty.setTag("catalog-row"); body.addView(empty);
            }
        } catch (Exception e) { catalogStatus.setText("Não foi possível mostrar estes textos recuperados."); }
    }

    private void showImage(int step) {
        imageIndex = (imageIndex + step + IMAGES.length) % IMAGES.length;
        String name = IMAGES[imageIndex];
        try (InputStream in = getAssets().open("images/" + name)) {
            Bitmap bitmap = BitmapFactory.decodeStream(in); imageView.setImageBitmap(bitmap);
            imageCaption.setText((imageIndex + 1) + " / " + IMAGES.length + " · " + name);
        } catch (Exception e) { imageCaption.setText("Imagem recuperada indisponível."); }
    }

    private String readAsset(String path) throws Exception {
        try (InputStream in = getAssets().open(path); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[32768]; int n; while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
            return out.toString(StandardCharsets.UTF_8.name());
        }
    }
    private ArrayAdapter<String> adapter(String[] values) {
        return new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, values);
    }
    private TextView text(String s, int size, boolean bold) {
        TextView v = new TextView(this); v.setText(s); v.setTextColor(ink); v.setTextSize(size);
        if (bold) v.setTypeface(null, 1); return v;
    }
    private Button button(String s) { Button b = new Button(this); b.setText(s); return b; }
    private LinearLayout row() { LinearLayout l = new LinearLayout(this); l.setOrientation(LinearLayout.HORIZONTAL); return l; }
    private LinearLayout.LayoutParams weight() { return new LinearLayout.LayoutParams(0, -2, 1); }
    private LinearLayout.LayoutParams gap(int top) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, -2); p.topMargin = dp(top); return p;
    }
    private int dp(int n) { return (int)(n * getResources().getDisplayMetrics().density + .5f); }
    private static final class SimpleSelect implements android.widget.AdapterView.OnItemSelectedListener {
        private final Runnable action; SimpleSelect(Runnable action) { this.action = action; }
        public void onItemSelected(android.widget.AdapterView<?> p, View v, int position, long id) { action.run(); }
        public void onNothingSelected(android.widget.AdapterView<?> p) {}
    }
}
