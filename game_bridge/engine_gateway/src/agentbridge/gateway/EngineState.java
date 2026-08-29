package agentbridge.gateway;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * EngineState — BridgeState JSON snapshot (GL thread only).
 *
 * Assembly is ported VERBATIM from the legacy bridge AgentBridge.buildState()
 * (field set: turn/map/my_civ/money/provinces/units/move_points/civs/players/
 * turn_state/in_game/autosave_in/my_tech/capital/date/province_detail/wars/
 * stability/messages/msg_types/tech_points/skills/my_provinces/neighbors/
 * front_lines/treaties). Protected engine members are read via EngineApi.
 * Guarded extras requested by engine-api.md (data-model §1): diplomacy_points,
 * assimilates, income.*, low_stability_list, truce, war_score, game_end.
 */
final class EngineState {

    private EngineState() {
    }

    private static final String CFG = "age.of.civilizations2.jakowski.lukasz.CFG";
    private static final String GAME_CALENDAR = "age.of.civilizations2.jakowski.lukasz.Game_Calendar";
    private static final String SAVE_MANAGER = "age.of.civilizations2.jakowski.lukasz.SaveManager";
    private static final String GAME_ACTION = "age.of.civilizations2.jakowski.lukasz.Game_Action";

    private static volatile String lastState = "{}";
    private static volatile long lastStateMs = 0L;

    static String lastState() {
        return lastState;
    }

    /** Build immediately (throttled by the GL pump when called via lastState() path). */
    static String buildNow() {
        lastState = build();
        return lastState;
    }

    /** Build at most once per 1000ms (legacy throttle), called from the GL pump. */
    static void buildIfStale() {
        long now = System.currentTimeMillis();
        if (now - lastStateMs < 1000L) {
            return;
        }
        lastStateMs = now;
        buildNow();
    }

    private static Object game() {
        return EngineApi.get(EngineApi.cls(CFG), "game");
    }

    private static int me() {
        Object turn = EngineApi.get(EngineApi.cls(CFG), "PLAYER_TURNID");
        Object player = EngineApi.call(game(), "getPlayer", turn);
        return ((Integer) EngineApi.call(player, "getCivID")).intValue();
    }

    private static String build() {
        try {
            int me = me();
            boolean inGame = false;
            try {
                inGame = ((Boolean) EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "menuManager"), "getInGameView")).booleanValue();
            } catch (Throwable ignored) {
            }

            StringBuilder sb = new StringBuilder(4096);
            sb.append("{");

            // turn / map / my_civ
            sb.append("\"turn\":")
              .append(EngineApi.get(EngineApi.cls(GAME_CALENDAR), "TURN_ID"))
              .append(",\"map\":").append(Json.quote((String) EngineApi.call(
                      EngineApi.get(EngineApi.cls(CFG), "map"), "getFile_ActiveMap_Path")))
              .append(",\"my_civ\":").append(me);

