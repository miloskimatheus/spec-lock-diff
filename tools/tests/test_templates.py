"""The templates against the README they copy (SLP-20, SLP-21, SLP-22).

A template that drifts from the README is worse than no template: it looks
like the framework and enforces something else.
"""

import re

import pytest
import yaml

from conftest import TOOLS

README = (TOOLS.parent / "README.md").read_text(encoding="utf-8")
TEMPLATES = TOOLS / "templates"


def _table(after, before):
    return README.split(after)[1].split(before)[0]


def test_codeowners_protects_every_path_the_readme_lists():
    """Control 5A is a table in prose; the template is the same table as a control."""
    template = (TEMPLATES / "CODEOWNERS").read_text(encoding="utf-8")
    paths = re.findall(r"^\| `([^`]+)`", _table("**Part A — CODEOWNERS", "**Part B"), re.M)
    assert len(paths) == 11
    for path in paths:
        assert path.strip("/") in template, path


def test_codeowners_adds_only_what_it_explains():
    """The three additions to the README's list are the only ones."""
    template = (TEMPLATES / "CODEOWNERS").read_text(encoding="utf-8")
    owned = re.findall(r"^(/\S+)\s+@", template, re.M)  # commented lines own nothing
    # The additions the template explains: the gate itself, the second place git
    # looks for CODEOWNERS, and the other two files that pin dependencies.
    extra = {"/tools/", "/CODEOWNERS", "/.github/CODEOWNERS",
             "/package-lock.yml", "/dependencies.yml"}
    for path in owned:
        assert path in extra or path.strip("/").split("*")[0] in README, path


def test_every_placeholder_says_what_to_put_there():
    """A line the reader must edit is marked, and never left to be guessed."""
    for name in sorted(p.name for p in TEMPLATES.iterdir()):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if "YOU:" in line:
                assert len(line.split("YOU:")[1].split()) >= 4, "%s:%d" % (name, number)


def test_agents_md_carries_the_eight_rules_and_their_mechanisms():
    """Rule and mechanism travel together: a rule with no mechanism is a suggestion."""
    template = (TEMPLATES / "AGENTS.md").read_text(encoding="utf-8")
    table = _table("**The 8 agent rules:**", "### Stage D")
    rows = [r for r in table.splitlines() if re.match(r"^\| \d", r)]
    assert len(rows) == 8
    for row in rows:
        number, rule, mechanism = [c.strip() for c in row.strip().strip("|").split("|")][:3]
        assert rule in template, "rule %s is not in AGENTS.md as the README writes it" % number
        assert mechanism in template, "rule %s lost its mechanism" % number


def test_agents_md_says_it_is_not_a_control():
    template = (TEMPLATES / "AGENTS.md").read_text(encoding="utf-8")
    assert "Nothing in this file is a control" in template.split("\n\n")[1]
    for command in ("python tools/slp.py check", "python tools/slp.py gate --base",
                    "dbt compile", "dbt test --select test_type:unit", "dbt build"):
        assert command in template


def test_ci_yml_wires_the_three_commands_into_two_jobs():
    """The job names are what branch protection lists; the commands are the gates."""
    workflow = yaml.safe_load((TEMPLATES / "ci.yml").read_text(encoding="utf-8"))
    assert sorted(workflow["jobs"]) == ["ci", "diff"]
    assert workflow[True]["pull_request"]["types"] == [
        "opened", "synchronize", "reopened", "ready_for_review"]
    assert workflow["concurrency"]["cancel-in-progress"] is True
    assert workflow["jobs"]["ci"]["timeout-minutes"] == 15  # Stage D: about 15 minutes
    assert workflow["jobs"]["diff"]["needs"] == "ci"
    steps = {"ci": "", "diff": ""}
    for job in steps:
        steps[job] = "\n".join(str(step.get("run", "")) for step in workflow["jobs"][job]["steps"])
    # The commands run from the base branch's copy of tools/ (see below), so
    # the path is the SLP variable that step sets, never tools/slp.py itself.
    assert 'python "$SLP" check' in steps["ci"]
    assert 'python "$SLP" gate' in steps["ci"]
    assert 'python "$SLP" compare' in steps["diff"]
    assert "python tools/slp.py" not in steps["ci"] + steps["diff"]
    # The gate walks the commits of the pull request, so a shallow checkout breaks it.
    for job in ("ci", "diff"):
        checkout = workflow["jobs"][job]["steps"][0]
        assert checkout["uses"].startswith("actions/checkout")
        assert checkout["with"]["fetch-depth"] == 0


def test_ci_yml_pipes_the_gate_into_the_job_summary_without_losing_its_exit_code():
    text = (TEMPLATES / "ci.yml").read_text(encoding="utf-8")
    for line in text.splitlines():
        if "tee -a" in line:
            assert "GITHUB_STEP_SUMMARY" in line
    assert text.count("shell: bash") == 3  # bash -eo pipefail on every piped step


