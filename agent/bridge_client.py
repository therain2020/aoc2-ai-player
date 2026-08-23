"""HTTP client for AgentBridge (in-game control bridge)."""
import time
import urllib.parse
import urllib.request

DEFAULT_PORT = 9110


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
