package agentbridge.gateway;

import com.badlogic.gdx.Gdx;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * EngineGateway — source-level bridge entry (2026-08-29 decision: replaces the
 * ASM javaagent bridge; no ASM, no engine class changes, no Premain manifest).
 *
 * Lifecycle: start() creates the HTTP server (127.0.0.1:7187) and spawns a
 * daemon pump thread that re-posts a GL-thread tick via Gdx.app.postRunnable —
 * the source-level replacement for the ASM-injected AgentBridge.tick() hook in
 * AoCGame.render(). The GL tick performs the legacy auto-advance
 * (NextPlayerTurn dismiss, LOADING/TURN_ACTIONS advance, Menu_StartTheGame
 * auto-done) and keeps the /state snapshot cache fresh. Engine mutations and
 * state reads run ONLY on the GL thread (constitution II); HTTP threads block
 * on bounded latches and never block the render thread.
 */
public final class EngineGateway {

    private EngineGateway() {
    }

    /** Bridge port (fixed, same convention as the legacy AgentBridge). */
    public static final int DEFAULT_PORT = 7187;

    /** True once the HTTP server is up and the GL pump is running. */
    public static volatile boolean ready = false;

    static class Names {
        static final String CFG = "age.of.civilizations2.jakowski.lukasz.CFG";
        static final String GAME_ACTION = "age.of.civilizations2.jakowski.lukasz.Game_Action";
        static final String GAME_CALENDAR = "age.of.civilizations2.jakowski.lukasz.Game_Calendar";
        static final String TURN_CIVS_IN_RANGE = "age.of.civilizations2.jakowski.lukasz.Turn_CivsInRange";
        static final String MENU_NEXT_PLAYER_TURN = "age.of.civilizations2.jakowski.lukasz.Menu_NextPlayerTurn";
        static final String MENU_IN_GAME_PROVINCE_INFO = "age.of.civilizations2.jakowski.lukasz.Menu_InGame_ProvinceInfo";
        static final String MENU_START_THE_GAME = "age.of.civilizations2.jakowski.lukasz.Menu_StartTheGame";
    }

    private static volatile boolean started = false;

    private static final AtomicBoolean tickPosted = new AtomicBoolean(false);
    private static volatile long lastAutoAdv = 0L;

    // ---- HUD data feed (金额/Token/战报/战略档) + aoc2_hud.txt persistence ----

    static volatile String hudLine1 = "";
    static volatile String hudLine2 = "";
    static volatile String hudLine3 = "";
    static volatile String hudLine4 = "";
    static volatile String hudLine5 = "";
    static volatile String planText = "";
    /** Raw POST /plan JSON body (dashboard GET /plan read-back). */
    static volatile String planJson = "";

    static String hudLine(int i) {
        switch (i) {
            case 1: return hudLine1;
            case 2: return hudLine2;
            case 3: return hudLine3;
            case 4: return hudLine4;
            default: return hudLine5;
        }
    }

    static synchronized void setHud(String l1, String l2, String l3, String l4, String l5) {
        if (l1 != null) hudLine1 = l1;
        if (l2 != null) hudLine2 = l2;
        if (l3 != null) hudLine3 = l3;
        if (l4 != null) hudLine4 = l4;
        if (l5 != null) hudLine5 = l5;
        persistHud();
    }

    static void setPlanText(String text) {
        planText = text == null ? "" : text;
    }

    static void setPlanJson(String json) {
        planJson = json == null ? "" : json;
    }

    private static void persistHud() {
        try {
            OutputStreamWriter fw = new OutputStreamWriter(new FileOutputStream("aoc2_hud.txt"), "UTF-8");
            fw.write(hudLine1 + "\n" + hudLine2 + "\n" + hudLine3 + "\n" + hudLine4 + "\n" + hudLine5);
            fw.close();
        } catch (IOException ignored) {
        }
    }

