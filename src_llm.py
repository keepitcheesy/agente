
import inspect, sys, os
sys.path.insert(0, "/home/remvelchio/agent")
os.chdir("/home/remvelchio/agent")

from anchor_cycler import AnchorCycler
import yaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)

cycler = AnchorCycler(config["anchors"]["cycle_order"])
print(inspect.getsource(cycler._generate_llm_commentary))
