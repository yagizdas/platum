"""Small shared I/O helpers. All script paths are relative to this repository."""
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent


def normalize(name):
    """Conservative matching: never fuzzy-match a different recipe."""
    name = unicodedata.normalize("NFKC", name).casefold()
    return re.sub(r"\W+", " ", name, flags=re.UNICODE).strip()


def load_config(path=None):
    return yaml.safe_load(Path(path or ROOT / "config.yaml").read_text())


def today(config):
    return datetime.now(ZoneInfo(config["timezone"])).date()


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, data):
    """Replace atomically; an interrupted run must not corrupt the cache."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def fetch(url):
    request = Request(url, headers={"User-Agent": "MensaPlate/0.1 (static student menu)"})
    with urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8")
