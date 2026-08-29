package agentbridge.gateway;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * EngineActions — engine-side action execution (GL thread only).
 *
 * Every branch is ported VERBATIM from the legacy bridge AgentBridge.dispatch()
 * (game_bridge/agent_bridge/src/age/of/civilizations2/jakowski/lukasz/AgentBridge.java),
 * with the only adaptation being that protected engine members are reached via
 * EngineApi (reflection) because this bridge lives in agentbridge.gateway.
 * New-style names follow agent/actions.py ACTION_SPEC; legacy pipe names
 * (declareWar|...|...) are accepted as aliases for backward compatibility.
 */
final class EngineActions {

    private EngineActions() {
    }

    // engine class names
    private static final String CFG = "age.of.civilizations2.jakowski.lukasz.CFG";
    private static final String GAME = "age.of.civilizations2.jakowski.lukasz.Game";
    private static final String GAME_ACTION = "age.of.civilizations2.jakowski.lukasz.Game_Action";
    private static final String GAME_NEWGAME = "age.of.civilizations2.jakowski.lukasz.Game_NewGame";
    private static final String DIPLO = "age.of.civilizations2.jakowski.lukasz.DiplomacyManager";
    private static final String SKILLS = "age.of.civilizations2.jakowski.lukasz.SkillsManager";
    private static final String BUILDINGS = "age.of.civilizations2.jakowski.lukasz.BuildingsManager";
    private static final String RTS = "age.of.civilizations2.jakowski.lukasz.RTS";
    private static final String MAP_SCALE = "age.of.civilizations2.jakowski.lukasz.Map_Scale";
    private static final String START_THE_GAME_DATA = "age.of.civilizations2.jakowski.lukasz.Start_The_Game_Data";
    private static final String PEACE_TREATY_DATA = "age.of.civilizations2.jakowski.lukasz.PeaceTreaty_Data";
    private static final String MENU = "age.of.civilizations2.jakowski.lukasz.Menu";
    private static final String TRADE_REQUEST = "age.of.civilizations2.jakowski.lukasz.TradeRequest_GameData";
    private static final String TRADE_REQUEST_LIST = "age.of.civilizations2.jakowski.lukasz.TradeRequest_List";
    private static final String ULTIMATUM = "age.of.civilizations2.jakowski.lukasz.Ultimatum_GameData";
    private static final String SUPPORT_REBELS_DATA = "age.of.civilizations2.jakowski.lukasz.SupportRebels_Data";

    /** ACTION_SPEC names (agent/actions.py) plus bridge extras. */
    static final Set<String> ACTION_NAMES = new HashSet<String>(Arrays.asList(
            "declare_war", "recruit_army", "move_army", "invest", "invest_dev",
            "invest_tech", "disband_army", "move_capital", "offer_alliance",
            "construct", "peace_treaty", "new_game", "end_turn", "enter_god_view",
            "respond_messages", "load_game", "list_saves", "toast", "state",
            // L1 外交全集 (T034, docs/mechanics.md L1)
            "send_gift", "send_insult", "trade_request", "nonaggression_pact",
            "offer_vasalization", "military_access_ask", "military_access_give",
            "improve_relations", "decrease_relations", "support_rebels", "ultimatum",
            "civilize", "form_civilization", "proclaim_independence",
            "prepare_for_war", "call_to_arms",
            // 内政三动作 (T035)
            "assimilate", "festival", "colonize",
            // 交易挑拨 (TradeRequest_GameData 双清单：LEFT=我方给金, RIGHT=对方宣誓战/联盟)
            "buy_war", "coalition_war",
            // Budget 面板滑块（玩家等价操作；引擎 clamp，支出总和<=200%）
            "set_budget",
            // 联盟链：互保条约 / 联合统治提议
            "guarantee_independence", "union_proposal"));

    static final class Result {
        final String result; // "OK" | "FAIL"
        final String log;    // human- / agent-readable one-liner
        final String detail; // raw JSON object (may be "{}")

        Result(String result, String log, String detail) {
            this.result = result;
            this.log = log;
            this.detail = detail == null ? "{}" : detail;
        }
    }

