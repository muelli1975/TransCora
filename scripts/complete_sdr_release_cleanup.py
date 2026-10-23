"""Complete a verified release after GitHub returned HTTP 500 during old-asset cleanup."""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://api.github.com/repos/muelli1975/TransCora"
SOURCE = "6b19180c7fc47f6128d934304a2ff95417117245"
EXPECTED = {
    "TransCora_1.1_Linux_x64.tar.gz": {
        "digest": "sha256:d1fc6dd9a285326466693ef74a715cf84026dd90c2310c5f24f652c6d27e9b80",
        "size": 117857973
    },
    "TransCora_1.1_Linux_x64.tar.gz.sha256": {
        "digest": "sha256:1f48ba365250000d2a0cadeaeae7d84c553e748962ddaa2a92af1a9edf26fd88",
        "size": 97
    },
    "TransCora_1.1_macOS_AppleSilicon.tar.gz": {
        "digest": "sha256:a9486a50bd73cdca50448ed8e1638abab2e87945f05abbbe74854bef97c13f32",
        "size": 101652593
    },
    "TransCora_1.1_macOS_AppleSilicon.tar.gz.sha256": {
        "digest": "sha256:8cce5781843a81b2916969c7dd42e723b3f011d1566ca3cd4fb7f9183f269b77",
        "size": 106
    },
    "TransCora_1.1_Windows_x64.zip": {
        "digest": "sha256:4932a71d5243c0eebdf38fd5a6b33abbf561c6808c407531459f64f0a2b44ee4",
        "size": 168634198
    },
    "TransCora_1.1_Windows_x64.zip.sha256": {
        "digest": "sha256:8774e3da0767d0b3bc3b17e5caf1920a0ba3156db368c0668cd9448ed56e8128",
        "size": 97
    }
}
STALE = {
    "id": 640973837,
    "name": "TransCora_1.1_Windows_x64.zip.sha256.previous-6b19180c7fc4",
    "digest": "sha256:a7d002ca6cc963b89be1bd47eba69436acf031ba4558314c4fb2c2a65f43ce7e",
    "size": 97
}


def api(path, method="GET"):
    request = urllib.request.Request(BASE + path, method=method, headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
            return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            if method == "DELETE" and exc.code == 404:
                return None
            if exc.code not in (500, 502, 503, 504) or attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))


release = api("/releases/tags/v1.1")
assert release["id"] == 411672025 and release["target_commitish"] == SOURCE
assert api("/git/ref/tags/v1.1")["object"]["sha"] == SOURCE
assert api("/git/ref/heads/main")["object"]["sha"] == SOURCE
assets = {a["name"]: a for a in release["assets"]}
assert set(assets) <= set(EXPECTED) | {STALE["name"]}
assert set(EXPECTED) <= set(assets)
for name, expected in EXPECTED.items():
    actual = assets[name]
    assert actual["digest"] == expected["digest"] and actual["size"] == expected["size"]
    with urllib.request.urlopen(actual["browser_download_url"], timeout=180) as response:
        digest = "sha256:" + hashlib.file_digest(response, "sha256").hexdigest()
    assert digest == expected["digest"], name
    if not name.endswith(".sha256"):
        assert digest.split(":")[1] in release["body"]
    print("Verified current public download:", name, flush=True)
if STALE["name"] in assets:
    old = assets[STALE["name"]]
    assert all(old[k] == v for k, v in STALE.items())
    api("/releases/assets/" + str(STALE["id"]), "DELETE")
final = api("/releases/tags/v1.1")
assert final["body"] == release["body"] and len(final["assets"]) == 6
assert {a["name"] for a in final["assets"]} == set(EXPECTED)
print(json.dumps({"status": "passed", "release": final["html_url"], "commit": SOURCE,
                  "assets": EXPECTED}, indent=2))
