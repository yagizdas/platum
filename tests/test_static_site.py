import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "daily.yml"


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


def _packaging_script() -> str:
    lines = WORKFLOW.read_text().splitlines()
    step = lines.index("      - name: Package only public static files")
    run = lines.index("        run: |", step)
    script = []
    for line in lines[run + 1 :]:
        if line.startswith("      - "):
            break
        script.append(line[10:] if line.startswith("          ") else line)
    return "\n".join(script)


def test_packaging_allows_a_static_file_to_exist_only_on_staging(tmp_path):
    main = tmp_path / "main"
    shutil.copytree(ROOT, main, ignore=shutil.ignore_patterns(".git", "font-trial.js"))
    shutil.copytree(ROOT, main / "staging-source", ignore=shutil.ignore_patterns(".git"))

    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _packaging_script()],
        cwd=main,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert not (main / "dist" / "font-trial.js").exists()
    assert (main / "dist" / "staging" / "font-trial.js").is_file()
