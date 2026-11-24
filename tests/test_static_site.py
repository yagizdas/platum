import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


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


def _packaging_script(workflow) -> str:
    lines = (WORKFLOWS / workflow).read_text().splitlines()
    step = lines.index("      - name: Package only public static files")
    run = lines.index("        run: |", step)
    script = []
    for line in lines[run + 1 :]:
        if line.startswith("      - "):
            break
        script.append(line[10:] if line.startswith("          ") else line)
    return "\n".join(script)


@pytest.mark.parametrize("workflow", ["daily.yml", "publish.yml"])
def test_packaging_allows_a_static_file_to_exist_only_on_staging(tmp_path, workflow):
    main = tmp_path / "main"
    shutil.copytree(ROOT, main, ignore=shutil.ignore_patterns(".git", ".venv", ".taste-skill", "node_modules", "font-trial.js"))
    shutil.copytree(ROOT, main / "staging-source", ignore=shutil.ignore_patterns(".git", ".venv", ".taste-skill", "node_modules"))

    for source in (main, main / "staging-source"):
        campus = source / "data/campuses/garching"
        (campus / "days").mkdir(parents=True, exist_ok=True)
        for name in ("week.json", "today.json", "days/2026-11-23.json"):
            (campus / name).write_text('{"campus":"garching"}')
        (campus / "proposals").mkdir(exist_ok=True)
        (campus / "proposals/private-cache.json").write_text('{}')
    # Optional scripts may exist only on the staging branch.
    (main / "staging-source" / "font-trial.js").write_text("// staging-only fixture\n")

    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _packaging_script(workflow)],
        cwd=main,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert not (main / "dist" / "font-trial.js").exists()
    assert (main / "dist" / "staging" / "font-trial.js").is_file()

    assert (main / "dist" / "menu.html").read_bytes() == (ROOT / "menu.html").read_bytes()
    assert (main / "dist" / "staging" / "menu.html").is_file()
    assert (main / "dist" / "staging" / "label" / "index.html").is_file()
    assert (main / "dist" / "data" / "today.json").is_file()
    assert (main / "dist" / "staging" / "data" / "today.json").is_file()
    for site in (main / "dist", main / "dist" / "staging"):
        for private in (".env", "data/dish_cache.json", "data/proposals", "data/judgments"):
            assert not (site / private).exists()
        assert (site / 'data/campuses/garching/week.json').is_file()
        assert (site / 'data/campuses/garching/days/2026-11-23.json').is_file()
        assert not (site / 'data/campuses/garching/proposals').exists()
        assert not (site / 'data/campuses/garching/menus').exists()


def _workflow(name):
    # BaseLoader keeps GitHub's `on` key as a string rather than YAML 1.1's boolean.
    return yaml.load((WORKFLOWS / name).read_text(), Loader=yaml.BaseLoader)


def test_pushes_publish_cached_data_without_model_access():
    workflow = _workflow("publish.yml")
    assert set(workflow["on"]) == {"push", "workflow_dispatch"}
    assert set(workflow["on"]["push"]["branches"]) == {"main", "staging"}
    definition = (WORKFLOWS / "publish.yml").read_text()
    assert "GEMINI_API_KEY" not in definition
    runs = [step.get("run", "") for step in workflow["jobs"]["publish"]["steps"]]
    for command in runs:
        assert not re.search(r"python\s+(?:scrape|tag|pair|proposals|judge)\.py", command)
        for line in command.splitlines():
            if re.search(r"python\s+pick\.py", line):
                assert "--no-llm" in line
    assert any("python rescore_cached.py" in command for command in runs)
    assert "no_llm=True" in (ROOT / "rescore_cached.py").read_text()
    assert workflow["jobs"]["publish"]["permissions"]["contents"] == "read"


def test_generation_is_explicit_or_scheduled_and_deployments_share_a_lock():
    daily = _workflow("daily.yml")
    publish = _workflow("publish.yml")
    assert set(daily["on"]) == {"schedule", "workflow_dispatch"}
    assert daily["on"]["schedule"] == [{"cron": "30 6 * * 1-5"}, {"cron": "30 7 * * 6,0"}]
    assert daily["concurrency"] == publish["concurrency"]
    assert daily["concurrency"]["cancel-in-progress"] == "false"
    definition = (WORKFLOWS / "daily.yml").read_text()
    assert "secrets.GEMINI_API_KEY" in definition
    assert "python weekly_batch.py" in definition
    assert "python scrape.py" not in definition