    /** Execute one action. MUST run on the GL thread (Gdx.app.postRunnable). */
    static Result execute(String name, Map<String, Object> p) {
        if (name == null) {
            return fail("unknown", "missing action name");
        }
        // legacy aliases (AgentBridge pipe names)
        String n = name;
        if (n.equals("declareWar")) { n = "declare_war"; }
        else if (n.equals("recruitArmy")) { n = "recruit_army"; }
        else if (n.equals("moveArmy")) { n = "move_army"; }
        else if (n.equals("investDev")) { n = "invest_dev"; }
        else if (n.equals("investTech")) { n = "invest_tech"; }
        else if (n.equals("disbandArmy")) { n = "disband_army"; }
        else if (n.equals("moveCapital")) { n = "move_capital"; }
        else if (n.equals("offerAlliance")) { n = "offer_alliance"; }
        else if (n.equals("peaceTreaty")) { n = "peace_treaty"; }
        else if (n.equals("newGame")) { n = "new_game"; }
        else if (n.equals("endTurn")) { n = "end_turn"; }
        else if (n.equals("enterGodView")) { n = "enter_god_view"; }
        else if (n.equals("respondMessages")) { n = "respond_messages"; }
        else if (n.equals("loadGame")) { n = "load_game"; }
        else if (n.equals("listSaves")) { n = "list_saves"; }
        else if (n.equals("sendGift")) { n = "send_gift"; }
        else if (n.equals("sendInsult")) { n = "send_insult"; }
        else if (n.equals("tradeRequest")) { n = "trade_request"; }
        else if (n.equals("nonAggressionPact")) { n = "nonaggression_pact"; }
        else if (n.equals("offerVasalization")) { n = "offer_vasalization"; }
        else if (n.equals("militaryAccessAsk")) { n = "military_access_ask"; }
        else if (n.equals("militaryAccessGive")) { n = "military_access_give"; }
        else if (n.equals("improveRelations")) { n = "improve_relations"; }
        else if (n.equals("decreaseRelations")) { n = "decrease_relations"; }
        else if (n.equals("supportRebels")) { n = "support_rebels"; }
        else if (n.equals("ultimatum")) { n = "ultimatum"; }
        else if (n.equals("civilize")) { n = "civilize"; }
        else if (n.equals("formCivilization")) { n = "form_civilization"; }
        else if (n.equals("proclaimIndependence")) { n = "proclaim_independence"; }
        else if (n.equals("prepareForWar")) { n = "prepare_for_war"; }
        else if (n.equals("callToArms")) { n = "call_to_arms"; }
        else if (n.equals("buyWar")) { n = "buy_war"; }
        else if (n.equals("coalitionWar")) { n = "coalition_war"; }
        else if (n.equals("setBudget")) { n = "set_budget"; }
        else if (n.equals("guaranteeIndependence")) { n = "guarantee_independence"; }
        else if (n.equals("unionProposal")) { n = "union_proposal"; }
        else if (n.equals("assimilate")) { n = "assimilate"; }
        else if (n.equals("festival")) { n = "festival"; }
        else if (n.equals("colonize")) { n = "colonize"; }
        else if (n.equals("assimilate")) { n = "assimilate"; }
        else if (n.equals("festival")) { n = "festival"; }
        else if (n.equals("colonize")) { n = "colonize"; }

        if (!ACTION_NAMES.contains(n)) {
            return fail(name, "unknown action: " + name);
        }
        Map<String, Object> ps = p == null ? new HashMap<String, Object>() : p;
        try {
            if (n.equals("declare_war")) {
                return declareWar(ps);
            } else if (n.equals("recruit_army")) {
                return recruitArmy(ps);
            } else if (n.equals("move_army")) {
                return moveArmy(ps);
            } else if (n.equals("invest")) {
                return invest(ps);
            } else if (n.equals("invest_dev")) {
                return investDev(ps);
            } else if (n.equals("invest_tech")) {
                return investTech(ps);
            } else if (n.equals("disband_army")) {
                return disbandArmy(ps);
            } else if (n.equals("move_capital")) {
                return moveCapital(ps);
            } else if (n.equals("offer_alliance")) {
                return offerAlliance(ps);
            } else if (n.equals("construct")) {
                return construct(ps);
            } else if (n.equals("peace_treaty")) {
                return peaceTreaty(ps);
            } else if (n.equals("send_gift")) {
                return sendGift(ps);
            } else if (n.equals("send_insult")) {
                return sendInsult(ps);
            } else if (n.equals("trade_request")) {
                return tradeRequest(ps);
            } else if (n.equals("nonaggression_pact")) {
                return nonAggressionPact(ps);
            } else if (n.equals("offer_vasalization")) {
                return offerVasalization(ps);
            } else if (n.equals("military_access_ask")) {
                return militaryAccessAsk(ps);
            } else if (n.equals("military_access_give")) {
                return militaryAccessGive(ps);
            } else if (n.equals("buy_war")) {
                return buyWar(ps);
            } else if (n.equals("coalition_war")) {
                return coalitionWar(ps);
            } else if (n.equals("set_budget")) {
                return setBudget(ps);
            } else if (n.equals("guarantee_independence")) {
                return guaranteeIndependence(ps);
            } else if (n.equals("union_proposal")) {
                return unionProposal(ps);
            } else if (n.equals("improve_relations")) {
                return improveRelations(ps);
            } else if (n.equals("decrease_relations")) {
                return decreaseRelations(ps);
            } else if (n.equals("support_rebels")) {
                return supportRebels(ps);
            } else if (n.equals("ultimatum")) {
                return ultimatum(ps);
            } else if (n.equals("civilize")) {
                return civilize(ps);
            } else if (n.equals("form_civilization")) {
                return formCivilization(ps);
            } else if (n.equals("proclaim_independence")) {
                return proclaimIndependence(ps);
            } else if (n.equals("prepare_for_war")) {
                return prepareForWar(ps);
            } else if (n.equals("call_to_arms")) {
                return callToArms(ps);
            } else if (n.equals("assimilate")) {
                return assimilate(ps);
            } else if (n.equals("festival")) {
                return festival(ps);
            } else if (n.equals("colonize")) {
                return colonize(ps);
            } else if (n.equals("new_game")) {
                return newGame();
            } else if (n.equals("end_turn")) {
                return endTurn();
            } else if (n.equals("enter_god_view")) {
                return enterGodView();
            } else if (n.equals("respond_messages")) {
                return respondMessages();
            } else if (n.equals("load_game")) {
                return loadGame(ps);
            } else if (n.equals("list_saves")) {
                return listSaves();
            } else if (n.equals("toast")) {
                return toast(ps);
            } else if (n.equals("state")) {
                return new Result("OK", "query|state", "{\"endpoint\":\"GET /state\"}");
            }
            return fail(name, "unknown action: " + name);
        } catch (Throwable t) {
            return fail(name, "ERR|" + t.getClass().getSimpleName() + "|" + t.getMessage());
        }
    }

