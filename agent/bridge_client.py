"""HTTP client for AgentBridge (in-game control bridge)."""
import time
import urllib.parse
import urllib.request

# EngineGateway (source-level bridge, T014): port unified to 7187; legacy 9110 retired.
DEFAULT_PORT = 7187


class BridgeError(RuntimeError):
    pass


class BridgeClient:
    def __init__(self, port: int = DEFAULT_PORT, host: str = "127.0.0.1", timeout: float = 5.0):
        self.base = f"http://{host}:{port}"
        self.timeout = timeout

    def _get(self, path: str) -> str:
        try:
            with urllib.request.urlopen(self.base + path, timeout=self.timeout) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            raise BridgeError(f"bridge unreachable: {e}") from e

    def ping(self) -> bool:
        try:
            return self._get("/ping").strip() == "pong"
        except BridgeError:
            return False

    def state(self) -> str:
        return self._get("/state")

    def action(self, cmd: str) -> str:
        return self._get("/action?cmd=" + urllib.parse.quote(cmd, safe=""))

    def narration(self, text: str) -> str:
        return self._get("/narration?text=" + urllib.parse.quote(text, safe=""))

    # ---- semantic wrappers (mirror engine API) ----

    def declare_war(self, target_civ_id: int) -> str:
        return self.action(f"declareWar|{target_civ_id}")

    def recruit_army(self, province_id: int, count: int) -> str:
        return self.action(f"recruitArmy|{province_id}|{count}")

    def move_army(self, from_province: int, to_province: int, count: int) -> str:
        return self.action(f"moveArmy|{from_province}|{to_province}|{count}")

    def invest(self, province_id: int, gold: int) -> str:
        return self.action(f"invest|{province_id}|{gold}")

    def end_turn(self) -> str:
        return self.action("endTurn")

    def respond_messages(self) -> str:
        return self.action("respondMessages")

    def hud(self, line1: str = "", line2: str = "", line3: str = "",
            line4: str = "", line5: str = "") -> str:
        return self._get("/hud?l1=" + urllib.parse.quote(line1, safe="")
                         + "&l2=" + urllib.parse.quote(line2, safe="")
                         + "&l3=" + urllib.parse.quote(line3, safe="")
                         + "&l4=" + urllib.parse.quote(line4, safe="")
                         + "&l5=" + urllib.parse.quote(line5, safe=""))

    def enter_god_view(self) -> str:
        return self.action("enterGodView")

    def load_game(self, index: int) -> str:
        return self.action(f"loadGame|{index}")

    def new_game(self) -> str:
        return self.action("newGame")

    def invest_tech(self, category: str, count: int = 1) -> str:
        return self.action(f"investTech|{category}|{count}")

    def disband_army(self, province_id: int, count: int) -> str:
        return self.action(f"disbandArmy|{province_id}|{count}")

    def move_capital(self, province_id: int) -> str:
        return self.action(f"moveCapital|{province_id}")

    def offer_alliance(self, target_civ_id: int) -> str:
        return self.action(f"offerAlliance|{target_civ_id}")

    def invest_dev(self, province_id: int, gold: int) -> str:
        return self.action(f"investDev|{province_id}|{gold}")

    def construct(self, building_type: str, province_id: int) -> str:
        return self.action(f"construct|{building_type}|{province_id}")

    def peace_treaty(self, target_civ_id: int) -> str:
        return self.action(f"peaceTreaty|{target_civ_id}")

    # ---- L1 外交全集 (engine-api.md) ----

    def send_gift(self, target_civ_id: int, gold: int) -> str:
        return self.action(f"sendGift|{target_civ_id}|{gold}")

    def send_insult(self, target_civ_id: int) -> str:
        return self.action(f"sendInsult|{target_civ_id}")

    def trade_request(self, target_civ_id: int, gold: int) -> str:
        return self.action(f"tradeRequest|{target_civ_id}|{gold}")

    def nonaggression_pact(self, target_civ_id: int) -> str:
        return self.action(f"nonAggressionPact|{target_civ_id}")

    def offer_vasalization(self, target_civ_id: int) -> str:
        return self.action(f"offerVasalization|{target_civ_id}")

    def military_access_ask(self, target_civ_id: int) -> str:
        return self.action(f"militaryAccessAsk|{target_civ_id}")

    def military_access_give(self, target_civ_id: int) -> str:
        return self.action(f"militaryAccessGive|{target_civ_id}")

    def improve_relations(self, target_civ_id: int) -> str:
        return self.action(f"improveRelations|{target_civ_id}")

    def decrease_relations(self, target_civ_id: int) -> str:
        return self.action(f"decreaseRelations|{target_civ_id}")

    def support_rebels(self, target_civ_id: int, gold: int) -> str:
        return self.action(f"supportRebels|{target_civ_id}|{gold}")

    def ultimatum(self, target_civ_id: int) -> str:
        return self.action(f"ultimatum|{target_civ_id}")

    def civilize(self, target_civ_id: int) -> str:
        return self.action(f"civilize|{target_civ_id}")

    def form_civilization(self) -> str:
        return self.action("formCivilization")

    def proclaim_independence(self, target_civ_id: int) -> str:
        return self.action(f"proclaimIndependence|{target_civ_id}")

    def prepare_for_war(self, target_civ_id: int, against_civ_id: int, turns: int = 4) -> str:
        return self.action(f"prepareForWar|{target_civ_id}|{against_civ_id}|{turns}")

    def call_to_arms(self, target_civ_id: int, against_civ_id: int) -> str:
        return self.action(f"callToArms|{target_civ_id}|{against_civ_id}")

    # ---- 内政三动作 (T035) ----

    def assimilate(self, province_id: int, num_of_turns: int = 10) -> str:
        return self.action(f"assimilate|{province_id}|{num_of_turns}")

    def festival(self, province_id: int) -> str:
        return self.action(f"festival|{province_id}")

    def colonize(self, province_id: int) -> str:
        return self.action(f"colonize|{province_id}")

    def buy_war(self, target_civ_id: int, declare_war_on: int, gold: int) -> str:
        return self.action(f"buyWar|{target_civ_id}|{declare_war_on}|{gold}")

    def coalition_war(self, target_civ_id: int, coalition_against: int, gold: int) -> str:
        return self.action(f"coalitionWar|{target_civ_id}|{coalition_against}|{gold}")

    def set_budget(self, tax_pct: int, goods_pct: int, research_pct: int, invest_pct: int) -> str:
        return self.action(f"setBudget|{tax_pct}|{goods_pct}|{research_pct}|{invest_pct}")

    def push_plan(self, text: str) -> str:
        return self._get("/plan?text=" + urllib.parse.quote(text, safe=""))

    def toast(self, text: str) -> str:
        return self.narration(text)


def wait_until_up(port: int = DEFAULT_PORT, timeout_s: float = 120.0) -> BridgeClient:
    client = BridgeClient(port=port)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if client.ping():
            return client
        time.sleep(2.0)
    raise BridgeError(f"bridge not up within {timeout_s}s")
