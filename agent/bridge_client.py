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