            Object civ = EngineApi.call(game(), "getCiv", me);
            sb.append(",\"money\":").append(EngineApi.call(civ, "getMoney"))
              .append(",\"provinces\":").append(EngineApi.call(civ, "getNumOfProvinces"))
              .append(",\"units\":").append(EngineApi.call(civ, "getNumOfUnits"))
              .append(",\"move_points\":").append(EngineApi.call(civ, "getMovePoints"))
              .append(",\"civs\":").append(EngineApi.call(game(), "getCivsSize"))
              .append(",\"players\":").append(EngineApi.call(game(), "getPlayersSize"))
              .append(",\"turn_state\":").append(Json.quote((String) EngineApi.call(
                      EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "gameAction"), "getActiveTurnState"), "name")))
              .append(",\"in_game\":").append(inGame);

            // autosave_in / my_tech / capital / date (guarded as in legacy)
            try {
                int autosaveIn = -1;
                try {
                    int total = ((Integer) EngineApi.get(
                            EngineApi.get(EngineApi.cls(CFG), "settingsManager"), "TURNS_BETWEEN_AUTOSAVE")).intValue();
                    if (total > 0) {
                        autosaveIn = total - ((Integer) EngineApi.get(EngineApi.cls(SAVE_MANAGER), "iTurnsSinceLastSave")).intValue();
                    }
                } catch (Throwable ignored) {
                }
                sb.append(",\"autosave_in\":").append(autosaveIn)
                  .append(",\"my_tech\":").append(String.format("%.2f", ((Float) EngineApi.call(civ, "getTechnologyLevel")).floatValue()))
                  .append(",\"capital\":").append(EngineApi.call(civ, "getCapitalProvinceID"))
                  .append(",\"date\":").append(Json.quote((String) EngineApi.call(
                          EngineApi.cls(GAME_CALENDAR), "getDate_ByTurnID",
                          EngineApi.get(EngineApi.cls(GAME_CALENDAR), "TURN_ID"))));
            } catch (Throwable ignored) {
            }

            // province_detail (my provinces, capped ~1400 chars)
            sb.append(",\"province_detail\":[");
            StringBuilder pd = new StringBuilder();
            int provincialSize = ((Integer) EngineApi.call(game(), "getProvincesSize")).intValue();
            for (int pid = 0; pid < provincialSize && pd.length() < 1400; ++pid) {
                if (((Integer) EngineApi.call(EngineApi.call(game(), "getProvince", pid), "getCivID")).intValue() != me) {
                    continue;
                }
                try {
                    int armyV = 0;
                    try {
                        armyV = ((Integer) EngineApi.call(EngineApi.call(game(), "getProvince", pid), "getArmyCivID", me)).intValue();
                    } catch (Throwable ignoredArmy) {
                    }
                    Object prov = EngineApi.call(game(), "getProvince", pid);
                    if (pd.length() > 0) {
                        pd.append(',');
                    }
                    pd.append("{\"id\":").append(pid)
                      .append(",\"pop\":").append(EngineApi.call(EngineApi.call(prov, "getPopulationData"), "getPopulation"))
                      .append(",\"dev\":").append(String.format("%.1f", ((Float) EngineApi.call(prov, "getDevelopmentLevel")).floatValue()))
                      .append(",\"econ\":").append(EngineApi.call(prov, "getEconomy"))
                      .append(",\"army\":").append(armyV)
                      .append(",\"fort\":").append(EngineApi.call(prov, "getLevelOfFort"))
                      .append(",\"capital\":").append(((Boolean) EngineApi.call(prov, "getIsCapital")).booleanValue() ? 1 : 0)
                      .append("}");
                } catch (Throwable ignored) {
                }
            }
            sb.append(pd).append("],");

            // wars ({agg,def} pairs touching me, capped ~300 chars)
            sb.append("\"wars\":[");
            StringBuilder ws = new StringBuilder();
            try {
                int warSize = ((Integer) EngineApi.call(game(), "getWarsSize")).intValue();
                for (int i = 0; i < warSize && ws.length() < 300; ++i) {
                    try {
                        Object war = EngineApi.call(game(), "getWar", i);
                        int aggSize = ((Integer) EngineApi.call(war, "getAggressorsSize")).intValue();
                        int defSize = ((Integer) EngineApi.call(war, "getDefendersSize")).intValue();
                        for (int a = 0; a < aggSize && ws.length() < 300; ++a) {
                            for (int d = 0; d < defSize && ws.length() < 300; ++d) {
                                int ag = ((Integer) EngineApi.call(EngineApi.call(war, "getAggressorID", a), "getCivID")).intValue();
                                int df = ((Integer) EngineApi.call(EngineApi.call(war, "getDefenderID", d), "getCivID")).intValue();
                                if (ag != me && df != me) {
                                    continue;
                                }
                                if (ws.length() > 0) {
                                    ws.append(',');
                                }
                                int score = 0;
                                int myScore = 0;
                                try {
                                    score = ((Integer) EngineApi.call(war, "getWarScore")).intValue();
                                    boolean meAggressor = ((Boolean) EngineApi.call(war, "getIsAggressor", me)).booleanValue();
                                    // engine score is defender-advantage: negative = aggressors lead
                                    myScore = meAggressor ? -score : score;
                                } catch (Throwable ignoredScore) {
                                }
                                ws.append("{\"agg\":").append(ag).append(",\"def\":").append(df)
                                  .append(",\"war_score\":").append(score)
                                  .append(",\"my_score\":").append(myScore)
                                  .append(",\"their_score\":").append(-myScore).append("}");
                            }
                        }
                    } catch (Throwable ignored) {
                    }
                }
            } catch (Throwable ignored) {
            }
            sb.append(ws).append("],");

            // stability (hap_avg / rev_max / core / no_core)
            sb.append("\"stability\":{");
            try {
                float hapSum = 0f;
                float revMax = 0f;
                int coreN = 0;
                int noCore = 0;
                int provinceN = 0;
                for (int pid2 = 0; pid2 < provincialSize; ++pid2) {
                    Object prov = EngineApi.call(game(), "getProvince", pid2);
                    if (((Integer) EngineApi.call(prov, "getCivID")).intValue() != me) {
                        continue;
                    }
                    ++provinceN;
                    hapSum += ((Float) EngineApi.call(prov, "getHappiness")).floatValue();
                    float rv = ((Float) EngineApi.call(prov, "getRevolutionaryRisk")).floatValue();
                    if (rv > revMax) {
                        revMax = rv;
                    }
                    if (((Integer) EngineApi.call(prov, "getTrueOwnerOfProvince")).intValue() == me) {
                        ++coreN;
                    } else {
                        ++noCore;
                    }
                }
                float hapAvg = provinceN > 0 ? hapSum / provinceN : 0f;
                sb.append("\"hap_avg\":").append(String.format("%.2f", hapAvg))
                  .append(",\"rev_max\":").append(String.format("%.2f", revMax))
                  .append(",\"core\":").append(coreN)
                  .append(",\"no_core\":").append(noCore);
            } catch (Throwable ignored) {
            }
            sb.append("},");

            // messages / msg_types
            int mbox = 0;
            StringBuilder mtypes = new StringBuilder();
            try {
                Object messageBox = EngineApi.get(
                        EngineApi.call(civ, "getCivilization_Diplomacy_GameData"), "messageBox");
                mbox = ((Integer) EngineApi.call(messageBox, "getMessagesSize")).intValue();
                for (int i = 0; i < mbox && mtypes.length() < 120; ++i) {
                    Object m = EngineApi.call(messageBox, "getMessage", i);
                    if (mtypes.length() > 0) {
                        mtypes.append(',');
                    }
                    mtypes.append(m.getClass().getSimpleName());
                }
            } catch (Throwable ignored) {
            }
            sb.append("\"messages\":").append(mbox)
              .append(",\"msg_types\":").append(Json.quote(mtypes.toString()));

            // tech_points / skills (guarded as in legacy)
            try {
                Object skills = EngineApi.get(EngineApi.get(civ, "civGameData"), "skills");
                sb.append(",\"tech_points\":").append(EngineApi.call(skills, "getPointsLeft", me))
                  .append(",\"skills\":{")
                  .append("\"pop_growth\":").append(EngineApi.get(skills, "POINTS_POP_GROWTH"))
                  .append(",\"eco_growth\":").append(EngineApi.get(skills, "POINTS_ECONOMY_GROWTH"))
                  .append(",\"taxation\":").append(EngineApi.get(skills, "POINTS_INCOME_TAXATION"))
                  .append(",\"production\":").append(EngineApi.get(skills, "POINTS_INCOME_PRODUCTION"))
                  .append(",\"administration\":").append(EngineApi.get(skills, "POINTS_ADMINISTRATION"))
                  .append(",\"military_upkeep\":").append(EngineApi.get(skills, "POINTS_MILITARY_UPKEEP"))
                  .append(",\"research\":").append(EngineApi.get(skills, "POINTS_RESEARCH"))
                  .append(",\"colonization\":").append(EngineApi.get(skills, "POINTS_COLONIZATION"))
                  .append("}");
            } catch (Throwable ignored) {
            }

            // my_provinces (non-sea ids)
            sb.append(",\"my_provinces\":[");
            StringBuilder provsIds = new StringBuilder();
            for (int i = 0; i < provincialSize; ++i) {
                Object prov = EngineApi.call(game(), "getProvince", i);
                if (((Integer) EngineApi.call(prov, "getCivID")).intValue() == me
                        && !((Boolean) EngineApi.call(prov, "getSeaProvince")).booleanValue()) {
                    if (provsIds.length() > 0) {
                        provsIds.append(',');
                    }
                    provsIds.append(i);
                }
            }
            sb.append(provsIds).append("],");

            // neighbors (civ -> border province count, +profile)
            sb.append("\"neighbors\":[");
            StringBuilder neigh = new StringBuilder();
            Map<Integer, Integer> nMap = new HashMap<Integer, Integer>();
            String pv = provsIds.toString();
            if (pv.length() > 0) {
                for (String pidStr : pv.split(",")) {
                    if (pidStr.length() == 0) {
                        continue;
                    }
                    int pid = Integer.parseInt(pidStr);
                    Object prov = EngineApi.call(game(), "getProvince", pid);
                    int nbSize = ((Integer) EngineApi.call(prov, "getNeighboringProvincesSize")).intValue();
                    for (int j = 0; j < nbSize; ++j) {
                        int nProv = ((Integer) EngineApi.call(prov, "getNeighboringProvinces", j)).intValue();
                        int nc = ((Integer) EngineApi.call(EngineApi.call(game(), "getProvince", nProv), "getCivID")).intValue();
                        if (nc <= 0 || nc == me) {
                            continue;
                        }
                        Integer old = nMap.get(nc);
                        nMap.put(nc, old == null ? 1 : old + 1);
                    }
                }
            }
            for (Map.Entry<Integer, Integer> e : nMap.entrySet()) {
                if (neigh.length() > 0) {
                    neigh.append(',');
                }
                int nc = e.getKey().intValue();
                try {
                    Object nCiv = EngineApi.call(game(), "getCiv", nc);
                    long pop = ((Number) EngineApi.call(nCiv, "countPopulation")).longValue();
                    float tech = ((Float) EngineApi.call(nCiv, "getTechnologyLevel")).floatValue();
                    int rel = (int) ((Float) EngineApi.call(game(), "getCivRelation_OfCivB", me, nc)).floatValue();
                    boolean atWar = ((Boolean) EngineApi.call(game(), "getCivsAtWar", me, nc)).booleanValue();
                    boolean allied = ((Boolean) EngineApi.call(game(), "getCivsAreAllied", me, nc)).booleanValue();
                    int capital = ((Integer) EngineApi.call(nCiv, "getCapitalProvinceID")).intValue();
                    neigh.append("{\"civ_id\":").append(nc)
                         .append(",\"provinces\":").append(EngineApi.call(nCiv, "getNumOfProvinces"))
                         .append(",\"units\":").append(EngineApi.call(nCiv, "getNumOfUnits"))
                         .append(",\"population\":").append(pop)
                         .append(",\"money\":").append(EngineApi.call(nCiv, "getMoney"))
                         .append(",\"tech\":").append(String.format("%.2f", tech))
                         .append(",\"relation\":").append(rel)
                         .append(",\"allied\":").append(allied)
                         .append(",\"war\":").append(atWar)
                         .append(",\"capital\":").append(capital)
                         .append(",\"border_provinces\":").append(e.getValue().intValue()).append("}");
                } catch (Throwable ignored) {
                    neigh.append("{\"civ_id\":").append(nc)
                         .append(",\"border_provinces\":").append(e.getValue().intValue()).append("}");
                }
            }
            sb.append(neigh).append("],");

            // front_lines (war borders, capped ~900 chars). Each entry is built
            // in its own buffer with per-field guards: a failed getter must not
            // corrupt the JSON (a partially-appended entry caused a parse
            // failure on the war path — smoke run).
            sb.append("\"front_lines\":[");
            StringBuilder fl = new StringBuilder();
            try {
                for (int pid = 0; pid < provincialSize && fl.length() < 900; ++pid) {
                    Object prov = EngineApi.call(game(), "getProvince", pid);
                    if (((Integer) EngineApi.call(prov, "getCivID")).intValue() != me) {
                        continue;
                    }
                    int nbSize = ((Integer) EngineApi.call(prov, "getNeighboringProvincesSize")).intValue();
                    for (int j2 = 0; j2 < nbSize; ++j2) {
                        try {
                            int ep = ((Integer) EngineApi.call(prov, "getNeighboringProvinces", j2)).intValue();
                            int ec = ((Integer) EngineApi.call(EngineApi.call(game(), "getProvince", ep), "getCivID")).intValue();
                            if (ec <= 0 || ec == me
                                    || !((Boolean) EngineApi.call(game(), "getCivsAtWar", me, ec)).booleanValue()) {
                                continue;
                            }
                            Object myArmy = null;
                            Object enemyArmy = null;
                            try {
                                myArmy = EngineApi.call(prov, "getArmyCivID", me);
                            } catch (Throwable ignoredArmy) {
                            }
                            try {
                                enemyArmy = EngineApi.call(
                                        EngineApi.call(game(), "getProvince", ep), "getArmyCivID", ec);
                            } catch (Throwable ignoredArmy) {
                            }
                            // 2026-08-29: army getter may fail for occupied/war zones —
                            // emit 0 instead of dropping the whole front entry
                            // (dropping emptied front_lines and starved the war loop).
                            if (myArmy == null) {
                                myArmy = Integer.valueOf(0);
                            }
                            if (enemyArmy == null) {
                                enemyArmy = Integer.valueOf(0);
                            }
                            StringBuilder item = new StringBuilder();
                            item.append("{\"from\":").append(pid)
                                .append(",\"to\":").append(ep)
                                .append(",\"civ\":").append(ec)
                                .append(",\"my_units\":").append(myArmy)
                                .append(",\"enemy_units\":").append(enemyArmy)
                                .append("}");
                            if (fl.length() > 0) {
                                fl.append(',');
                            }
                            fl.append(item);
                        } catch (Throwable ignoredEntry) {
                        }
                    }
                }
            } catch (Throwable ignored) {
            }
            sb.append(fl).append("],");

            // treaties (per-neighbor: truce/nap/defensive pact/guarantee)
            sb.append("\"treaties\":{");
            StringBuilder tr = new StringBuilder();
            for (Map.Entry<Integer, Integer> e : nMap.entrySet()) {
                int nc2 = e.getKey().intValue();
                try {
                    int dp = ((Integer) EngineApi.call(game(), "getDefensivePact", me, nc2)).intValue();
                    int gu = ((Integer) EngineApi.call(game(), "getGuarantee", me, nc2)).intValue();
                    int na = ((Integer) EngineApi.call(game(), "getCivNonAggressionPact", me, nc2)).intValue();
                    int trc = ((Integer) EngineApi.call(game(), "getCivTruce", me, nc2)).intValue();
                    if (dp <= 0 && gu <= 0 && na <= 0 && trc <= 0) {
                        continue;
                    }
                    if (tr.length() > 0) {
                        tr.append(',');
                    }
                    tr.append(Json.quote(Integer.toString(nc2))).append(':').append(Json.quote(
                            treatyText(trc, na, dp, gu)));
                } catch (Throwable ignored) {
                }
            }
            sb.append(tr).append("}");

            // contract extras — machine-readable truce per neighbor (getCivTruce, guarded)
            sb.append(",\"truce\":[");
            StringBuilder tc = new StringBuilder();
            for (Map.Entry<Integer, Integer> e2 : nMap.entrySet()) {
                int nc3 = e2.getKey().intValue();
                try {
                    int trcV = ((Integer) EngineApi.call(game(), "getCivTruce", me, nc3)).intValue();
                    if (trcV <= 0) {
                        continue;
                    }
                    if (tc.length() > 0) {
                        tc.append(',');
                    }
                    tc.append("{\"civ_id\":").append(nc3).append(",\"turns\":").append(trcV).append("}");
                } catch (Throwable ignored) {
                }
            }
            sb.append(tc).append("]");

            // contract extras — diplomacy_points (guarded)
            try {
                int dpPoints = ((Integer) EngineApi.call(EngineApi.call(game(), "getCiv", me), "getDiplomacyPoints")).intValue();
                sb.append(",\"diplomacy_points\":").append(dpPoints);
            } catch (Throwable ignored) {
            }
            // contract extras — assimilates (guarded; engine exposes these via
            // protected class-level APIs, so fields hit via reflection)
            try {
                Object meCiv = EngineApi.call(game(), "getCiv", me);
                int asz = ((Integer) EngineApi.call(meCiv, "getAssimilatesSize")).intValue();
                StringBuilder as = new StringBuilder("[");
                for (int i = 0; i < asz && as.length() < 500; ++i) {
                    Object a = EngineApi.call(meCiv, "getAssimilate", i);
                    int pid = ((Integer) EngineApi.get(a, "iProvinceID")).intValue();
                    int turns = ((Integer) EngineApi.get(a, "iTurnsLeft")).intValue();
                    long population = ((Number) EngineApi.call(
                            EngineApi.call(EngineApi.call(game(), "getProvince", pid), "getPopulationData"), "getPopulation")).longValue();
                    if (i > 0) {
                        as.append(',');
                    }
                    as.append("{\"province_id\":").append(pid)
                      .append(",\"turns_left\":").append(turns)
                      .append(",\"population\":").append(population)
                      .append("}");
                }
                as.append("]");
                sb.append(",\"assimilates\":").append(as);
            } catch (Throwable ignored) {
            }
            // contract extras — income (FR-003): gold_in/gold_out/balance from
            // Game_NextTurnUpdate, diplo_delta from Game_Action.updateCivsDiplomacyPoints
            try {
                Object ntu = EngineApi.get(EngineApi.cls(CFG), "game_NextTurnUpdate");
                float goldIn = ((Number) EngineApi.call(ntu, "getIncome", me)).floatValue();
                float goldOut = ((Number) EngineApi.call(ntu, "getExpenses", me)).floatValue();
                int balance = ((Number) EngineApi.call(ntu, "getBalance", me)).intValue();
                int diploDelta = ((Number) EngineApi.call(
                        EngineApi.get(EngineApi.cls(CFG), "gameAction"), "getUpdateCivsDiplomacyPoints", me)).intValue();
                sb.append(",\"income\":{")
                  .append("\"gold_in\":").append(goldIn)
                  .append(",\"gold_out\":").append(goldOut)
                  .append(",\"balance\":").append(balance)
                  .append(",\"diplo_delta\":").append(diploDelta)
                  .append("}");
            } catch (Throwable ignored) {
            }
            // contract extras — adjacency for MY provinces (agent battlefield
            // view: which of my provinces touch which enemy provinces — move
            // legality & gather targets, 2026-08-29 user requirement)
            try {
                StringBuilder adj = new StringBuilder("[");
                boolean firstAdj = true;
                for (int pidA2 = 0; pidA2 < provincialSize; ++pidA2) {
                    Object provA2 = EngineApi.call(game(), "getProvince", pidA2);
                    if (((Integer) EngineApi.call(provA2, "getCivID")).intValue() != me) {
                        continue;
                    }
                    int nbSizeA = ((Integer) EngineApi.call(provA2, "getNeighboringProvincesSize")).intValue();
                    for (int ja = 0; ja < nbSizeA; ++ja) {
                        int npa = ((Integer) EngineApi.call(provA2, "getNeighboringProvinces", ja)).intValue();
                        try {
                            int nca = ((Integer) EngineApi.call(
                                    EngineApi.call(game(), "getProvince", npa), "getCivID")).intValue();
                            if (!firstAdj) {
                                adj.append(',');
                            }
                            firstAdj = false;
                            adj.append("{\"mine\":").append(pidA2)
                               .append(",\"nbr\":").append(npa)
                               .append(",\"civ\":").append(nca).append("}");
                        } catch (Throwable ignoredNb) {
                        }
                    }
                }
                adj.append("]");
                sb.append(",\"adjacency\":").append(adj);
            } catch (Throwable ignored) {
            }
            // contract extras — armies overview: EVERY province with MY army >0
            // (user fix 2026-08-29: getArmyCivID is the safe per-civ reader —
            // shows where my garrisons actually are, not just front pairs)
            try {
                StringBuilder aw = new StringBuilder("[");
                boolean firstArmy = true;
                for (int pidA = 0; pidA < provincialSize; ++pidA) {
                    Object provA = EngineApi.call(game(), "getProvince", pidA);
                    if (((Integer) EngineApi.call(provA, "getCivID")).intValue() != me) {
                        continue;
                    }
                    int aN = ((Integer) EngineApi.call(provA, "getArmyCivID", me)).intValue();
                    if (aN <= 0) {
                        continue;
                    }
                    if (!firstArmy) {
                        aw.append(',');
                    }
                    firstArmy = false;
                    aw.append("{\"prov\":").append(pidA).append(",\"army\":").append(aN).append("}");
                }
                aw.append("]");
                sb.append(",\"armies_overview\":").append(aw);
            } catch (Throwable ignored) {
            }
            // contract extras — budget sliders (Budget 面板滑块，玩家等价可调)
            try {
                Object meCiv2 = EngineApi.call(game(), "getCiv", me);
                sb.append(",\"budget\":{")
                  .append("\"taxation\":").append(EngineApi.call(meCiv2, "getTaxationLevel"))
                  .append(",\"goods\":").append(EngineApi.call(meCiv2, "getSpendings_Goods"))
                  .append(",\"research\":").append(EngineApi.call(meCiv2, "getSpendings_Research"))
                  .append(",\"investments\":").append(EngineApi.call(meCiv2, "getSpendings_Investments"))
                  .append("}");
            } catch (Throwable ignored) {
            }
            // contract extras — low_stability_list (civ.lProvincesWithLowStability, guarded)
            try {
                Object lowList = EngineApi.get(EngineApi.call(game(), "getCiv", me), "lProvincesWithLowStability");
                if (lowList instanceof List) {
                    List<?> low = (List<?>) lowList;
                    StringBuilder ls = new StringBuilder("[");
                    for (int i = 0; i < low.size() && ls.length() < 500; ++i) {
                        if (i > 0) {
                            ls.append(',');
                        }
                        ls.append(low.get(i).toString());
                    }
                    ls.append("]");
                    sb.append(",\"low_stability_list\":").append(ls);
                }
            } catch (Throwable ignored) {
            }
            // contract extras — game_end signal (Game_Action.gameEnded)
            try {
                boolean ended = ((Boolean) EngineApi.get(EngineApi.cls(GAME_ACTION), "gameEnded")).booleanValue();
                sb.append(",\"game_end\":{\"ended\":").append(ended).append("}");
            } catch (Throwable ignored) {
            }

            sb.append("}");
            return sb.toString();
        } catch (Throwable t) {
            return "{\"err\":\"" + t.getClass().getSimpleName() + "\"}";
        }
    }

    private static String treatyText(int trc, int na, int dp, int gu) {
        StringBuilder t = new StringBuilder();
        if (trc > 0) {
            t.append("停战").append(trc);
        }
        if (na > 0) {
            if (trc > 0) {
                t.append('/');
            }
            t.append("互不侵犯").append(na);
        }
        if (dp > 0) {
            if (trc > 0 || na > 0) {
                t.append('/');
            }
            t.append("防御条约").append(dp);
        }
        if (gu > 0) {
            if (trc > 0 || na > 0 || dp > 0) {
                t.append('/');
            }
            t.append("保障").append(gu);
        }
        return t.toString();
    }
}