    /** Legacy pipe form: "declareWar|5|3" (AgentBridge cmd=… transport). */
    static Result executePipe(String cmd) {
        String[] p = cmd.split("\\|", -1);
        Map<String, Object> ps = new HashMap<String, Object>();
        String head = p.length > 0 ? p[0] : "";
        try {
            if (head.equals("declareWar")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
            } else if (head.equals("recruitArmy")) {
                ps.put("province_id", Integer.parseInt(p[1]));
                ps.put("count", Integer.parseInt(p[2]));
            } else if (head.equals("moveArmy")) {
                ps.put("from_province", Integer.parseInt(p[1]));
                ps.put("to_province", Integer.parseInt(p[2]));
                ps.put("count", Integer.parseInt(p[3]));
            } else if (head.equals("invest")) {
                ps.put("province_id", Integer.parseInt(p[1]));
                ps.put("gold", Integer.parseInt(p[2]));
            } else if (head.equals("investDev")) {
                ps.put("province_id", Integer.parseInt(p[1]));
                ps.put("gold", Integer.parseInt(p[2]));
            } else if (head.equals("investTech")) {
                ps.put("category", p.length > 1 ? p[1] : "");
                ps.put("count", p.length > 2 && p[2].length() > 0 ? Integer.parseInt(p[2]) : 1);
            } else if (head.equals("disbandArmy")) {
                ps.put("province_id", Integer.parseInt(p[1]));
                ps.put("count", Integer.parseInt(p[2]));
            } else if (head.equals("moveCapital")) {
                ps.put("province_id", Integer.parseInt(p[1]));
            } else if (head.equals("offerAlliance")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
            } else if (head.equals("construct")) {
                ps.put("building_type", p.length > 1 ? p[1] : "");
                ps.put("province_id", Integer.parseInt(p[2]));
            } else if (head.equals("peaceTreaty")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
            } else if (head.equals("sendGift")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
                ps.put("gold", p.length > 2 && p[2].length() > 0 ? Integer.parseInt(p[2]) : 0);
            } else if (head.equals("sendInsult") || head.equals("decreaseRelations")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
                if (p.length > 2 && p[2].length() > 0) {
                    ps.put("turns", Integer.parseInt(p[2]));
                }
            } else if (head.equals("tradeRequest")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
                ps.put("gold", p.length > 2 && p[2].length() > 0 ? Integer.parseInt(p[2]) : 0);
            } else if (head.equals("nonAggressionPact")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
            } else if (head.equals("offerVasalization")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
            } else if (head.equals("militaryAccessAsk")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
            } else if (head.equals("militaryAccessGive")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
            } else if (head.equals("improveRelations")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
            } else if (head.equals("supportRebels")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
                ps.put("gold", Integer.parseInt(p[2]));
                if (p.length > 3 && p[3].length() > 0) {
                    ps.put("rebel_civ_id", Integer.parseInt(p[3]));
                }
            } else if (head.equals("ultimatum")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
            } else if (head.equals("civilize")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
            } else if (head.equals("formCivilization")) {
                // self-directed (formCiv(me)); no pipe args
            } else if (head.equals("proclaimIndependence")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
            } else if (head.equals("prepareForWar")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
                ps.put("against_civ_id", Integer.parseInt(p[2]));
                if (p.length > 3 && p[3].length() > 0) {
                    ps.put("turns", Integer.parseInt(p[3]));
                }
            } else if (head.equals("callToArms")) {
                ps.put("target_civ_id", Integer.parseInt(p[1]));
                ps.put("against_civ_id", Integer.parseInt(p[2]));
            } else if (head.equals("assimilate")) {
                ps.put("province_id", Integer.parseInt(p[1]));
                if (p.length > 2 && p[2].length() > 0) {
                    ps.put("num_of_turns", Integer.parseInt(p[2]));
                }
            } else if (head.equals("festival")) {
                ps.put("province_id", Integer.parseInt(p[1]));
            } else if (head.equals("colonize")) {
                ps.put("province_id", Integer.parseInt(p[1]));
            } else if (head.equals("loadGame")) {
                ps.put("save_index", Integer.parseInt(p[1]));
            } else if (head.equals("toast")) {
                ps.put("text", p.length > 1 ? p[1] : "");
            }
            return execute(head, ps);
        } catch (Throwable t) {
            return fail(head, "ERR|" + t.getClass().getSimpleName() + "|" + t.getMessage());
        }
    }

    // ---- engine handle helpers ----

    private static Object game() {
        return EngineApi.get(EngineApi.cls(CFG), "game");
    }

    private static Object gameAction() {
        return EngineApi.get(EngineApi.cls(CFG), "gameAction");
    }

    private static Object menuManager() {
        return EngineApi.get(EngineApi.cls(CFG), "menuManager");
    }

    private static Object gameNewGame() {
        return EngineApi.get(EngineApi.cls(CFG), "gameNewGame");
    }

    private static int me() {
        Object turn = EngineApi.get(EngineApi.cls(CFG), "PLAYER_TURNID");
        Object player = EngineApi.call(game(), "getPlayer", turn);
        return ((Integer) EngineApi.call(player, "getCivID")).intValue();
    }

    private static Object civ(int id) {
        return EngineApi.call(game(), "getCiv", id);
    }

    private static int intP(Map<String, Object> ps, String... keys) {
        return Json.asInt(Json.first(ps, keys));
    }

    private static String strP(Map<String, Object> ps, String... keys) {
        Object v = Json.first(ps, keys);
        return v == null ? "" : v.toString();
    }

    private static Result ok(String name, String log, String detail) {
        return new Result("OK", log, detail);
    }

    private static Result fail(String name, String log) {
        return new Result("FAIL", log, null);
    }

    // ---- action branches (ported from legacy AgentBridge.dispatch) ----

    /** declareWar|target — CFG.game.declareWar(me, target, false) */
    private static Result declareWar(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int me = me();
        EngineApi.call(game(), "declareWar", me, target, Boolean.FALSE);
        return ok("declare_war", "OK|declareWar|" + target, detail("target", target));
    }

    /** recruitArmy|province|count — civ.recruitArmy_AI(province, count) */
    private static Result recruitArmy(Map<String, Object> ps) {
        int province = intP(ps, "province_id", "province");
        int count = intP(ps, "count");
        EngineApi.call(civ(me()), "recruitArmy_AI", province, count);
        return ok("recruit_army", "OK|recruitArmy|" + province + "|" + count,
                detail("province_id", province, "count", count));
    }

    /** moveArmy|from|to|count — gameAction.moveArmy(from, to, count, me, true, false) */
    private static Result moveArmy(Map<String, Object> ps) {
        int from = intP(ps, "from_province", "from", "province_a");
        int to = intP(ps, "to_province", "to", "province_b");
        int count = intP(ps, "count");
        boolean okFlag = ((Boolean) EngineApi.call(gameAction(), "moveArmy",
                from, to, count, me(), Boolean.TRUE, Boolean.FALSE)).booleanValue();
        if (okFlag) {
            return ok("move_army", "OK|moveArmy|" + from + "|" + to + "|" + count,
                    detail("from", from, "to", to, "count", count));
        }
        return fail("move_army", "FAIL|moveArmy|" + from + "|" + to + "|" + count);
    }

