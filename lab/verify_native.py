#!/usr/bin/env python3
"""Run only the isolated fixture binary; capture and scroll its native texture."""
import hashlib, json, os, pathlib, shutil, socket, subprocess, sys, time, urllib.parse, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[1]
binary = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "target/debug/examples/viewer"
output = ROOT / "lab/evidence"
output.mkdir(parents=True, exist_ok=True)
report_path = output / "native-validation.json"
report_path.unlink(missing_ok=True)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
def request(path, **params):
    url = f"http://127.0.0.1:{port}{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)
env = dict(os.environ, MAKEPAD_REMOTE=str(port), MAKEPAD_HIDE_WINDOWS="1", MAKEPAD_NO_FOCUS="1")
with (output / "native-run.log").open("w") as log:
    app = subprocess.Popen([str(binary), *sys.argv[2:]], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(100):
            if app.poll() is not None:
                raise RuntimeError("Fixture app exited during startup")
            try:
                status = request("/s")
                assert status["pid"] == app.pid, "Bridge belongs to another process"
                if status["w"]:
                    rows = request("/snap")["s"]
                    if any("Ready · Offline HTML/CSS" in row.get("t", "") for row in rows):
                        break
            except (OSError, ValueError):
                pass
            time.sleep(.2)
        else:
            raise RuntimeError("Fixture did not become ready")
        request("/m", k="move", x=1, y=1, wait=1)
        time.sleep(.3)
        top = output / "native-top.png"
        shutil.copyfile(request("/g")["png"], top)
        request("/m", k="scroll", x=200, y=400, dy=1600, wait=1)
        time.sleep(.3)
        bottom = output / "native-bottom.png"
        shutil.copyfile(request("/g")["png"], bottom)
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (top,bottom)}
        assert hashes[top.name] != hashes[bottom.name], "Native scrolling did not change pixels"
        ocr = ROOT / "target/makepad-html-ocr"
        ocr.parent.mkdir(parents=True, exist_ok=True)
        if not ocr.exists():
            subprocess.run(["swiftc", str(ROOT / "lab/ocr.swift"), "-o", str(ocr)], check=True)
        top_text = " ".join(row["text"] for row in json.loads(subprocess.check_output([str(ocr), str(top)], text=True)))
        bottom_text = " ".join(row["text"] for row in json.loads(subprocess.check_output([str(ocr), str(bottom)], text=True)))
        (output / "native-ocr.json").write_text(json.dumps({"top": top_text, "bottom": bottom_text}, ensure_ascii=False, indent=2))
        assert "把周末还给山野" in top_text, top_text
        # Vision can confuse the small heading 呈/星 on a 1x CI display. Verify
        # multiple table rows instead; retain the raw OCR and screenshots.
        table_markers = ("标题与正文", "文章阅读", "PingFang", "Blitz", "RGBA")
        assert all(marker in bottom_text for marker in table_markers), bottom_text
        report = {"passed": True, "ocr": {"top_contains_chinese_title": True, "bottom_contains_table": True}, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "window": status["w"], "screenshots": hashes, "checks": ["isolated fixture process and owned loopback bridge", "native Makepad widget ready", "Blitz RGBA uploaded as native texture", "native scroll changes displayed article pixels"], "personal_accounts_used": False}
        report_path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
    finally:
        if app.poll() is None:
            try:
                assert request("/s")["pid"] == app.pid
                request("/gq")
            except OSError:
                app.terminate()
            app.wait(timeout=15)
