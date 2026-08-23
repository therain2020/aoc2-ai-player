package age.of.civilizations2.jakowski.lukasz;

import com.badlogic.gdx.graphics.Color;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URLDecoder;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicReference;

/**
 * AgentBridge: in-game HTTP control bridge.
 * Runs inside the game JVM; command queue is drained on the GL thread via
 * AgentBridge.tick(), which a ClassFileTransformer injects at the top of
 * AoCGame.render(). All engine calls happen on the render thread (no races),
 * and AgentBridge lives in this package so protected engine APIs are
 * directly callable. Localhost only.
 */
public class AgentBridge {
    private static final ConcurrentLinkedQueue<String> commands = new ConcurrentLinkedQueue<>();
    private static final ConcurrentHashMap<String, String> responses = new ConcurrentHashMap<>();
    private static final AtomicReference<String> lastState = new AtomicReference<>("{}");
    private static volatile HttpServer server;

    // ---- lifecycle ----

    public static void start(int port) throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 16);
        server.createContext("/ping", AgentBridge::handlePing);
        server.createContext("/state", AgentBridge::handleState);
        server.createContext("/action", AgentBridge::handleAction);
        server.createContext("/narration", AgentBridge::handleNarration);
        server.start();
        System.out.println("[AgentBridge] listening on 127.0.0.1:" + port);
    }

    // ---- GL-thread pump (injected into AoCGame.render top) ----

    public static void tick() {
        String cmd;
        while ((cmd = commands.poll()) != null) {
            try {
                dispatch(cmd);
            } catch (Throwable t) {
                report("ERR|" + t.getClass().getSimpleName() + "|" + t.getMessage());
            }
        }
        buildState();
    }

    // ---- dispatch (safe: engine APIs only) ----

    private static void dispatch(String cmd) {
        String[] p = cmd.split("\\|", -1);
        switch (p[0]) {
            case "declareWar": {
                int target = Integer.parseInt(p[1]);
                CFG.game.declareWar(CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID(), target, false);
                report("OK|declareWar|" + target);
                break;
            }
            case "recruitArmy": {
                int province = Integer.parseInt(p[1]);
                int count = Integer.parseInt(p[2]);
                CFG.game.getCiv(CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID()).recruitArmy_AI(province, count);
                report("OK|recruitArmy|" + province + "|" + count);
                break;
            }
            case "moveArmy": {
                int from = Integer.parseInt(p[1]);
                int to = Integer.parseInt(p[2]);
                int count = Integer.parseInt(p[3]);
                boolean ok = CFG.gameAction.moveArmy(from, to, count,
                        CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID(), true, false);
                report(ok ? "OK|moveArmy|" + from + "|" + to + "|" + count
                        : "FAIL|moveArmy|" + from + "|" + to + "|" + count);
                break;
            }
            case "invest": {
                int province = Integer.parseInt(p[1]);
                int gold = Integer.parseInt(p[2]);
                boolean ok = DiplomacyManager.invest(province, CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID(), gold);
                report(ok ? "OK|invest|" + province + "|" + gold : "FAIL|invest|" + province + "|" + gold);
                break;
            }
            case "endTurn": {
                CFG.gameAction.tryToTakeNexTurn();
                report("OK|endTurn");
                break;
            }
            case "toast": {
                CFG.toast.setInView(p[1], new Color(0.95f, 0.75f, 0.25f, 1.0f));
                CFG.toast.setTimeInView(4000);
                report("OK|toast");
                break;
            }
            default:
                report("ERR|unknown|" + p[0]);
        }
    }

    private static void report(String s) {
        responses.put("last", s);
    }

    // ---- state snapshot (built on GL thread every tick) ----

    private static void buildState() {
        try {
            int me = CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID();
            StringBuilder sb = new StringBuilder();
            sb.append("{");
            sb.append("\"turn\":").append(Game_Calendar.TURN_ID).append(",");
            sb.append("\"map\":\"").append(CFG.map.getFile_ActiveMap_Path()).append("\",");
            sb.append("\"my_civ\":").append(me).append(",");
            sb.append("\"money\":").append(CFG.game.getCiv(me).getMoney()).append(",");
            sb.append("\"provinces\":").append(CFG.game.getCiv(me).getNumOfProvinces()).append(",");
            sb.append("\"units\":").append(CFG.game.getCiv(me).getNumOfUnits()).append(",");
            sb.append("\"civs\":").append(CFG.game.getCivsSize()).append(",");
            sb.append("\"players\":").append(CFG.game.getPlayersSize());
            sb.append("}");
            lastState.set(sb.toString());
        } catch (Throwable t) {
            lastState.set("{\"err\":\"" + t.getClass().getSimpleName() + "\"}");
        }
    }

    // ---- HTTP handlers (localhost only) ----

    private static void handlePing(HttpExchange ex) throws IOException {
        respond(ex, "pong");
    }

    private static void handleState(HttpExchange ex) throws IOException {
        respond(ex, lastState.get());
    }

    private static void handleAction(HttpExchange ex) throws IOException {
        String q = ex.getRequestURI().getRawQuery();
        if (q == null) {
            respond(ex, "ERR|empty");
            return;
        }
        String cmd = URLDecoder.decode(q, "UTF-8").replace("cmd=", "");
        commands.add(cmd);
        respond(ex, "QUEUED|" + cmd);
    }

    private static void handleNarration(HttpExchange ex) throws IOException {
        String q = ex.getRequestURI().getRawQuery();
        if (q == null) {
            respond(ex, "ERR|empty");
            return;
        }
        String text = URLDecoder.decode(q, "UTF-8").replace("text=", "");
        commands.add("toast|" + text);
        respond(ex, "QUEUED|toast");
    }

    private static void respond(HttpExchange ex, String body) throws IOException {
        byte[] b = body.getBytes("UTF-8");
        ex.getResponseHeaders().set("Content-Type", "text/plain; charset=utf-8");
        ex.sendResponseHeaders(200, b.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(b);
        }
    }
}
