import re
from pathlib import Path


ROOT = Path(__file__).parents[1]


def local_scripts(page):
    html = (ROOT / page).read_text()
    return {
        source.removeprefix("./").split("?", 1)[0]
        for source in re.findall(r'<script[^>]+src=["\']([^"\']+)', html)
        if not source.startswith(("http://", "https://", "//"))
    }


def test_workflows_package_every_local_menu_script():
    scripts = local_scripts("menu.html")
    assert scripts
    for workflow in ("daily.yml", "publish.yml"):
        definition = (ROOT / ".github" / "workflows" / workflow).read_text()
        missing = {script for script in scripts if script not in definition}
        assert not missing, f"{workflow} does not package: {sorted(missing)}"