    /** invest|province|gold — DiplomacyManager.invest(province, me, gold) with retry */
    private static Result invest(Map<String, Object> ps) {
        int province = intP(ps, "province_id", "province");
        int gold = intP(ps, "gold");
        int me = me();
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "invest",
                province, me, gold)).booleanValue();
        if (okFlag) {
            return ok("invest", "OK|invest|" + province + "|" + gold,
                    detail("province_id", province, "gold", gold));
        }
        // same province may already have an active invest window: remove it and retry once
        try {
            EngineApi.call(civ(me), "removeInvest_ProvinceID", province);
        } catch (Throwable ignored) {
        }
        okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "invest",
                province, me, gold)).booleanValue();
        if (okFlag) {
            return ok("invest", "OK|invest(retry)|" + province + "|" + gold,
                    detail("province_id", province, "gold", gold));
        }
        return fail("invest", "FAIL|invest|" + province + "|" + gold);
    }

    /** investDev|province|gold — DiplomacyManager.investDevelopment(province, me, gold) */
    private static Result investDev(Map<String, Object> ps) {
        int province = intP(ps, "province_id", "province");
        int gold = intP(ps, "gold");
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "investDevelopment",
                province, me(), gold)).booleanValue();
        if (okFlag) {
            return ok("invest_dev", "OK|investDev|" + province + "|" + gold,
                    detail("province_id", province, "gold", gold));
        }
        return fail("invest_dev", "FAIL|investDev|" + province + "|" + gold);
    }

    /** investTech|category|count — SkillsManager.canAdd_X / add_X (8 categories) */
    private static Result investTech(Map<String, Object> ps) {
        String cat = strP(ps, "category", "cat");
        int count = ps.containsKey("count") ? intP(ps, "count") : 1;
        int me = me();
        int done = 0;
        for (int k = 0; k < count; ++k) {
            try {
                if (cat.equals("pop_growth")) {
                    if (!((Boolean) EngineApi.call(EngineApi.cls(SKILLS), "canAdd_PopGrowth", me)).booleanValue()) {
                        break;
                    }
                    EngineApi.call(EngineApi.cls(SKILLS), "add_PopGrowth", me);
                } else if (cat.equals("eco_growth")) {
                    if (!((Boolean) EngineApi.call(EngineApi.cls(SKILLS), "canAdd_EcoGrowth", me)).booleanValue()) {
                        break;
                    }
                    EngineApi.call(EngineApi.cls(SKILLS), "add_EcoGrowth", me);
                } else if (cat.equals("taxation")) {
                    if (!((Boolean) EngineApi.call(EngineApi.cls(SKILLS), "canAdd_IncomeTaxation", me)).booleanValue()) {
                        break;
                    }
                    EngineApi.call(EngineApi.cls(SKILLS), "add_IncomeTaxation", me);
                } else if (cat.equals("production")) {
                    if (!((Boolean) EngineApi.call(EngineApi.cls(SKILLS), "canAdd_IncomeProduction", me)).booleanValue()) {
                        break;
                    }
                    EngineApi.call(EngineApi.cls(SKILLS), "add_IncomeProduction", me);
                } else if (cat.equals("administration")) {
                    if (!((Boolean) EngineApi.call(EngineApi.cls(SKILLS), "canAdd_Administration", me)).booleanValue()) {
                        break;
                    }
                    EngineApi.call(EngineApi.cls(SKILLS), "add_Administration", me);
                } else if (cat.equals("military_upkeep")) {
                    if (!((Boolean) EngineApi.call(EngineApi.cls(SKILLS), "canAdd_MilitaryUpkeep", me)).booleanValue()) {
                        break;
                    }
                    EngineApi.call(EngineApi.cls(SKILLS), "add_MilitaryUpkeep", me);
                } else if (cat.equals("research")) {
                    if (!((Boolean) EngineApi.call(EngineApi.cls(SKILLS), "canAdd_Research", me)).booleanValue()) {
                        break;
                    }
                    EngineApi.call(EngineApi.cls(SKILLS), "add_Research", me);
                } else if (cat.equals("colonization")) {
                    if (!((Boolean) EngineApi.call(EngineApi.cls(SKILLS), "canAdd_Colonization", me)).booleanValue()) {
                        break;
                    }
                    EngineApi.call(EngineApi.cls(SKILLS), "add_Colonization", me);
                } else {
                    return fail("invest_tech", "ERR|investTech|unknownCategory|" + cat);
                }
                ++done;
            } catch (Throwable t) {
                return fail("invest_tech", "ERR|investTech|" + t.getClass().getSimpleName());
            }
        }
        return ok("invest_tech", "OK|investTech|" + cat + "|" + done,
                "{\"category\":" + Json.quote(cat) + ",\"done\":" + done + "}");
    }

    /** disbandArmy|province|count — gameAction.disbandArmy(province, count, me) */
    private static Result disbandArmy(Map<String, Object> ps) {
        int province = intP(ps, "province_id", "province");
        int count = intP(ps, "count");
        EngineApi.call(gameAction(), "disbandArmy", province, count, me());
        return ok("disband_army", "OK|disbandArmy|" + province + "|" + count,
                detail("province_id", province, "count", count));
    }

    /** moveCapital|province — gameAction.moveCapital(me, province) */
    private static Result moveCapital(Map<String, Object> ps) {
        int province = intP(ps, "province_id", "province");
        EngineApi.call(gameAction(), "moveCapital", me(), province);
        return ok("move_capital", "OK|moveCapital|" + province,
                detail("province_id", province));
    }

    /** offerAlliance|target — DiplomacyManager.sendAllianceProposal(target, me) */
    private static Result offerAlliance(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        EngineApi.call(EngineApi.cls(DIPLO), "sendAllianceProposal", target, me());
        return ok("offer_alliance", "OK|offerAlliance|" + target, detail("target", target));
    }

    /** construct|type|province — BuildingsManager.construct*(province, me) (7 types) */
    private static Result construct(Map<String, Object> ps) {
        int province = intP(ps, "province_id", "province");
        int me = me();
        String type = strP(ps, "building_type", "type");
        boolean okFlag = false;
        if (type.equals("fort")) {
            okFlag = ((Boolean) EngineApi.call(EngineApi.cls(BUILDINGS), "constructFort", province, me)).booleanValue();
        } else if (type.equals("farm")) {
            okFlag = ((Boolean) EngineApi.call(EngineApi.cls(BUILDINGS), "constructFarm", province, me)).booleanValue();
        } else if (type.equals("library")) {
            okFlag = ((Boolean) EngineApi.call(EngineApi.cls(BUILDINGS), "constructLibrary", province, me)).booleanValue();
        } else if (type.equals("workshop")) {
            okFlag = ((Boolean) EngineApi.call(EngineApi.cls(BUILDINGS), "constructWorkshop", province, me)).booleanValue();
        } else if (type.equals("armoury")) {
            okFlag = ((Boolean) EngineApi.call(EngineApi.cls(BUILDINGS), "constructArmoury", province, me)).booleanValue();
        } else if (type.equals("port")) {
            okFlag = ((Boolean) EngineApi.call(EngineApi.cls(BUILDINGS), "constructPort", province, me)).booleanValue();
        } else if (type.equals("supply")) {
            okFlag = ((Boolean) EngineApi.call(EngineApi.cls(BUILDINGS), "constructSupply", province, me)).booleanValue();
        } else {
            return fail("construct", "ERR|construct|unknownType|" + type);
        }
        if (okFlag) {
            return ok("construct", "OK|construct|" + type + "|" + province,
                    "{\"building_type\":" + Json.quote(type) + ",\"province_id\":" + province + "}");
        }
        return fail("construct", "FAIL|construct|" + type + "|" + province);
    }

    /** peaceTreaty|target — PeaceTreaty_Data + AI_UseVictoryPoints + sendPeaceTreaty (legacy verbatim) */
    private static Result peaceTreaty(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int me = me();
        int nWarID = ((Integer) EngineApi.call(game(), "getWarID", me, target)).intValue();
        if (nWarID < 0) {
            return fail("peace_treaty", "FAIL|peaceTreaty|" + target + "|no war");
        }
        Object war = EngineApi.call(game(), "getWar", nWarID);
        boolean meAggressor = ((Boolean) EngineApi.call(war, "getIsAggressor", me)).booleanValue();
        Object peaceData = EngineApi.newInst(EngineApi.cls(PEACE_TREATY_DATA), nWarID, Boolean.valueOf(meAggressor));
        EngineApi.call(peaceData, "AI_UseVictoryPoints");
        Object peaceGameData = EngineApi.get(peaceData, "peaceTreatyGameData");
        EngineApi.call(EngineApi.cls(DIPLO), "sendPeaceTreaty", Boolean.valueOf(meAggressor), me, peaceGameData);
        return ok("peace_treaty", "OK|peaceTreaty|" + target, detail("target", target, "war_id", nWarID));
    }

    // ---- L1 外交全集 (T034，docs/mechanics.md L1，成本由引擎方法内校验扣除) ----

    /** sendGift|target|gold — DiplomacyManager.sendGift(引擎侧削至 25% 金、扣 8 外交点) */
    private static Result sendGift(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int gold = ps.containsKey("gold") ? intP(ps, "gold") : 0;
        EngineApi.call(EngineApi.cls(DIPLO), "sendGift", target, me(), gold);
        return ok("send_gift", "OK|sendGift|" + target + "|" + gold,
                detail("target", target, "gold", gold));
    }

    /** sendInsult|target|turns — 关系羞辱（decreaseRelation：外交点≥2、扣 2、闭馆 turns 回合） */
    private static Result sendInsult(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int turns = ps.containsKey("turns") ? intP(ps, "turns") : 5;
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "decreaseRelation",
                me(), target, turns)).booleanValue();
        if (okFlag) {
            return ok("send_insult", "OK|sendInsult|" + target, detail("target", target, "turns", turns));
        }
        return fail("send_insult", "FAIL|sendInsult|" + target + "|外交点不足或非玩家");
    }

    /** tradeRequest|target|gold — SendTradeRequest_GameData(iCivLEFT=me, listLEFT.iGold=gold) → sendTradeRequest (扣 10 外交点) */
    private static Result tradeRequest(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int gold = ps.containsKey("gold") ? intP(ps, "gold") : 0;
        int me = me();
        Object data = EngineApi.newInst(EngineApi.cls(TRADE_REQUEST));
        Object left = EngineApi.newInst(EngineApi.cls(TRADE_REQUEST_LIST));
        EngineApi.set(left, "iGold", gold);
        EngineApi.set(data, "iCivLEFT", me);
        EngineApi.set(data, "iCivRIGHT", target);
        EngineApi.set(data, "listLEFT", left);
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "sendTradeRequest",
                target, me, data)).booleanValue();
        if (okFlag) {
            return ok("trade_request", "OK|tradeRequest|" + target + "|" + gold,
                    detail("target", target, "gold", gold));
        }
        return fail("trade_request", "FAIL|tradeRequest|" + target + "|外交点不足(需≥10)");
    }

    /** buyWar|target|warOn|gold — 给金(LEFT)买战争：要求 target 对 warOn 宣战
     *  (RIGHT.iDeclarWarOnCivID -> acceptTradeRequest 引擎强制 declareWar(target, warOn)). */
    private static Result buyWar(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int warOn = intP(ps, "declare_war_on", "warOn");
        int gold = intP(ps, "gold");
        int me = me();
        Object data = EngineApi.newInst(EngineApi.cls(TRADE_REQUEST));
        Object left = EngineApi.newInst(EngineApi.cls(TRADE_REQUEST_LIST));
        Object right = EngineApi.newInst(EngineApi.cls(TRADE_REQUEST_LIST));
        EngineApi.set(left, "iGold", gold);
        EngineApi.set(right, "iDeclarWarOnCivID", warOn);
        EngineApi.set(data, "iCivLEFT", me);
        EngineApi.set(data, "iCivRIGHT", target);
        EngineApi.set(data, "listLEFT", left);
        EngineApi.set(data, "listRight", right);
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "sendTradeRequest",
                target, me, data)).booleanValue();
        if (okFlag) {
            return ok("buy_war", "OK|buyWar|" + target + "|" + warOn + "|" + gold,
                    detail("target", target, "declare_war_on", warOn, "gold", gold));
        }
        return fail("buy_war", "FAIL|buyWar|" + target + "|外交点不足(需≥10)");
    }

    /** setBudget|tax|goods|research|invest — Budget 面板滑块（玩家等价）:
     *  setTaxationLevel 0..1, setSpendings_Goods/Research/Investments, 随后刷新预算。 */
    private static Result setBudget(Map<String, Object> ps) {
        int me = me();
        Object civ = civ(me);
        float tax = intP(ps, "tax") / 100.0f;
        float goods = intP(ps, "goods") / 100.0f;
        float research = intP(ps, "research") / 100.0f;
        float invest = intP(ps, "invest") / 100.0f;
        EngineApi.call(civ, "setTaxationLevel", Float.valueOf(tax));
        EngineApi.call(civ, "setSpendings_Goods", Float.valueOf(goods));
        EngineApi.call(civ, "setSpendings_Research", Float.valueOf(research));
        EngineApi.call(civ, "setSpendings_Investments", Float.valueOf(invest));
        try {
            int budget = ((Number) EngineApi.get(civ, "iBudget")).intValue();
            EngineApi.call(EngineApi.cls("age.of.civilizations2.jakowski.lukasz.Game_NextTurnUpdate"),
                    "updateSpendingsOfCiv", me, Integer.valueOf(budget));
            EngineApi.call(EngineApi.cls("age.of.civilizations2.jakowski.lukasz.Game_NextTurnUpdate"),
                    "getBalance_UpdateBudget_Prepare", Integer.valueOf(me));
        } catch (Throwable refreshIgnored) {
        }
        return ok("set_budget",
                "OK|setBudget|tax=" + ((Number) EngineApi.call(civ, "getTaxationLevel")).floatValue()
                        + "|goods=" + ((Number) EngineApi.call(civ, "getSpendings_Goods")).floatValue()
                        + "|research=" + ((Number) EngineApi.call(civ, "getSpendings_Research")).floatValue()
                        + "|invest=" + ((Number) EngineApi.call(civ, "getSpendings_Investments")).floatValue(),
                detail("tax_pct", tax * 100, "goods_pct", goods * 100,
                        "research_pct", research * 100, "invest_pct", invest * 100));
    }

    /** guaranteeIndependence|target|turns — 保对方独立（-10 点；对方被宣战→我方自动参战 Game.java:9918）. */
    private static Result guaranteeIndependence(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int turns = ps.containsKey("turns") ? intP(ps, "turns") : 100;
        int me = me();
        EngineApi.call(EngineApi.cls(DIPLO), "sendGuaranteeIndependence_AskProposal",
                target, me, Integer.valueOf(turns));
        return ok("guarantee_independence", "OK|guaranteeIndependence|" + target + "|" + turns,
                detail("target_civ_id", target, "turns", turns));
    }

    /** unionProposal|target — 提议联合统治（-22 点；同盟基础 + CFG.createUnion 合并版图）. */
    private static Result unionProposal(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int me = me();
        EngineApi.call(EngineApi.cls(DIPLO), "sendUnionProposal", target, me);
        return ok("union_proposal", "OK|unionProposal|" + target,
                detail("target_civ_id", target));
    }

    /** coalitionWar|target|against|gold — 给金组联合阵线：双方对 against 宣战 + NAP40 + 军事通行40. */
    private static Result coalitionWar(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int against = intP(ps, "coalition_against", "against");
        int gold = intP(ps, "gold");
        int me = me();
        Object data = EngineApi.newInst(EngineApi.cls(TRADE_REQUEST));
        Object left = EngineApi.newInst(EngineApi.cls(TRADE_REQUEST_LIST));
        Object right = EngineApi.newInst(EngineApi.cls(TRADE_REQUEST_LIST));
        EngineApi.set(left, "iGold", gold);
        EngineApi.set(right, "iFormCoalitionAgainst", against);
        EngineApi.set(data, "iCivLEFT", me);
        EngineApi.set(data, "iCivRIGHT", target);
        EngineApi.set(data, "listLEFT", left);
        EngineApi.set(data, "listRight", right);
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "sendTradeRequest",
                target, me, data)).booleanValue();
        if (okFlag) {
            return ok("coalition_war", "OK|coalitionWar|" + target + "|" + against + "|" + gold,
                    detail("target", target, "coalition_against", against, "gold", gold));
        }
        return fail("coalition_war", "FAIL|coalitionWar|" + target + "|外交点不足(需≥10)");
    }

    /** nonAggressionPact|target — 互不侵犯 40 回合（扣 8 外交点） */
    private static Result nonAggressionPact(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        EngineApi.call(EngineApi.cls(DIPLO), "sendNonAggressionProposal", target, me(), Integer.valueOf(40));
        return ok("nonaggression_pact", "OK|nonAggressionPact|" + target, detail("target", target, "turns", 40));
    }

    /** offerVasalization|target — 附庸化请求（扣 16 外交点） */
    private static Result offerVasalization(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        EngineApi.call(EngineApi.cls(DIPLO), "sendOfferVasalizationProposal", target, me(), Integer.valueOf(16));
        return ok("offer_vasalization", "OK|offerVasalization|" + target, detail("target", target));
    }

    /** militaryAccessAsk|target — 请求军事通行 40 回合（外交点≥10、扣 10） */
    private static Result militaryAccessAsk(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        EngineApi.call(EngineApi.cls(DIPLO), "sendMilitaryAccess_AskProposal", target, me(), Integer.valueOf(40));
        return ok("military_access_ask", "OK|militaryAccessAsk|" + target, detail("target", target, "turns", 40));
    }

    /** militaryAccessGive|target — 授予军事通行 40 回合（扣 4 外交点） */
    private static Result militaryAccessGive(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        EngineApi.call(EngineApi.cls(DIPLO), "sendMilitaryAccess_GiveProposal", target, me(), Integer.valueOf(40));
        return ok("military_access_give", "OK|militaryAccessGive|" + target, detail("target", target, "turns", 40));
    }

    /** improveRelations|target — 关系升级（improveRelation：外交点≥5 且未交战） */
    private static Result improveRelations(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "improveRelation",
                me(), target)).booleanValue();
        if (okFlag) {
            return ok("improve_relations", "OK|improveRelations|" + target, detail("target", target));
        }
        return fail("improve_relations", "FAIL|improveRelations|" + target + "|外交点<5 或交战/使馆关闭");
    }

    /** decreaseRelations|target|turns — 关系恶化（外交点≥2、扣 2、闭馆 turns 回合） */
    private static Result decreaseRelations(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int turns = ps.containsKey("turns") ? intP(ps, "turns") : 5;
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "decreaseRelation",
                me(), target, turns)).booleanValue();
        if (okFlag) {
            return ok("decrease_relations", "OK|decreaseRelations|" + target, detail("target", target, "turns", turns));
        }
        return fail("decrease_relations", "FAIL|decreaseRelations|" + target + "|外交点不足");
    }

    /** supportRebels|target|gold|rebel_civ_id? — 支持叛军（外交点≥34、扣 34；rebel 缺省取首个候选） */
    private static Result supportRebels(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int gold = intP(ps, "gold");
        int me = me();
        int rebel = -1;
        if (ps.containsKey("rebel_civ_id")) {
            rebel = intP(ps, "rebel_civ_id");
        } else {
            try {
                Object data = EngineApi.call(EngineApi.cls(DIPLO), "supportRebels", target);
                Object movements = EngineApi.get(data, "lMovements");
                if (movements instanceof List && !((List<?>) movements).isEmpty()) {
                    rebel = ((Number) ((List<?>) movements).get(0)).intValue();
                }
            } catch (Throwable ignored) {
            }
        }
        if (rebel <= 0) {
            return fail("support_rebels", "FAIL|supportRebels|" + target + "|no rebel civ");
        }
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "supportRebels",
                me, target, rebel, gold)).booleanValue();
        if (okFlag) {
            return ok("support_rebels", "OK|supportRebels|" + target + "|" + rebel,
                    detail("target", target, "rebel_civ_id", rebel, "gold", gold));
        }
        return fail("support_rebels", "FAIL|supportRebels|" + target + "|外交点<34 或无金");
    }

    /** ultimatum|target — 通牒吞并（关系≤−10 且对方为傀儡：外交点≥24、扣 24） */
    private static Result ultimatum(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int me = me();
        Object data = EngineApi.newInst(EngineApi.cls(ULTIMATUM));
        EngineApi.set(data, "demandAnexation", Boolean.TRUE);
        int units = ((Integer) EngineApi.call(civ(me), "getNumOfUnits")).intValue();
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "sendUltimatum",
                target, me, data, units)).booleanValue();
        if (okFlag) {
            return ok("ultimatum", "OK|ultimatum|" + target, detail("target", target, "units", units));
        }
        return fail("ultimatum", "FAIL|ultimatum|" + target + "|关系需≤−10 且外交点≥24");
    }

    /** civilize|target — 开化目标文明（外交点≥10、科技达标；扣 10） */
    private static Result civilize(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "civilizeCiv", target)).booleanValue();
        if (okFlag) {
            return ok("civilize", "OK|civilize|" + target, detail("target", target));
        }
        return fail("civilize", "FAIL|civilize|" + target + "|外交点<10 或不满足开化条件");
    }

    /** formCivilization — 组建可用文明（CFG.formCiv(me)；扣 1000 金 + 24 外交点） */
    private static Result formCivilization(Map<String, Object> ps) {
        EngineApi.call(EngineApi.cls(CFG), "formCiv", me());
        return ok("form_civilization", "OK|formCiv", null);
    }

    /** proclaimIndependence|target|turns — 独立宣言（保障请求：扣 10 外交点，默认 40 回合） */
    private static Result proclaimIndependence(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int turns = ps.containsKey("turns") ? intP(ps, "turns") : 40;
        EngineApi.call(EngineApi.cls(DIPLO), "sendGuaranteeIndependence_AskProposal",
                target, me(), turns);
        return ok("proclaim_independence", "OK|proclaimIndependence|" + target,
                detail("target", target, "turns", turns));
    }

    /** prepareForWar|target|against|turns — 通知盟友备战（AI 同款 sendPrepareForWar） */
    private static Result prepareForWar(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int against = intP(ps, "against_civ_id", "against");
        int turns = ps.containsKey("turns") ? intP(ps, "turns") : 4;
        int me = me();
        EngineApi.call(EngineApi.cls(DIPLO), "sendPrepareForWar", target, me, against, turns, me);
        return ok("prepare_for_war", "OK|prepareForWar|" + target + "|against|" + against,
                detail("target", target, "against_civ_id", against, "turns", turns));
    }

    /** callToArms|target|against — 号召盟友参战（sendCallToArms） */
    private static Result callToArms(Map<String, Object> ps) {
        int target = intP(ps, "target_civ_id", "target", "civ_id", "civ");
        int against = intP(ps, "against_civ_id", "against");
        EngineApi.call(EngineApi.cls(DIPLO), "sendCallToArms", target, me(), against);
        return ok("call_to_arms", "OK|callToArms|" + target + "|against|" + against,
                detail("target", target, "against_civ_id", against));
    }

    // ---- 内政三动作 (T035，docs/mechanics.md L1；前置校验由引擎方法内置) ----

    /** assimilate|province|turns — 同化（己方省/未占领/外交点≥6/钱≥cost；扣 6 外 + cost 金） */
    private static Result assimilate(Map<String, Object> ps) {
        int province = intP(ps, "province_id", "province");
        int turns = ps.containsKey("num_of_turns") ? intP(ps, "num_of_turns") : 10;
        int me = me();
        int cost = 0;
        try {
            cost = ((Number) EngineApi.call(EngineApi.cls(DIPLO), "assimilateCost", province, turns)).intValue();
        } catch (Throwable ignored) {
        }
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "addAssimilate",
                me, province, turns)).booleanValue();
        if (okFlag) {
            return ok("assimilate", "OK|assimilate|" + province + "|" + turns,
                    detail("province_id", province, "num_of_turns", turns, "cost", cost));
        }
        return fail("assimilate", "FAIL|assimilate|" + province + "|外交点<6/钱不足/非己有/已占领");
    }

    /** festival|province — 节日（行动点≥8 + 钱≥festivalCost；扣 8 行动点 + cost 金） */
    private static Result festival(Map<String, Object> ps) {
        int province = intP(ps, "province_id", "province");
        int me = me();
        int cost = 0;
        try {
            cost = ((Number) EngineApi.call(EngineApi.cls(DIPLO), "festivalCost", province)).intValue();
        } catch (Throwable ignored) {
        }
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO), "addFestival",
                me, province)).booleanValue();
        if (okFlag) {
            return ok("festival", "OK|festival|" + province, detail("province_id", province, "cost", cost));
        }
        return fail("festival", "FAIL|festival|" + province + "|行动点<8/钱不足/非己有");
    }

    /** colonize|province — 殖民荒芜省（殖民递进：外交点≥14 + 行动点 + 钱 + 邻接/军；科技<0.8 惩罚 ×8.25） */
    private static Result colonize(Map<String, Object> ps) {
        int province = intP(ps, "province_id", "province");
        int me = me();
        boolean okFlag = ((Boolean) EngineApi.call(EngineApi.cls(DIPLO),
                "colonizeWastelandProvince", province, me)).booleanValue();
        if (okFlag) {
            return ok("colonize", "OK|colonize|" + province, detail("province_id", province));
        }
        return fail("colonize", "FAIL|colonize|" + province + "|行动点/外交点<14/钱不足/非荒芜或无可达");
    }

    /** newGame — legacy AgentBridge "newGame" case (idempotency guard ported) */
    private static Result newGame() {
        try {
            // idempotency guard: a repeated call after the view switch has
            // happened must not reset the game a second time
            if (((Boolean) EngineApi.call(menuManager(), "getInGameView")).booleanValue()
                    || ((Boolean) EngineApi.call(menuManager(), "getInStartGameMenu")).booleanValue()) {
                return ok("new_game", "OK|newGame|already-in-game", null);
            }
            EngineApi.call(EngineApi.call(menuManager(), "getColorPicker"), "setVisible", Boolean.FALSE, null);
            EngineApi.call(EngineApi.cls(RTS), "reset");
            EngineApi.call(game(), "disableDrawCivlizationsRegions_Players");
            EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "viewsManager"), "disableAllViews");
            Object scaleCurrent = EngineApi.call(EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "map"), "getMapScale"), "getCurrentScale");
            float std = ((Float) EngineApi.get(EngineApi.cls(MAP_SCALE), "STANDARD_SCALE")).floatValue();
            if (((Float) scaleCurrent).floatValue() < std) {
                EngineApi.call(EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "map"), "getMapScale"), "setCurrentScale", Float.valueOf(std));
            }
            EngineApi.call(gameNewGame(), "newGame");
            EngineApi.set(EngineApi.cls(CFG), "startTheGameData",
                    EngineApi.newInst(EngineApi.cls(START_THE_GAME_DATA), Boolean.FALSE));
            EngineApi.call(menuManager(), "setViewIDWithoutAnimation",
                    EngineApi.enumConst(MENU, "eSTART_THE_GAME"));
            return ok("new_game", "OK|newGame", null);
        } catch (Throwable t) {
            return fail("new_game", "ERR|newGame|" + t.getClass().getSimpleName());
        }
    }

    /** endTurn — legacy "endTurn" case */
    private static Result endTurn() {
        try {
            EngineApi.set(EngineApi.get(EngineApi.cls(CFG), "settingsManager"), "CONFIRM_END_TURN", Boolean.FALSE);
            EngineApi.set(EngineApi.get(EngineApi.cls(CFG), "settingsManager"), "CONFIRM_NO_ORDERS", Boolean.FALSE);
        } catch (Throwable ignored) {
        }
        EngineApi.call(gameAction(), "tryToTakeNexTurn");
        return ok("end_turn", "OK|endTurn", null);
    }

    /** enterGodView — legacy "enterGodView" case */
    private static Result enterGodView() {
        try {
            EngineApi.set(EngineApi.cls(CFG), "FOG_OF_WAR", Integer.valueOf(0));
            EngineApi.call(gameAction(), "buildFogOfWar", Integer.valueOf(0));
            return ok("enter_god_view", "OK|enterGodView", null);
        } catch (Throwable t) {
            return fail("enter_god_view", "ERR|enterGodView|" + t.getClass().getSimpleName());
        }
    }

    /** respondMessages — legacy "respondMessages" case */
    private static Result respondMessages() {
        int me = me();
        int n = 0;
        try {
            Object messageBox = EngineApi.get(
                    EngineApi.call(civ(me), "getCivilization_Diplomacy_GameData"), "messageBox");
            while (((Integer) EngineApi.call(messageBox, "getMessagesSize")).intValue() > 0) {
                int last = ((Integer) EngineApi.call(messageBox, "getMessagesSize")).intValue() - 1;
                EngineApi.call(messageBox, "removeMessage", last);
                ++n;
            }
        } catch (Throwable t) {
            return fail("respond_messages", "ERR|respondMessages|" + t.getClass().getSimpleName());
        }
        return ok("respond_messages", "OK|respondMessages|" + n, "{\"removed\":" + n + "}");
    }

    /** loadGame|idx — legacy "loadGame" case */
    private static Result loadGame(Map<String, Object> ps) {
        int idx = intP(ps, "save_index", "index", "idx");
        try {
            EngineApi.call(gameNewGame(), "loadGame", idx);
            EngineApi.call(EngineApi.cls(RTS), "reset");
            EngineApi.call(game(), "disableDrawCivlizationsRegions_Players");
            EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "viewsManager"), "disableAllViews");
            Object scaleCurrent = EngineApi.call(EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "map"), "getMapScale"), "getCurrentScale");
            float std = ((Float) EngineApi.get(EngineApi.cls(MAP_SCALE), "STANDARD_SCALE")).floatValue();
            if (((Float) scaleCurrent).floatValue() < std) {
                EngineApi.call(EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "map"), "getMapScale"), "setCurrentScale", Float.valueOf(std));
            }
            Object savedGameTag = EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "langManager"), "get", "SavedGame");
            EngineApi.set(EngineApi.cls(CFG), "EDITOR_ACTIVE_GAMEDATA_TAG", savedGameTag == null ? "SavedGame" : savedGameTag.toString());
            EngineApi.set(EngineApi.cls(CFG), "startTheGameData",
                    EngineApi.newInst(EngineApi.cls(START_THE_GAME_DATA), Boolean.FALSE));
            EngineApi.call(menuManager(), "setViewIDWithoutAnimation",
                    EngineApi.enumConst(MENU, "eSTART_THE_GAME"));
            return ok("load_game", "OK|loadGame|" + idx, detail("index", idx));
        } catch (Throwable t) {
            return fail("load_game", "ERR|loadGame|" + t.getClass().getSimpleName());
        }
    }

    /** listSaves — legacy "listSaves" case (saves/games/<map>Age_of_Civilizations) */
    private static Result listSaves() {
        StringBuilder out = new StringBuilder();
        try {
            String mapPath = (String) EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "map"), "getFile_ActiveMap_Path");
            File f = new File("saves/games/" + mapPath + "Age_of_Civilizations");
            BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(f), "UTF-8"));
            String line = br.readLine();
            br.close();
            if (line != null) {
                String[] tags = line.split(";");
                List<String> entries = new ArrayList<String>();
                for (int i = 0; i < tags.length; ++i) {
                    entries.add(i + ":" + tags[i]);
                }
                StringBuilder detail = new StringBuilder("{\"saves\":[");
                for (int i = 0; i < entries.size(); ++i) {
                    if (i > 0) {
                        detail.append(',');
                    }
                    detail.append(Json.quote(entries.get(i)));
                }
                detail.append("]}");
                return ok("list_saves", "SAVES|" + join(out, entries), detail.toString());
            }
        } catch (Throwable e) {
            return ok("list_saves", "SAVES|ERR:" + e.getClass().getSimpleName(), "{\"saves\":[]}");
        }
        return ok("list_saves", "SAVES|", "{\"saves\":[]}");
    }

    private static String join(StringBuilder sb, List<String> list) {
        for (int i = 0; i < list.size(); ++i) {
            if (i > 0) {
                sb.append('|');
            }
            sb.append(list.get(i));
        }
        return sb.toString();
    }

    /** toast|text — CFG.toast.setInView(text, color) */
    private static Result toast(Map<String, Object> ps) {
        String text = strP(ps, "text", "message");
        try {
            com.badlogic.gdx.graphics.Color gold = new com.badlogic.gdx.graphics.Color(0.95f, 0.75f, 0.25f, 1.0f);
            EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "toast"), "setInView", text, gold);
            EngineApi.call(EngineApi.get(EngineApi.cls(CFG), "toast"), "setTimeInView", Integer.valueOf(4000));
            return ok("toast", "OK|toast", null);
        } catch (Throwable t) {
            return fail("toast", "ERR|toast|" + t.getClass().getSimpleName());
        }
    }

    // ---- small helpers ----

    private static String detail(Object... kvPairs) {
        StringBuilder sb = new StringBuilder("{");
        for (int i = 0; i + 1 < kvPairs.length; i += 2) {
            if (i > 0) {
                sb.append(',');
            }
            Object k = kvPairs[i];
            Object v = kvPairs[i + 1];
            sb.append(Json.quote(k == null ? "" : k.toString())).append(':');
            if (v instanceof Number) {
                sb.append(v.toString());
            } else if (v instanceof Boolean || v == null) {
                sb.append(v == null ? "null" : v.toString());
            } else {
                sb.append(Json.quote(v.toString()));
            }
        }
        return sb.append('}').toString();
    }
}
