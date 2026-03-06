
import re

path = "/home/remvelchio/agent/anchor_cycler.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print("original lines:", content.count("\n"))

content = content.replace(
    "from safe_search import get_policy_context, is_sensitive_topic",
    "from safe_search import get_policy_context, is_sensitive_topic\nfrom concurrent.futures import ThreadPoolExecutor\ntry:\n    import eigentrace\n    EIGENTRACE_AVAILABLE = True\nexcept ImportError:\n    EIGENTRACE_AVAILABLE = False",
    1
)

content = content.replace(
    "        self.last_pair_stances = []",
    "        self.last_pair_stances = []\n\n        # EigenTrace state\n        self.last_vance_metrics = None\n        self.last_vance_text = None\n        self.last_wire_text = None\n        self.last_ddg_report = None\n        self._ddg_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=\"ddg\")",
    1
)

ET_BLOCK = """
        # EigenTrace integration
        wire_text = (story.get("title","") + " " + story.get("summary","")).strip()
        is_vance = anchor.name == "Anchor A"
        is_responder = anchor.name in ("Anchor B", "Anchor C", "Anchor D", "Anchor E")
        is_synthesis = self.phase == "synthesis"

        if EIGENTRACE_AVAILABLE:
            if is_vance and self.last_vance_text:
                result = eigentrace.analyze(self.last_vance_text, model, "Anchor A")
                if result:
                    self.last_vance_metrics = result.metrics
                    self.last_wire_text = wire_text
                    title = story.get("title", "")
                    vance_snap = self.last_vance_text
                    def _run_ddg(t, v):
                        try:
                            return eigentrace.ddg_research_desk(t, v)
                        except Exception:
                            return "RESEARCH DESK: offline."
                    self._ddg_future = self._ddg_executor.submit(_run_ddg, title, vance_snap)

            if is_responder and self.last_vance_metrics is not None:
                ddg_report = "RESEARCH DESK: pending."
                if hasattr(self, "_ddg_future"):
                    try:
                        ddg_report = self._ddg_future.result(timeout=0.1)
                        self.last_ddg_report = ddg_report
                    except Exception:
                        ddg_report = self.last_ddg_report or "RESEARCH DESK: pending."
                prior_exchange = " | ".join([
                    m["anchor"] + ": " + m["text"][:80]
                    for m in self.story_memory[-3:]
                    if m["anchor"] != anchor.name
                ])
                eigenprompt = eigentrace.build_response_prompt(
                    anchor.name,
                    self.last_wire_text or wire_text,
                    self.last_vance_text or "",
                    self.last_vance_metrics,
                    ddg_report,
                    prior_exchange
                )
                prompt = (
                    eigenprompt + "\\n\\n"
                    "BROADCAST FORMAT RULES:\\n"
                    "- Write 8-12 short sentences in one paragraph.\\n"
                    "- Keep sentences under 16 words.\\n"
                    "- End with: And that is the setup -- back to you.\\n"
                    "- Do NOT include your name or labels in the output.\\n"
                    "- No repetition of what other anchors already said.\\n"
                )
                _host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
                _timeout = float(os.environ.get("OLLAMA_TIMEOUT", "60"))
                _payload = {
                    "model": model, "prompt": prompt, "stream": False, "keep_alive": "5m",
                    "options": {"num_predict": 280, "temperature": 1.2, "top_p": 0.92, "repeat_penalty": 1.1}
                }
                try:
                    _req = urllib.request.Request(
                        _host + "/api/generate",
                        data=json.dumps(_payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(_req, timeout=_timeout) as _resp:
                        _data = json.load(_resp)
                    _text = _data.get("response", "").strip()
                    if _text:
                        _text = re.sub(r"^(Anchor\s+[A-Z]:\s*)", "", _text, flags=re.IGNORECASE).strip()
                        _text = re.sub(r"^(Anchor\s+[A-Z]\s+here\.?\s*)", "", _text, flags=re.IGNORECASE).strip()
                        _text = re.sub(r"(Headline:|Summary:|Source:|Extra context URLs:).*", "", _text, flags=re.IGNORECASE|re.DOTALL).strip()
                        return _text
                except Exception as _exc:
                    self.logger.warning("EigenTrace responder path failed: %s", _exc)

            if is_synthesis and self.last_vance_metrics is not None and self.last_vance_text:
                full_exchange = " | ".join([
                    m["anchor"] + ": " + m["text"][:100]
                    for m in self.story_memory[-6:]
                ])
                synth_prompt = eigentrace.build_synthesis_prompt(
                    self.last_wire_text or wire_text,
                    self.last_vance_text,
                    full_exchange,
                    self.last_vance_metrics
                )
                _host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
                _timeout = float(os.environ.get("OLLAMA_TIMEOUT", "60"))
                _payload = {
                    "model": model, "prompt": synth_prompt, "stream": False, "keep_alive": "5m",
                    "options": {"num_predict": 120, "temperature": 0.7, "top_p": 0.9}
                }
                try:
                    _req = urllib.request.Request(
                        _host + "/api/generate",
                        data=json.dumps(_payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(_req, timeout=_timeout) as _resp:
                        _data = json.load(_resp)
                    _text = _data.get("response", "").strip()
                    if _text:
                        return _text
                except Exception as _exc:
                    self.logger.warning("EigenTrace synthesis path failed: %s", _exc)
        # end EigenTrace
"""

content = content.replace(
    '        model = os.environ.get("OLLAMA_MODEL", "mistral:latest")',
    '        model = os.environ.get("OLLAMA_MODEL", "mistral:latest")' + ET_BLOCK,
    1
)

old_return = '            return text\n        except Exception as exc:\n            self.logger.warning("LLM commentary failed: %s", exc)'
new_return = '            if EIGENTRACE_AVAILABLE and anchor.name == "Anchor A":\n                self.last_vance_text = text\n            return text\n        except Exception as exc:\n            self.logger.warning("LLM commentary failed: %s", exc)'
content = content.replace(old_return, new_return, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("patched lines:", content.count("\n"))
checks = [
    ("EIGENTRACE_AVAILABLE", "eigentrace import guard"),
    ("_ddg_executor", "DDG thread pool"),
    ("build_response_prompt", "responder prompt"),
    ("build_synthesis_prompt", "synthesis prompt"),
    ("last_vance_text = text", "vance text storage"),
]
for key, label in checks:
    print(("OK  " if key in content else "FAIL"), label)