def test_ci_yml_fences_the_findings_so_the_job_summary_can_be_read():
    """A finding is tab separated; unfenced, the summary renders the lot as one paragraph."""
    workflow = yaml.safe_load((TEMPLATES / "ci.yml").read_text(encoding="utf-8"))
    piped = [step for job in workflow["jobs"].values() for step in job["steps"]
             if "tee -a" in str(step.get("run", ""))]
    assert len(piped) == 3
    for step in piped:
        run = step["run"]
        assert run.count("```") == 2, step["name"]
        # A trap, so the fence closes even when the command blocks and -e ends
        # the step - an unclosed fence swallows everything printed after it.
        assert "trap " in run and run.index("trap ") < run.index("tee -a"), step["name"]


def test_ci_yml_hands_compare_every_diff_in_one_call():
    """C7 blocks on a pre-registered model with no diff, and only sees what it was given."""
    workflow = yaml.safe_load((TEMPLATES / "ci.yml").read_text(encoding="utf-8"))
    steps = "\n".join(str(s.get("run", "")) for s in workflow["jobs"]["diff"]["steps"])
    assert re.search(r'python "\$SLP" compare \\\n\s+--base .+ \\\n\s+diff/\*\.json', steps), steps


def test_the_readme_and_the_workflow_ask_for_the_same_jsonschema():
    """Draft 2020-12 needs jsonschema 4; a floor in one place and not the other
    means the machine that installs from the README is not the machine CI is."""
    workflow = (TEMPLATES / "ci.yml").read_text(encoding="utf-8")
    assert workflow.count('"jsonschema>=4"') == 2
    for name in ("README.md", "README.pt-br.md"):
        assert '"jsonschema>=4"' in (TOOLS / name).read_text(encoding="utf-8"), name


def test_the_rule_count_in_the_readmes_is_the_number_of_rules():
    """A count nobody checks is a count that drifts the first time a rule lands."""
    import slp
    said = {7: "seven", 24: "twenty-four", 25: "twenty-five", 26: "twenty-six",
            27: "twenty-seven", 28: "twenty-eight", 29: "twenty-nine", 30: "thirty",
            31: "thirty-one", 32: "thirty-two"}
    words = {"twenty-four": "vinte e quatro", "twenty-five": "vinte e cinco",
             "twenty-six": "vinte e seis", "twenty-seven": "vinte e sete",
             "twenty-eight": "vinte e oito", "twenty-nine": "vinte e nove",
             "thirty": "trinta", "thirty-one": "trinta e uma", "thirty-two": "trinta e duas"}
    english = said.get(len(slp.RULE_IDS))
    assert english, "no word for %d rules; add it here" % len(slp.RULE_IDS)
    assert "%s rules" % english in (TOOLS / "README.md").read_text(encoding="utf-8")
    assert "%s regras" % words[english] in \
        (TOOLS / "README.pt-br.md").read_text(encoding="utf-8")


def test_ci_yml_requires_the_gate_on_the_agents_pull_requests_and_fails_closed():
    """Control 5B: required on the pull requests the bot opens; advisory where CODEOWNERS decides.

    The opener of a pull request is an identity the platform authenticates, unlike
    a commit's author. A variable nobody set must not make the gate optional, so
    an empty AGENT_LOGIN means required everywhere.
    """
    workflow = yaml.safe_load((TEMPLATES / "ci.yml").read_text(encoding="utf-8"))
    flag = workflow["env"]["AGENT_PR"]
    assert "vars.AGENT_LOGIN == ''" in flag
    assert "github.event.pull_request.user.login == vars.AGENT_LOGIN" in flag
    gates = [s for s in workflow["jobs"]["ci"]["steps"] if str(s.get("name", "")).startswith("slp gate")]
    assert [g["name"] for g in gates] == ["slp gate", "slp gate (advisory)"]
    required, advisory = gates
    assert required["if"] == "env.AGENT_PR == 'true'" and "continue-on-error" not in required
    assert advisory["if"] == "env.AGENT_PR != 'true'" and advisory["continue-on-error"] is True
    assert "advisory" in advisory["run"] and "CODEOWNERS decides" in advisory["run"]


def test_ci_yml_runs_the_tools_from_the_base_branch():
    """A pull request that edits tools/ must not be judged by its own edit."""
    workflow = yaml.safe_load((TEMPLATES / "ci.yml").read_text(encoding="utf-8"))
    for job in ("ci", "diff"):
        steps = workflow["jobs"][job]["steps"]
        base = [s for s in steps if s.get("name") == "the tools from the base branch"]
        assert len(base) == 1, job
        run = base[0]["run"]
        assert "github.event.pull_request.base.sha" in run and "git archive" in run
        assert 'echo "SLP=' in run and "GITHUB_ENV" in run
        # It fails open only in the one case where there is nothing to fall back
        # to, and says so on stderr.
        assert "is not on the base branch yet" in run and ">&2" in run
        # And it comes before the first command that uses it.
        names = [s.get("name", "") for s in steps]
        first = min(i for i, n in enumerate(names) if n.startswith("slp "))
        assert names.index("the tools from the base branch") < first, job