    private static void loadHudAtBoot() {
        try {
            File f = new File("aoc2_hud.txt");
            if (f.exists()) {
                BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(f), "UTF-8"));
                String[] lines = new String[5];
                for (int i = 0; i < 5; ++i) {
                    String line = br.readLine();
                    lines[i] = line == null ? "" : line;
                }
                br.close();
                hudLine1 = lines[0];
                hudLine2 = lines[1];
                hudLine3 = lines[2];
                hudLine4 = lines[3];
                hudLine5 = lines[4];
            }
        } catch (Throwable ignored) {
        }
    }

    // ---- lifecycle ----

    /** Start the bridge (HTTP server + GL pump). Idempotent. */
    public static synchronized void start() throws IOException {
        if (started) {
            return;
        }
        BridgeHttpServer.start(DEFAULT_PORT);
        loadHudAtBoot();
        Thread pump = new Thread(EngineGateway::pumpLoop, "engine-gateway-pump");
        pump.setDaemon(true);
        pump.start();
        started = true;
        ready = true;
        System.out.println("[EngineGateway] listening on 127.0.0.1:" + DEFAULT_PORT);
    }

    public static int port() {
        return DEFAULT_PORT;
    }

    // ---- GL-thread pump (source-level replacement of legacy AgentBridge.tick) ----

    /**
     * Daemon loop: keeps exactly one GL tick queued at a time so the autopilot
     * actions run on the render thread even though no code was injected into
     * AoCGame.render.
     */
    private static void pumpLoop() {
        for (;;) {
            try {
                Thread.sleep(150L);
            } catch (InterruptedException e) {
                return;
            }
            try {
                if (Gdx.app == null || tickPosted.get()) {
                    continue;
                }
                if (tickPosted.compareAndSet(false, true)) {
                    Gdx.app.postRunnable(EngineGateway::glTick);
                }
            } catch (Throwable ignored) {
            }
        }
    }

    static volatile int glTickRan = 0;

    /** Ask the pump to run its GL tick sooner (used when the state cache is cold). */
    static void tickSoon() {
        tickPosted.compareAndSet(true, false);
    }

    /** GL-thread tick (same code points as legacy AgentBridge.tick). */
    private static void glTick() {
        tickPosted.set(false);
        glTickRan++;
        EngineState.buildIfStale();
        try {
            Object game = EngineApi.get(EngineApi.cls(Names.CFG), "game");
            // auto-dismiss the "Next Player Turn" screen (same code path as a click)
            Object menuMgr = EngineApi.get(EngineApi.cls(Names.CFG), "menuManager");
            if (((Boolean) EngineApi.call(menuMgr, "getInNextPlayerTurn")).booleanValue()) {
                EngineApi.call(EngineApi.cls(Names.MENU_NEXT_PLAYER_TURN), "clickEnd");
            }
            // battle flow: advance "next step" confirm screens exactly like the
            // engine's own auto-continue (same code path as a manual click);
            // throttled to avoid click-storming
            String ts = EngineApi.call(
                    EngineApi.call(EngineApi.get(EngineApi.cls(Names.CFG), "gameAction"), "getActiveTurnState"), "name").toString();
            if (ts.equals("LOADING_NEXT_TURN") || ts.equals("LOAD_AI_RTO") || ts.equals("TURN_ACTIONS")) {
                long now = System.currentTimeMillis();
                if (now - lastAutoAdv > 500L) {
                    lastAutoAdv = now;
                    EngineApi.call(EngineApi.cls(Names.MENU_IN_GAME_PROVINCE_INFO), "clickEndTurn");
                }
            }
            // auto-confirm the "Start The Game" screen once init has finished
            // (same code path as the user's click on the screen)
            if (((Boolean) EngineApi.call(menuMgr, "getInStartGameMenu")).booleanValue()
                    && ((Integer) EngineApi.get(EngineApi.cls(Names.TURN_CIVS_IN_RANGE), "DONE_CIVS")).intValue()
                        >= ((Integer) EngineApi.call(game, "getCivsSize")).intValue()) {
                EngineApi.call(EngineApi.cls(Names.MENU_START_THE_GAME), "done");
            }
        } catch (Throwable ignored) {
        }
        // keep the /state cache fresh (throttled inside)
        EngineState.buildIfStale();
    }
}
