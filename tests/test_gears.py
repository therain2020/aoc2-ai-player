"""Gear -> engine-API policy tests (2026-08-29 user critique: gear 4 was recruit-loop)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.mechanics import gears
from agent.mechanics.prompts import build_plan_system


def test_gear_index_parse():
    assert gears.gear_index("④疯狂扩张：全力军事化，持续战争扩张") == 4
    assert gears.gear_index("【用户战略指示】⑤外交结盟：积极结盟，借力扩张") == 5
    assert gears.gear_index("随便写的文本") is None
    assert gears.gear_index("") is None


def test_gear_policies_reference_only_blacklisted_ops():
    from agent.actions import ACTION_SPEC
    for idx, p in gears.GEAR_POLICY.items():
        ops = p["ops"] + p["diplo"]
        for each in ops:
            assert each in ACTION_SPEC, (idx, each)
        assert p["war"] and p["taboo"] and p["pulse"], idx


def test_gear4_is_war_loop_not_recruit_loop():
    p = gears.GEAR_POLICY[4]
    assert "declare_war" in p["ops"] and "assimilate" in p["ops"] and "support_rebels" in p["ops"]
    assert "连续 2 计划净省 0" in p["taboo"]           # 纯征兵=不合格
    assert "同化窗口" in p["war"] or "同化" in p["war"]


def test_gear4_uses_trade_war_incitement_api():
    p = gears.GEAR_POLICY[4]
    assert "buy_war" in p["war"] and "declare_war_on" in p["war"]   # 花钱挑拨 = 交易机制 API
    assert "coalition_war" in p["war"] or "coalition_war" in p["ops"]
    from agent.actions import ACTION_SPEC
    assert "buy_war" in ACTION_SPEC and "coalition_war" in ACTION_SPEC
    assert {"target_civ_id", "declare_war_on", "gold"} <= set(ACTION_SPEC["buy_war"])


def test_plan_prompt_injects_gear_policy():
    sys = build_plan_system(4)
    assert "【当前档位执行要点】" in sys
    assert "连续战争" in sys or "战争" in sys
    assert "support_rebels" in sys
    plain = build_plan_system(None)
    assert "【当前档位执行要点】" not in plain or plain.count("【当前档位执行要点】") == 0


def test_gear_text_synced_with_dashboard_source():
    # dashboard imports GEARS = GEAR_TEXT; verify canonical list count
    assert len(gears.GEAR_TEXT) == 6
    assert all(t.startswith("①") or all(c in "①②③④⑤⑥" for c in t[0]) for t in gears.GEAR_TEXT)
