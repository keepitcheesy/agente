
import sys, os, time
sys.path.insert(0, "/home/remvelchio/agent")
os.chdir("/home/remvelchio/agent")

import yaml
from anchor_cycler import AnchorCycler

with open("config.yaml") as f:
    config = yaml.safe_load(f)

anchors = config["anchors"]["cycle_order"]
cycler = AnchorCycler(anchors)

story = {
    "title": "OpenAI releases GPT-5 with real-time reasoning and tool use",
    "summary": "OpenAI has announced GPT-5, claiming major advances in multi-step reasoning, live web access, and autonomous tool execution. Critics warn of safety risks.",
    "source": "TechCrunch",
    "url": "https://example.com"
}

phases = [
    ("lead",       "Anchor A", "neutral",  False),
    ("analysis_b", "Anchor B", "skeptical", False),
    ("analysis_c", "Anchor C", "bullish",   False),
    ("analysis_d", "Anchor D", "cultural",  False),
    ("roundtable", "Anchor E", "synthesis", True),
]

context_lines = []

print("=" * 60)
print(f"STORY: {story['title']}")
print("=" * 60)

for phase, anchor_name, stance, synthesize in phases:
    cycler.set_phase(phase)
    anchor = next(a for a in cycler.anchors if a.name == anchor_name)
    cycler.current_anchor = anchor

    print(f"\n--- {anchor_name} [{phase}] ---")
    t0 = time.time()
    text = cycler._generate_llm_commentary(
        story, anchor,
        stance=stance,
        prev_summary="",
        synthesize=synthesize,
        context_lines=context_lines,
        sensitive=False
    )
    elapsed = time.time() - t0
    print(f"[{elapsed:.1f}s] {text}")
    if text:
        context_lines.append(f"{anchor_name}: {text[:80]}")

print("\n" + "=" * 60)
print("EigenTrace state after run:")
print(f"  last_vance_text    : {repr(cycler.last_vance_text[:80]) if cycler.last_vance_text else None}")
print(f"  last_vance_metrics : {cycler.last_vance_metrics}")
print(f"  last_wire_text     : {repr(cycler.last_wire_text)}")
print(f"  last_ddg_report    : {repr(str(cycler.last_ddg_report)[:120]) if cycler.last_ddg_report else None}")
print("=" * 60)
