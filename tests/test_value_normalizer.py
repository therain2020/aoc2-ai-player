"""Value normalizer tests (ledger-aware scaling — user critique)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.mechanics.value_normalizer import normalize_values


def test_recruit_scales_with_coffer():
    poor = normalize_values([{"action": "recruit_army", "province_id": 1, "count": 200}],
                            {"money": 5000})
    rich = normalize_values([{"action": "recruit_army", "province_id": 1, "count": 200}],
                            {"money": 67895})
    assert rich[0]["count"] > poor[0]["count"] >= 50
    assert rich[0]["count"] >= 500      # 67k coffer -> thousands, not 200


def test_invest_uses_15_percent_coffer():
    a = normalize_values([{"action": "invest", "province_id": 5, "gold": 500}], {"money": 67895})
    assert 10000 <= a[0]["gold"] <= 12000     # ~15% of 67k
    a2 = normalize_values([{"action": "invest_dev", "province_id": 5, "gold": 500}], {"money": 800})
    assert a2[0]["gold"] >= 300               # floor persists for small coffers


def test_gift_and_buywar_scale():
    a = normalize_values([{"action": "send_gift", "target_civ_id": 9, "gold": 500},
                          {"action": "buy_war", "target_civ_id": 9, "declare_war_on": 8, "gold": 500}],
                         {"money": 30000})
    assert a[0]["gold"] == 1500                # 5% cap
    assert a[1]["gold"] == 3000                # 10% cap


def test_unknown_actions_untouched():
    acts = [{"action": "move_army", "from_province": 1, "to_province": 2, "count": 300}]
    assert normalize_values(acts, {"money": 50000})[0]["count"] == 300
