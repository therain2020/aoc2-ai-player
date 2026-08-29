package age.of.civilizations2.jakowski.lukasz;

import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
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
    public static volatile String hudLine1 = "";
    public static volatile String hudLine2 = "";
    public static volatile String hudLine3 = "";
    public static volatile String hudLine4 = "";
    public static volatile String hudLine5 = "";
    public static volatile String planText = "";

    // ---- lifecycle ----

    public static void start(int port) throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 16);
        server.createContext("/ping", AgentBridge::handlePing);
        server.createContext("/state", AgentBridge::handleState);
        server.createContext("/action", AgentBridge::handleAction);
        server.createContext("/narration", AgentBridge::handleNarration);
        server.createContext("/hud", AgentBridge::handleHud);
        server.createContext("/plan", AgentBridge::handlePlan);
        server.start();
        loadStrategyAtBoot();
        loadHudAtBoot();
        System.out.println("[AgentBridge] listening on 127.0.0.1:" + port);
    }

    static long lastAutoAdv = 0L;

    private static void persistHud() {
        try {
            java.io.OutputStreamWriter fw = new java.io.OutputStreamWriter(
                    new java.io.FileOutputStream("aoc2_hud.txt"), "UTF-8");
            fw.write(hudLine1 + "\n" + hudLine2 + "\n" + hudLine3 + "\n" + hudLine4 + "\n" + hudLine5);
            fw.close();
        } catch (java.io.IOException ignored) {
        }
    }

    private static void loadHudAtBoot() {
        try {
            java.io.File f = new java.io.File("aoc2_hud.txt");
            if (f.exists()) {
                java.io.BufferedReader br = new java.io.BufferedReader(new java.io.InputStreamReader(
                        new java.io.FileInputStream(f), "UTF-8"));
                String[] lines = new String[5];
                for (int i = 0; i < 5; ++i) {
                    String line = br.readLine();
                    lines[i] = line == null ? "" : line;
                }
                br.close();
                hudLine1 = lines[0]; hudLine2 = lines[1]; hudLine3 = lines[2];
                hudLine4 = lines[3]; hudLine5 = lines[4];
            }
        } catch (Throwable ignored) {
        }
    }

    private static void loadStrategyAtBoot() {
        try {
            java.io.File f = new java.io.File("aoc2_strategy.txt");
            if (f.exists() && f.length() > 0) {
                java.io.BufferedReader br = new java.io.BufferedReader(new java.io.InputStreamReader(
                        new java.io.FileInputStream(f), "UTF-8"));
                String line = br.readLine();
                br.close();
                if (line != null && line.trim().length() > 0) {
                    currentStrategy = line.trim();
                }
            }
        } catch (Throwable ignored) {
        }
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
        try {
            // auto-dismiss the "Next Player Turn" screen (same code path as a click)
            if (CFG.menuManager.getInNextPlayerTurn()) {
                Menu_NextPlayerTurn.clickEnd();
                report("OK|autoDismissNextPlayerTurn");
            }
            // battle flow: advance "next step" confirm screens exactly like the
            // engine's own auto-continue (same code path as a manual click);
            // throttled to avoid click-storming
            Game_Action.TurnStates ts = CFG.gameAction.getActiveTurnState();
            if (ts == Game_Action.TurnStates.LOADING_NEXT_TURN
                    || ts == Game_Action.TurnStates.LOAD_AI_RTO
                    || ts == Game_Action.TurnStates.TURN_ACTIONS) {
                long now = System.currentTimeMillis();
                if (now - lastAutoAdv > 500L) {
                    lastAutoAdv = now;
                    Menu_InGame_ProvinceInfo.clickEndTurn();
                }
            }
            // auto-confirm the "Start The Game" screen once init has finished
            // (same code path as the user's click on the screen)
            if (CFG.menuManager.getInStartGameMenu()
                    && Turn_CivsInRange.DONE_CIVS >= CFG.game.getCivsSize()) {
                Menu_StartTheGame.done();
            }
        } catch (Throwable ignored) {
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
                int me = CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID();
                boolean ok = DiplomacyManager.invest(province, me, gold);
                if (ok) {
                    report("OK|invest|" + province + "|" + gold);
                    break;
                }
                // same province may already have an active invest window:
                // remove it and retry once
                try {
                    CFG.game.getCiv(me).removeInvest_ProvinceID(province);
                } catch (Throwable ignored) { }
                ok = DiplomacyManager.invest(province, me, gold);
                report(ok ? "OK|invest(retry)|" + province + "|" + gold
                        : "FAIL|invest|" + province + "|" + gold);
                break;
            }
            case "endTurn": {
                try {
                    CFG.settingsManager.CONFIRM_END_TURN = false;
                    CFG.settingsManager.CONFIRM_NO_ORDERS = false;
                } catch (Throwable ignored) { }
                CFG.gameAction.tryToTakeNexTurn();
                report("OK|endTurn");
                break;
            }
            case "newGame": {
                try {
                    // idempotency guard: a repeated call after the view switch has
                    // happened must not reset the game a second time
                    if (CFG.menuManager.getInGameView() || CFG.menuManager.getInStartGameMenu()) {
                        report("OK|newGame|already-in-game");
                        break;
                    }
                    CFG.menuManager.getColorPicker().setVisible(false, null);
                    RTS.reset();
                    CFG.game.disableDrawCivlizationsRegions_Players();
                    CFG.viewsManager.disableAllViews();
                    if (CFG.map.getMapScale().getCurrentScale() < Map_Scale.STANDARD_SCALE) {
                        CFG.map.getMapScale().setCurrentScale(Map_Scale.STANDARD_SCALE);
                    }
                    CFG.gameNewGame.newGame();
                    CFG.startTheGameData = new Start_The_Game_Data(false);
                    CFG.menuManager.setViewIDWithoutAnimation(Menu.eSTART_THE_GAME);
                    report("OK|newGame");
                } catch (Throwable t) {
                    report("ERR|newGame|" + t.getClass().getSimpleName());
                }
                break;
            }
            case "enterGodView": {
                try {
                    CFG.FOG_OF_WAR = 0;
                    CFG.gameAction.buildFogOfWar(0);
                    report("OK|enterGodView");
                } catch (Throwable t) {
                    report("ERR|enterGodView|" + t.getClass().getSimpleName());
                }
                break;
            }
            case "peaceTreaty": {
                try {
                    int target = Integer.parseInt(p[1]);
                    int me = CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID();
                    int nWarID = CFG.game.getWarID(me, target);
                    if (nWarID < 0) {
                        report("FAIL|peaceTreaty|" + target + "|no war");
                        break;
                    }
                    boolean meAggressor = CFG.game.getWar(nWarID).getIsAggressor(me);
                    CFG.peaceTreatyData = new PeaceTreaty_Data(nWarID, meAggressor);
                    CFG.peaceTreatyData.AI_UseVictoryPoints();
                    DiplomacyManager.sendPeaceTreaty(meAggressor, me, CFG.peaceTreatyData.peaceTreatyGameData);
                    report("OK|peaceTreaty|" + target);
                } catch (Throwable t) {
                    report("ERR|peaceTreaty|" + t.getClass().getSimpleName());
                }
                break;
            }
            case "respondMessages": {
                int me = CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID();
                int n = 0;
                try {
                    while (CFG.game.getCiv(me).getCivilization_Diplomacy_GameData().messageBox.getMessagesSize() > 0) {
                        int last = CFG.game.getCiv(me).getCivilization_Diplomacy_GameData().messageBox.getMessagesSize() - 1;
                        CFG.game.getCiv(me).getCivilization_Diplomacy_GameData().messageBox.removeMessage(last);
                        ++n;
                    }
                } catch (Throwable t) {
                    report("ERR|respondMessages|" + t.getClass().getSimpleName());
                    break;
                }
                report("OK|respondMessages|" + n);
                break;
            }
            case "loadGame": {
                int idx = Integer.parseInt(p[1]);
                CFG.gameNewGame.loadGame(idx);
                RTS.reset();
                CFG.game.disableDrawCivlizationsRegions_Players();
                CFG.viewsManager.disableAllViews();
                if (CFG.map.getMapScale().getCurrentScale() < Map_Scale.STANDARD_SCALE) {
                    CFG.map.getMapScale().setCurrentScale(Map_Scale.STANDARD_SCALE);
                }
                CFG.EDITOR_ACTIVE_GAMEDATA_TAG = CFG.langManager.get("SavedGame");
                CFG.startTheGameData = new Start_The_Game_Data(false);
                CFG.menuManager.setViewIDWithoutAnimation(Menu.eSTART_THE_GAME);
                report("OK|loadGame|" + idx);
                break;
            }
            case "listSaves": {
                StringBuilder out = new StringBuilder();
                try {
                    java.io.File f = new java.io.File("saves/games/" + CFG.map.getFile_ActiveMap_Path() + "Age_of_Civilizations");
                    java.io.BufferedReader br = new java.io.BufferedReader(
                            new java.io.InputStreamReader(new java.io.FileInputStream(f), "UTF-8"));
                    String line = br.readLine();
                    br.close();
                    if (line != null) {
                        String[] tags = line.split(";");
                        for (int i = 0; i < tags.length; ++i) {
                            if (out.length() > 0) out.append('|');
                            out.append(i).append(':').append(tags[i]);
                        }
                    }
                } catch (IOException e) {
                    out.append("ERR:").append(e.getClass().getSimpleName());
                }
                report("SAVES|" + out);
                break;
            }
            case "toast": {
                CFG.toast.setInView(p[1], new Color(0.95f, 0.75f, 0.25f, 1.0f));
                CFG.toast.setTimeInView(4000);
                report("OK|toast");
                break;
            }
            case "investTech": {
                int me = CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID();
                String cat = p[1];
                int count = p.length > 2 ? Integer.parseInt(p[2]) : 1;
                int done = 0;
                for (int k = 0; k < count; ++k) {
                    try {
                        if (cat.equals("pop_growth")) {
                            if (!SkillsManager.canAdd_PopGrowth(me)) break;
                            SkillsManager.add_PopGrowth(me);
                        } else if (cat.equals("eco_growth")) {
                            if (!SkillsManager.canAdd_EcoGrowth(me)) break;
                            SkillsManager.add_EcoGrowth(me);
                        } else if (cat.equals("taxation")) {
                            if (!SkillsManager.canAdd_IncomeTaxation(me)) break;
                            SkillsManager.add_IncomeTaxation(me);
                        } else if (cat.equals("production")) {
                            if (!SkillsManager.canAdd_IncomeProduction(me)) break;
                            SkillsManager.add_IncomeProduction(me);
                        } else if (cat.equals("administration")) {
                            if (!SkillsManager.canAdd_Administration(me)) break;
                            SkillsManager.add_Administration(me);
                        } else if (cat.equals("military_upkeep")) {
                            if (!SkillsManager.canAdd_MilitaryUpkeep(me)) break;
                            SkillsManager.add_MilitaryUpkeep(me);
                        } else if (cat.equals("research")) {
                            if (!SkillsManager.canAdd_Research(me)) break;
                            SkillsManager.add_Research(me);
                        } else if (cat.equals("colonization")) {
                            if (!SkillsManager.canAdd_Colonization(me)) break;
                            SkillsManager.add_Colonization(me);
                        } else {
                            report("ERR|investTech|unknownCategory|" + cat);
                            break;
                        }
                        ++done;
                    } catch (Throwable t) {
                        report("ERR|investTech|" + t.getClass().getSimpleName());
                        break;
                    }
                }
                report("OK|investTech|" + cat + "|" + done);
                break;
            }
            case "disbandArmy": {
                int province = Integer.parseInt(p[1]);
                int count = Integer.parseInt(p[2]);
                CFG.gameAction.disbandArmy(province, count, CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID());
                report("OK|disbandArmy|" + province + "|" + count);
                break;
            }
            case "moveCapital": {
                int province = Integer.parseInt(p[1]);
                CFG.gameAction.moveCapital(CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID(), province);
                report("OK|moveCapital|" + province);
                break;
            }
            case "offerAlliance": {
                int target = Integer.parseInt(p[1]);
                DiplomacyManager.sendAllianceProposal(target, CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID());
                report("OK|offerAlliance|" + target);
                break;
            }
            case "investDev": {
                int province = Integer.parseInt(p[1]);
                int gold = Integer.parseInt(p[2]);
                boolean ok = DiplomacyManager.investDevelopment(province, CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID(), gold);
                report(ok ? "OK|investDev|" + province + "|" + gold : "FAIL|investDev|" + province + "|" + gold);
                break;
            }
            case "construct": {
                int province = Integer.parseInt(p[2]);
                int me = CFG.game.getPlayer(CFG.PLAYER_TURNID).getCivID();
                String type = p[1];
                boolean ok = false;
                if (type.equals("fort")) ok = BuildingsManager.constructFort(province, me);
                else if (type.equals("farm")) ok = BuildingsManager.constructFarm(province, me);
                else if (type.equals("library")) ok = BuildingsManager.constructLibrary(province, me);
                else if (type.equals("workshop")) ok = BuildingsManager.constructWorkshop(province, me);
                else if (type.equals("armoury")) ok = BuildingsManager.constructArmoury(province, me);
                else if (type.equals("port")) ok = BuildingsManager.constructPort(province, me);
                else if (type.equals("supply")) ok = BuildingsManager.constructSupply(province, me);
                else report("ERR|construct|unknownType|" + type);
                report(ok ? "OK|construct|" + type + "|" + province : "FAIL|construct|" + type + "|" + province);
                break;
            }
            default:
                report("ERR|unknown|" + p[0]);
        }
    }

    private static void report(String s) {
        responses.put("last", s);
        try {
            java.io.FileWriter fw = new java.io.FileWriter("bridge.log", true);
            fw.write(System.currentTimeMillis() + " " + s + "\n");
            fw.close();
        } catch (IOException ignored) {
        }
    }

    // ---- state snapshot (built on GL thread, throttled) ----

    private static volatile long lastStateMs = 0L;

    private static void buildState() {
        long now = System.currentTimeMillis();
        if (now - lastStateMs < 1000L) {
            return;
        }
        lastStateMs = now;
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
            sb.append("\"move_points\":").append(CFG.game.getCiv(me).getMovePoints()).append(",");
            sb.append("\"civs\":").append(CFG.game.getCivsSize()).append(",");
            sb.append("\"players\":").append(CFG.game.getPlayersSize()).append(",");
            sb.append("\"turn_state\":\"").append(CFG.gameAction.getActiveTurnState().name()).append("\",");
            try {
                sb.append("\"in_game\":").append(CFG.menuManager.getInGameView() ? "true" : "false").append(",");
            } catch (Throwable ignored) { sb.append("\"in_game\":false,"); }
            try {
                int autosaveIn = -1;
                try {
                    int total = CFG.settingsManager.TURNS_BETWEEN_AUTOSAVE;
                    if (total > 0) autosaveIn = total - SaveManager.iTurnsSinceLastSave;
                } catch (Throwable ignored) { }
                sb.append("\"autosave_in\":").append(autosaveIn);
                sb.append(",\"my_tech\":").append(String.format("%.2f", CFG.game.getCiv(me).getTechnologyLevel()));
                sb.append(",\"capital\":").append(CFG.game.getCiv(me).getCapitalProvinceID());
                sb.append(",\"date\":\"").append(Game_Calendar.getDate_ByTurnID(Game_Calendar.TURN_ID)).append("\"");
            } catch (Throwable ignored) { }
            sb.append(",\"province_detail\":[");
            StringBuilder pd = new StringBuilder();
            for (int pid = 0; pid < CFG.game.getProvincesSize() && pd.length() < 1400; ++pid) {
                if (CFG.game.getProvince(pid).getCivID() != me) continue;
                try {
                    int armyV = 0;
                    try {
                        armyV = CFG.game.getProvince(pid).getArmy(me);
                    } catch (Throwable ignoredArmy) { }
                    if (pd.length() > 0) pd.append(',');
                    pd.append("{\"id\":").append(pid)
                      .append(",\"pop\":").append(CFG.game.getProvince(pid).getPopulationData().getPopulation())
                      .append(",\"dev\":").append(String.format("%.1f", CFG.game.getProvince(pid).getDevelopmentLevel()))
                      .append(",\"econ\":").append(CFG.game.getProvince(pid).getEconomy())
                      .append(",\"army\":").append(armyV)
                      .append(",\"fort\":").append(CFG.game.getProvince(pid).getLevelOfFort())
                      .append(",\"capital\":").append(CFG.game.getProvince(pid).getIsCapital() ? 1 : 0)
                      .append("}");
                } catch (Throwable ignored) { }
            }
            sb.append(pd).append("],");
            sb.append("\"wars\":[");
            StringBuilder ws = new StringBuilder();
            try {
                for (int i = 0; i < CFG.game.getWarsSize() && ws.length() < 300; ++i) {
                    try {
                        for (int a = 0; a < CFG.game.getWar(i).getAggressorsSize() && ws.length() < 300; ++a) {
                            for (int d = 0; d < CFG.game.getWar(i).getDefendersSize() && ws.length() < 300; ++d) {
                                int ag = CFG.game.getWar(i).getAggressorID(a).getCivID();
                                int df = CFG.game.getWar(i).getDefenderID(d).getCivID();
                                if (ag != me && df != me) continue;
                                if (ws.length() > 0) ws.append(',');
                                ws.append("{\"agg\":").append(ag).append(",\"def\":").append(df).append("}");
                            }
                        }
                    } catch (Throwable ignored) { }
                }
            } catch (Throwable ignored) { }
            sb.append(ws).append("],");
            sb.append("\"stability\":{");
            try {
                float hapSum = 0f;
                float revMax = 0f;
                int coreN = 0;
                int noCore = 0;
                int provinceN = 0;
                for (int pid2 = 0; pid2 < CFG.game.getProvincesSize(); ++pid2) {
                    if (CFG.game.getProvince(pid2).getCivID() != me) continue;
                    ++provinceN;
                    hapSum += CFG.game.getProvince(pid2).getHappiness();
                    float rv = CFG.game.getProvince(pid2).getRevolutionaryRisk();
                    if (rv > revMax) revMax = rv;
                    if (CFG.game.getProvince(pid2).getTrueOwnerOfProvince() == me) ++coreN;
                    else ++noCore;
                }
                float hapAvg = provinceN > 0 ? hapSum / provinceN : 0f;
                sb.append("\"hap_avg\":").append(String.format("%.2f", hapAvg));
                sb.append(",\"rev_max\":").append(String.format("%.2f", revMax));
                sb.append(",\"core\":").append(coreN);
                sb.append(",\"no_core\":").append(noCore);
            } catch (Throwable ignored) { }
            sb.append("},");
            int mbox = 0;
            StringBuilder mtypes = new StringBuilder();
            try {
                mbox = CFG.game.getCiv(me).getCivilization_Diplomacy_GameData().messageBox.getMessagesSize();
                for (int i = 0; i < mbox && mtypes.length() < 120; ++i) {
                    Object m = CFG.game.getCiv(me).getCivilization_Diplomacy_GameData().messageBox.getMessage(i);
                    if (mtypes.length() > 0) mtypes.append(',');
                    mtypes.append(m.getClass().getSimpleName());
                }
            } catch (Throwable ignored) { }
            sb.append("\"messages\":").append(mbox).append(",\"msg_types\":\"").append(mtypes).append("\"");
            try {
                sb.append(",\"tech_points\":").append(CFG.game.getCiv(me).civGameData.skills.getPointsLeft(me));
                sb.append(",\"skills\":{");
                sb.append("\"pop_growth\":").append(CFG.game.getCiv(me).civGameData.skills.POINTS_POP_GROWTH);
                sb.append(",\"eco_growth\":").append(CFG.game.getCiv(me).civGameData.skills.POINTS_ECONOMY_GROWTH);
                sb.append(",\"taxation\":").append(CFG.game.getCiv(me).civGameData.skills.POINTS_INCOME_TAXATION);
                sb.append(",\"production\":").append(CFG.game.getCiv(me).civGameData.skills.POINTS_INCOME_PRODUCTION);
                sb.append(",\"administration\":").append(CFG.game.getCiv(me).civGameData.skills.POINTS_ADMINISTRATION);
                sb.append(",\"military_upkeep\":").append(CFG.game.getCiv(me).civGameData.skills.POINTS_MILITARY_UPKEEP);
                sb.append(",\"research\":").append(CFG.game.getCiv(me).civGameData.skills.POINTS_RESEARCH);
                sb.append(",\"colonization\":").append(CFG.game.getCiv(me).civGameData.skills.POINTS_COLONIZATION);
                sb.append("}");
            } catch (Throwable ignored) { }
            sb.append(",\"my_provinces\":[");
            StringBuilder provsIds = new StringBuilder();
            for (int i = 0; i < CFG.game.getProvincesSize(); ++i) {
                if (CFG.game.getProvince(i).getCivID() == me && CFG.game.getProvince(i).getSeaProvince() == false) {
                    if (provsIds.length() > 0) provsIds.append(',');
                    provsIds.append(i);
                }
            }
            sb.append(provsIds).append("],");
            sb.append("\"neighbors\":[");
            StringBuilder neigh = new StringBuilder();
            java.util.HashMap<Integer, Integer> nMap = new java.util.HashMap<Integer, Integer>();
            String pv = provsIds.length() == 0 ? "" : provsIds.toString();
            for (String pidStr : pv.split(",")) {
                if (pidStr.length() == 0) continue;
                int pid = Integer.parseInt(pidStr);
                for (int j = 0; j < CFG.game.getProvince(pid).getNeighboringProvincesSize(); ++j) {
                    int nc = CFG.game.getProvince(CFG.game.getProvince(pid).getNeighboringProvinces(j)).getCivID();
                    if (nc <= 0 || nc == me) continue;
                    Integer old = nMap.get(nc);
                    nMap.put(nc, old == null ? 1 : old + 1);
                }
            }
            for (java.util.Map.Entry<Integer, Integer> e : nMap.entrySet()) {
                if (neigh.length() > 0) neigh.append(',');
                int nc = e.getKey();
                try {
                    long pop = CFG.game.getCiv(nc).countPopulation();
                    double tech = CFG.game.getCiv(nc).getTechnologyLevel();
                    int rel = (int) CFG.game.getCivRelation_OfCivB(me, nc);
                    boolean atWar = CFG.game.getCivsAtWar(me, nc);
                    boolean allied = CFG.game.getCivsAreAllied(me, nc);
                    int capital = CFG.game.getCiv(nc).getCapitalProvinceID();
                    neigh.append("{\"civ_id\":").append(nc)
                         .append(",\"provinces\":").append(CFG.game.getCiv(nc).getNumOfProvinces())
                         .append(",\"units\":").append(CFG.game.getCiv(nc).getNumOfUnits())
                         .append(",\"population\":").append(pop)
                         .append(",\"money\":").append(CFG.game.getCiv(nc).getMoney())
                         .append(",\"tech\":").append(String.format("%.2f", tech))
                         .append(",\"relation\":").append(rel)
                         .append(",\"allied\":").append(allied)
                         .append(",\"war\":").append(atWar)
                         .append(",\"capital\":").append(capital)
                         .append(",\"border_provinces\":").append(e.getValue()).append("}");
                } catch (Throwable ignored) {
                    neigh.append("{\"civ_id\":").append(nc)
                         .append(",\"border_provinces\":").append(e.getValue()).append("}");
                }
            }
            sb.append(neigh).append("],");
            sb.append("\"front_lines\":[");
            StringBuilder fl = new StringBuilder();
            try {
                for (int pid = 0; pid < CFG.game.getProvincesSize() && fl.length() < 900; ++pid) {
                    if (CFG.game.getProvince(pid).getCivID() != me) continue;
                    for (int j2 = 0; j2 < CFG.game.getProvince(pid).getNeighboringProvincesSize(); ++j2) {
                        int ep = CFG.game.getProvince(pid).getNeighboringProvinces(j2);
                        int ec = CFG.game.getProvince(ep).getCivID();
                        if (ec <= 0 || ec == me || !CFG.game.getCivsAtWar(me, ec)) continue;
                        if (fl.length() > 0) fl.append(',');
                        fl.append("{\"from\":").append(pid)
                          .append(",\"to\":").append(ep)
                          .append(",\"civ\":").append(ec)
                          .append(",\"my_units\":").append(CFG.game.getProvince(pid).getArmy(me))
                          .append(",\"enemy_units\":").append(CFG.game.getProvince(ep).getArmy(ec))
                          .append("}");
                    }
                }
            } catch (Throwable ignored) { }
            sb.append(fl).append("],");
            sb.append("\"treaties\":{");
            StringBuilder tr = new StringBuilder();
            for (java.util.Map.Entry<Integer, Integer> e : nMap.entrySet()) {
                int nc2 = e.getKey();
                try {
                    int dp = CFG.game.getDefensivePact(me, nc2);
                    int gu = CFG.game.getGuarantee(me, nc2);
                    int na = CFG.game.getCivNonAggressionPact(me, nc2);
                    int trc = CFG.game.getCivTruce(me, nc2);
                    if (dp <= 0 && gu <= 0 && na <= 0 && trc <= 0) continue;
                    if (tr.length() > 0) tr.append(',');
                    tr.append("\"").append(nc2).append("\":\"");
                    if (trc > 0) tr.append("停战").append(trc);
                    if (na > 0) { if (trc > 0) tr.append('/'); tr.append("互不侵犯").append(na); }
                    if (dp > 0) { if (trc > 0 || na > 0) tr.append('/'); tr.append("防御条约").append(dp); }
                    if (gu > 0) { if (trc > 0 || na > 0 || dp > 0) tr.append('/'); tr.append("保障").append(gu); }
                    tr.append("\"");
                } catch (Throwable ignored) { }
            }
            sb.append(tr).append("}}");
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
        responses.put("last", "PENDING|" + cmd);
        commands.add(cmd);
        long deadline = System.currentTimeMillis() + 4000L;
        while (System.currentTimeMillis() < deadline) {
            String r = responses.get("last");
            if (r != null && !r.startsWith("PENDING")) {
                respond(ex, r);
                return;
            }
            try {
                Thread.sleep(20);
            } catch (InterruptedException ignored) {
            }
        }
        respond(ex, "TIMEOUT|" + cmd);
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

    private static void handleHud(HttpExchange ex) throws IOException {
        String q = ex.getRequestURI().getRawQuery();
        if (q == null) {
            respond(ex, "ERR|empty");
            return;
        }
        java.util.Map<String, String> kv = new java.util.HashMap<String, String>();
        for (String part : URLDecoder.decode(q, "UTF-8").split("&")) {
            int eq = part.indexOf('=');
            if (eq > 0) {
                kv.put(fromQueryKey(part.substring(0, eq)), part.substring(eq + 1));
            }
        }
        if (kv.containsKey("l1")) hudLine1 = kv.get("l1");
        if (kv.containsKey("l2")) hudLine2 = kv.get("l2");
        if (kv.containsKey("l3")) hudLine3 = kv.get("l3");
        if (kv.containsKey("l4")) hudLine4 = kv.get("l4");
        if (kv.containsKey("l5")) hudLine5 = kv.get("l5");
        persistHud();
        respond(ex, "OK|hud");
    }

    private static String fromQueryKey(String k) {
        if (k.equals("l1")) return "l1";
        return k;
    }

    private static void handlePlan(HttpExchange ex) throws IOException {
        String q = ex.getRequestURI().getRawQuery();
        if (q != null) {
            planText = URLDecoder.decode(q, "UTF-8").replace("text=", "");
        }
        respond(ex, "OK|plan|" + planText.length());
    }

    /**
     * Called right after Game_Action.hideExtraViews() (injected hook) — same
     * frame, so there is no visible flicker. Re-opens the user's data windows
     * from the snapshot updatePlayerData() stored on the Player object before
     * the close sequence ran, i.e. effectively "never closed".
     */
    public static void restoreLockedViews() {
        try {
            Player p = CFG.game.getPlayer(CFG.PLAYER_TURNID);
            if (p.visible_Rank) CFG.menuManager.rebuildInGame_Rank();
            if (p.visible_History) CFG.menuManager.rebuildInGame_History();
            if (p.visible_Wars) CFG.menuManager.rebuildInGame_Wars();
            if (p.visible_Alliances) CFG.menuManager.rebuildInGame_MilitaryAlliances();
            if (p.visible_WarStats >= 0) CFG.menuManager.rebuildInGame_WarDetails();
            if (p.visible_WorldPop) CFG.menuManager.rebuildInGame_WorldPopulation();
            if (p.visible_VictoryConditions) CFG.menuManager.rebuildInGame_VictoryConditions();
            if (p.visible_Technology) CFG.menuManager.rebuildInGame_Technology(p.getCivID());
            if (p.visible_Tribute) CFG.menuManager.rebuildInGame_Tribute();
        } catch (Throwable t) {
            // never break turn flow
        }
    }

    // ---- fixed-position HUD (drawn inside AoCGame.render after drawMapDetails) ----

    static String currentStrategy = "②均衡发展：内政与军备并举，伺机扩张";

    public static void drawHud(SpriteBatch oSB) {
        if (hudLine1 == null) return;
        try {
            CFG.fontMain.getData().setScale(0.72f);
            Color gold = new Color(0.95f, 0.78f, 0.35f, 1.0f);
            Color white = new Color(0.92f, 0.96f, 1.0f, 1.0f);
            Color dim = new Color(0.78f, 0.85f, 0.98f, 1.0f);
            int x = CFG.PADDING * 2;
            int y = 62;                          // below the top info bar
            int lh = (int) (CFG.TEXT_HEIGHT * 1.25f);
            CFG.drawTextWithShadow(oSB, "战略: " + currentStrategy, x, y, gold);
            y += lh;
            if (hudLine1.length() > 0) {
                CFG.drawTextWithShadow(oSB, hudLine1, x, y, white);
                y += lh;
            }
            if (hudLine2.length() > 0) {
                CFG.drawTextWithShadow(oSB, hudLine2, x, y, dim);
                y += lh;
            }
            if (hudLine3.length() > 0) {
                CFG.drawTextWithShadow(oSB, hudLine3, x, y, dim);
                y += lh;
            }
            if (hudLine4.length() > 0) {
                CFG.drawTextWithShadow(oSB, hudLine4, x, y, dim);
                y += lh;
            }
            if (hudLine5.length() > 0) {
                CFG.drawTextWithShadow(oSB, hudLine5, x, y, dim);
            }
            CFG.fontMain.getData().setScale(1.0f);
        } catch (Throwable ignored) {
        }
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
