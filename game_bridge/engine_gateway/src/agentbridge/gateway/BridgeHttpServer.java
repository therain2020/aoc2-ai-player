package agentbridge.gateway;

import com.badlogic.gdx.Gdx;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URLDecoder;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.logging.Logger;

/**
 * BridgeHttpServer — REST face of the source-level bridge (127.0.0.1).
 *
 * Endpoints (engine-api.md): GET /state, POST /action, POST /plan, GET /hud.
 * Compatibility extras: GET /ping, GET /action?cmd=…, GET /plan?text=…,
 * GET /narration?text=… (legacy AgentBridge transport). Engine calls are
 * always dispatched on the GL/render thread via Gdx.app.postRunnable and the
 * HTTP thread waits on a bounded latch (never blocks the render thread).
 */
public final class BridgeHttpServer {

    public static final String HOST = "127.0.0.1";

    private BridgeHttpServer() {
    }

    /** Create, wire routes and start. Returns the running server. */
    public static HttpServer start(int port) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress(HOST, port), 0);
        final ExecutorService pool = Executors.newCachedThreadPool(new ThreadFactory() {
            @Override
            public Thread newThread(Runnable r) {
                Thread t = new Thread(r, "engine-gateway-http");
                t.setDaemon(true);
                return t;
            }
        });
        server.setExecutor(pool);
        server.createContext("/ping", BridgeHttpServer::handlePing);
        server.createContext("/state", BridgeHttpServer::handleState);
        server.createContext("/action", BridgeHttpServer::handleAction);
        server.createContext("/plan", BridgeHttpServer::handlePlan);
        server.createContext("/hud", BridgeHttpServer::handleHud);
        server.createContext("/narration", BridgeHttpServer::handleNarration);
        server.createContext("/diag", BridgeHttpServer::handleDiag);
        server.start();
        return server;
    }

    // ---- handlers ----

    private static void handlePing(HttpExchange ex) throws IOException {
        respond(ex, 200, "text/plain; charset=utf-8", "pong");
    }

    /** GET /diag — T015 troubleshooting: Gdx.app, postRunnable, pump ticks. */
    private static void handleDiag(HttpExchange ex) throws IOException {
        respondJson(ex, 200, "{"
                + "\"diag\":" + Json.quote(diag)
                + ",\"null_app_count\":" + diagNullApp
                + ",\"post_err_count\":" + diagPostErr
                + ",\"post_err_msg\":" + Json.quote(diagPostErrMsg)
                + ",\"runnable_ran\":" + diagRunnableRan
                + ",\"gl_tick_ran\":" + EngineGateway.glTickRan
                + "}");
    }

    /** GET /state — serve the GL-pump cached snapshot (glTick builds at most once
     *  per second; a full build touches every province through reflection and can
     *  exceed any sane HTTP latch, so building on demand here is wrong by design). */
    private static void handleState(HttpExchange ex) throws IOException {
        String body = EngineState.lastState();
        if (body == null || body.equals("{}")) {
            // force one build through the pump if never built yet
            EngineGateway.tickSoon();
        }
        respondJson(ex, 200, body == null ? "{}" : body);
    }

    /**
     * POST /action {"action": "...", "params": {...}} (or legacy
     * GET /action?cmd=declareWar|5). Engine call runs on the GL thread;
     * response shape per engine-api.md: {"result","log","detail"}.
     */
    private static void handleAction(HttpExchange ex) throws IOException {
        String query = ex.getRequestURI().getRawQuery();
        boolean legacy = "GET".equalsIgnoreCase(ex.getRequestMethod()) && query != null && query.contains("cmd=");
        if (legacy) {
            String cmd = URLDecoder.decode(query, "UTF-8").replace("cmd=", "");
            final AtomicReference<EngineActions.Result> ref = new AtomicReference<EngineActions.Result>();
            final CountDownLatch latch = new CountDownLatch(1);
            if (!postGl(() -> ref.set(EngineActions.executePipe(cmd)), ref, latch)) {
                respondJson(ex, 500, "{\"result\":\"FAIL\",\"log\":\"gdx-not-ready\",\"detail\":{}}");
                return;
            }
            respondResult(ex, await(ref, latch, 5));
            return;
        }
        // POST json
        String body = readBody(ex);
        Map<String, Object> root;
        try {
            root = toMap(Json.parse(body));
        } catch (Throwable t) {
            respondJson(ex, 400, "{\"result\":\"FAIL\",\"log\":\"bad json body: " + t.getMessage() + "\",\"detail\":{}}");
            return;
        }
        String action = root.get("action") == null ? "" : root.get("action").toString();
        Object paramsObj = root.get("params");
        Map<String, Object> params = paramsObj instanceof Map ? toMap(paramsObj) : new HashMap<String, Object>();
        final AtomicReference<EngineActions.Result> ref = new AtomicReference<EngineActions.Result>();
        final CountDownLatch latch = new CountDownLatch(1);
        if (!postGl(() -> ref.set(EngineActions.execute(action, params)), ref, latch)) {
            respondJson(ex, 500, "{\"result\":\"FAIL\",\"log\":\"gdx-not-ready\",\"detail\":{}}");
            return;
        }
        respondResult(ex, await(ref, latch, 5));
    }

    /**
     * POST /plan {brief, turns:[{offset, actions:[...], note}], base_provinces,
     * start_turn} — stores the plan into the in-memory channel (dashboard
     * reads it back). GET /plan?text=… is the legacy transport.
     */
    private static void handlePlan(HttpExchange ex) throws IOException {
        String query = ex.getRequestURI().getRawQuery();
        if ("GET".equalsIgnoreCase(ex.getRequestMethod())) {
            if (query != null && query.contains("text=")) {
                String text = URLDecoder.decode(query, "UTF-8").replace("text=", "");
                EngineGateway.setPlanText(text);
                respondJson(ex, 200, "{\"result\":\"OK\",\"log\":\"OK|plan|" + text.length() + "\",\"detail\":{\"chars\":" + text.length() + "}}");
                return;
            }
            // GET /plan without text=: dashboard read-back of the last POST /plan body
            String stored = EngineGateway.planJson;
            respondJson(ex, 200, "{\"result\":\"OK\",\"log\":\"plan-read\",\"detail\":"
                    + (stored == null || stored.length() == 0 ? "{}" : stored) + "}");
            return;
        }
        String body = readBody(ex);
        Map<String, Object> root;
        try {
            root = toMap(Json.parse(body));
        } catch (Throwable t) {
            respondJson(ex, 400, "{\"result\":\"FAIL\",\"log\":\"bad json body\",\"detail\":{}}");
            return;
        }
        int turns = 0;
        int actions = 0;
        try {
            Object turnsObj = root.get("turns");
            if (turnsObj instanceof List) {
                List<?> turnList = (List<?>) turnsObj;
                turns = turnList.size();
                for (Object t : turnList) {
                    Map<String, Object> turn = toMap(t);
                    Object acts = turn.get("actions");
                    if (!(acts instanceof List)) {
                        continue;
                    }
                    for (Object a : (List<?>) acts) {
                        Map<String, Object> am = toMap(a);
                        Object name = am.get("action");
                        if (name != null && !EngineActions.ACTION_NAMES.contains(name.toString())) {
                            respondJson(ex, 200, "{\"result\":\"FAIL\",\"log\":\"unknown action: " + name + "\",\"detail\":{}}");
                            return;
                        }
                        ++actions;
                    }
                }
            }
        } catch (Throwable t) {
            respondJson(ex, 400, "{\"result\":\"FAIL\",\"log\":\"plan parse error\",\"detail\":{}}");
            return;
        }
        String brief = root.get("brief") == null ? "" : root.get("brief").toString();
        StringBuilder text = new StringBuilder();
        text.append("[plan] brief: ").append(brief);
        if (turns > 0) {
            text.append(" (").append(turns).append(" turns, ").append(actions).append(" actions)");
        }
        EngineGateway.setPlanText(text.toString());
        EngineGateway.setPlanJson(body);
        respondJson(ex, 200, "{\"result\":\"OK\",\"log\":\"OK|plan|" + text.length() + "\",\"detail\":{\"brief\":" + Json.quote(brief) + ",\"turns\":" + turns + ",\"actions\":" + actions + "}}");
    }

    /**
     * GET /hud — with l1..l5 query params: HUD data feed (金额/Token/战报/战略档)
     * set in-memory lines + persist aoc2_hud.txt (legacy transport, agent
     * BridgeClient.hud()); without params: read current lines back.
     */
    private static void handleHud(HttpExchange ex) throws IOException {
        String query = ex.getRequestURI().getRawQuery();
        if (query != null && query.contains("l1=")) {
            Map<String, String> kv = new HashMap<String, String>();
            for (String part : URLDecoder.decode(query, "UTF-8").split("&")) {
                int eq = part.indexOf('=');
                if (eq > 0) {
                    kv.put(part.substring(0, eq), part.substring(eq + 1));
                }
            }
            EngineGateway.setHud(kv.get("l1"), kv.get("l2"), kv.get("l3"), kv.get("l4"), kv.get("l5"));
            respondJson(ex, 200, "{\"result\":\"OK\",\"log\":\"OK|hud\",\"detail\":{}}");
            return;
        }
        respondJson(ex, 200, "{\"result\":\"OK\",\"log\":\"hud-read\",\"detail\":{"
                + "\"l1\":" + Json.quote(EngineGateway.hudLine(1))
                + ",\"l2\":" + Json.quote(EngineGateway.hudLine(2))
                + ",\"l3\":" + Json.quote(EngineGateway.hudLine(3))
                + ",\"l4\":" + Json.quote(EngineGateway.hudLine(4))
                + ",\"l5\":" + Json.quote(EngineGateway.hudLine(5))
                + "}}");
    }

    /** GET /narration?text=… — legacy toast transport (compat). */
    private static void handleNarration(HttpExchange ex) throws IOException {
        String query = ex.getRequestURI().getRawQuery();
        if (query == null) {
            respondJson(ex, 200, "{\"result\":\"FAIL\",\"log\":\"empty\",\"detail\":{}}");
            return;
        }
        final String text = URLDecoder.decode(query, "UTF-8").replace("text=", "");
        final AtomicReference<EngineActions.Result> ref = new AtomicReference<EngineActions.Result>();
        final CountDownLatch latch = new CountDownLatch(1);
        Map<String, Object> params = new HashMap<String, Object>();
        params.put("text", text);
        if (!postGl(() -> ref.set(EngineActions.execute("toast", params)), ref, latch)) {
            respondJson(ex, 500, "{\"result\":\"FAIL\",\"log\":\"gdx-not-ready\",\"detail\":{}}");
            return;
        }
        respondResult(ex, await(ref, latch, 5));
    }

    // ---- plumbing ----

    // ---- diagnostics (T015 troubleshooting) ----
    static volatile String diag = "no-requests-yet";
    static volatile int diagNullApp = 0;
    static volatile int diagPostErr = 0;
    static volatile String diagPostErrMsg = "";
    static volatile int diagRunnableRan = 0;

    private static final Logger LOG = Logger.getLogger("engine-gateway");

    /** Post a GL-thread task. Returns false when Gdx.app is not ready. */
    private static boolean postGl(Runnable task, AtomicReference<?> ref, CountDownLatch latch) {
        try {
            if (Gdx.app == null) {
                diagNullApp++;
                diag = "Gdx.app==null (game booting?) nullCount=" + diagNullApp
                        + " pumpRan=" + EngineGateway.glTickRan;
                return false;
            }
            Gdx.app.postRunnable(() -> {
                diagRunnableRan++;
                try {
                    task.run();
                } catch (Throwable t) {
                    diag = "runnable-exc: " + t;
                } finally {
                    latch.countDown();
                }
            });
            diag = "posted ok, runnableRan=" + diagRunnableRan
                    + " pumpRan=" + EngineGateway.glTickRan;
            return true;
        } catch (Throwable t) {
            diagPostErr++;
            diagPostErrMsg = t.toString();
            diag = "postRunnable threw #" + diagPostErr + ": " + diagPostErrMsg;
            return false;
        }
    }

    private static EngineActions.Result await(AtomicReference<EngineActions.Result> ref,
                                              CountDownLatch latch, long secs) {
        try {
            if (latch.await(secs, TimeUnit.SECONDS)) {
                EngineActions.Result r = ref.get();
                return r == null ? new EngineActions.Result("FAIL", "bridge-error", null) : r;
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        return new EngineActions.Result("FAIL", "bridge-timeout", null);
    }

    private static void respondResult(HttpExchange ex, EngineActions.Result r) throws IOException {
        respondJson(ex, 200,
                "{\"result\":" + Json.quote(r.result) + ",\"log\":" + Json.quote(r.log)
                        + ",\"detail\":" + r.detail + "}");
    }

    private static void respondJson(HttpExchange ex, int status, String jsonBody) throws IOException {
        respond(ex, status, "application/json; charset=utf-8", jsonBody);
    }

    private static void respond(HttpExchange ex, int status, String contentType, String body) throws IOException {
        byte[] b = body.getBytes("UTF-8");
        ex.getResponseHeaders().set("Content-Type", contentType);
        ex.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
        ex.sendResponseHeaders(status, b.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(b);
        }
    }

    private static String readBody(HttpExchange ex) throws IOException {
        InputStream in = ex.getRequestBody();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0) {
            out.write(buf, 0, n);
        }
        return new String(out.toByteArray(), "UTF-8");
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> toMap(Object o) {
        if (o instanceof Map) {
            return (Map<String, Object>) o;
        }
        return new HashMap<String, Object>();
    }
}
