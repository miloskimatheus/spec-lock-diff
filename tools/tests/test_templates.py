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


def _workflows():
    """Every workflow template, by file name. A template with no jobs is not one."""
    found = {}
    for path in sorted(TEMPLATES.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and "jobs" in doc:
            found[path.name] = doc
    return found


WORKFLOWS = _workflows()


def _runs(job):
    return "\n".join(str(step.get("run", "")) for step in job["steps"])


def test_codeowners_protects_every_path_the_readme_lists():
    """Control 5A is a table in prose; the template is the same table as a control."""
    template = (TEMPLATES / "CODEOWNERS").read_text(encoding="utf-8")
    paths = re.findall(r"^\| `([^`]+)`", _table("**Part A — CODEOWNERS", "**Part B"), re.M)
    assert len(paths) == 12
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
    for path in sorted(p for p in TEMPLATES.iterdir() if p.is_file()):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "YOU:" in line:
                assert len(line.split("YOU:")[1].split()) >= 4, "%s:%d" % (path.name, number)


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


def test_the_workflows_wire_the_three_commands_into_three_jobs():
    """The job names are what branch protection lists; the commands are the gates.

    ci.yml is the rung that needs no warehouse, ci-warehouse.yml the rest. A job
    id is how a required check is addressed, so the ids must be unique across the
    two files and no job may rename its check with `name:`.
    """
    assert sorted(WORKFLOWS) == ["ci-warehouse.yml", "ci.yml"]
    assert sorted(WORKFLOWS["ci.yml"]["jobs"]) == ["ci"]
    assert sorted(WORKFLOWS["ci-warehouse.yml"]["jobs"]) == ["build", "diff"]
    assert sorted(j for w in WORKFLOWS.values() for j in w["jobs"]) == ["build", "ci", "diff"]
    for name, workflow in WORKFLOWS.items():
        for job_id, job in workflow["jobs"].items():
            assert "name" not in job, "%s: %s renames its check" % (name, job_id)


def test_the_workflows_trigger_alike_and_do_not_cancel_each_other():
    """One run per pull request per workflow, and no workflow cancels the other.

    A concurrency group is shared by every workflow in a repository. Two files
    with one group cancel each other on every push, and the cancelled one reports
    nothing at all - which branch protection reads as a check still running.
    """
    for name, workflow in WORKFLOWS.items():
        assert workflow[True]["pull_request"]["types"] == [
            "opened", "synchronize", "reopened", "ready_for_review"], name
        assert workflow["concurrency"]["cancel-in-progress"] is True, name
        assert "github.workflow" in workflow["concurrency"]["group"], name
    # github.workflow is the workflow's own name, so distinct names are what make
    # the one group expression evaluate to two groups.
    names = [workflow["name"] for workflow in WORKFLOWS.values()]
    assert len(set(names)) == len(names), names


def test_every_job_finishes_inside_the_budget_the_readme_promises():
    assert WORKFLOWS["ci.yml"]["jobs"]["ci"]["timeout-minutes"] == 5
    warehouse = WORKFLOWS["ci-warehouse.yml"]["jobs"]
    assert warehouse["build"]["timeout-minutes"] == 15  # Stage D: about 15 minutes
    assert warehouse["diff"]["timeout-minutes"] == 60   # Stage E: one full build


def test_the_diff_waits_for_the_build_it_measures():
    """`diff` said `needs: ci` while both lived in one file.

    GitHub has no dependency from one workflow to another, so the wait is on
    `build`, which is in the same file. What was traded away is the gate's veto
    over the hour: a pull request that trips `slp gate` now still pays for the
    sample build. `diff` opens with a check of its own to keep the sixty-minute
    job from being the place a broken spec is discovered.
    """
    diff = WORKFLOWS["ci-warehouse.yml"]["jobs"]["diff"]
    assert diff["needs"] == "build"
    runs = _runs(diff)
    assert runs.index('python "$SLP" check') < runs.index('python "$SLP" compare')


def test_the_commands_run_from_the_slp_the_base_branch_set():
    """The path is the SLP variable that step sets, never tools/slp.py itself."""
    ci = _runs(WORKFLOWS["ci.yml"]["jobs"]["ci"])
    assert 'python "$SLP" check' in ci and 'python "$SLP" gate' in ci
    assert 'python "$SLP" compare' in _runs(WORKFLOWS["ci-warehouse.yml"]["jobs"]["diff"])
    for name, workflow in WORKFLOWS.items():
        for job_id, job in workflow["jobs"].items():
            assert "python tools/slp.py" not in _runs(job), "%s: %s" % (name, job_id)


def test_every_job_checks_out_every_commit():
    """The gate walks the commits of the pull request, so a shallow checkout breaks it."""
    for name, workflow in WORKFLOWS.items():
        for job_id, job in workflow["jobs"].items():
            checkout = job["steps"][0]
            where = "%s: %s" % (name, job_id)
            assert checkout["uses"].startswith("actions/checkout"), where
            assert checkout["with"]["fetch-depth"] == 0, where


def test_the_first_workflow_needs_nothing_but_python():
    """The bottom rung of the ladder: check and gate, and not one credential.

    Twenty-one of the thirty rules and the whole of Control 5B run on yml, git
    and one line of sql. If this file ever grows a warehouse step, an adopter's
    first pull request is red again and the ladder loses the rung that makes
    starting cheap.
    """
    runs = _runs(WORKFLOWS["ci.yml"]["jobs"]["ci"])
    assert "exit 1" not in runs
    assert "dbt" not in runs
    installs = [line.strip() for line in runs.splitlines() if "pip install" in line]
    assert installs == ['pip install "pyyaml" "jsonschema>=4"']


def test_the_warehouse_workflow_fails_closed_until_it_is_edited():
    """Every step that needs a credential or a decision of yours exits 1 saying so.

    A template shipped unedited must not look like a pass: an empty Stage E that
    reports green is the green badge on nothing the framework exists to prevent.
    """
    stubs = [step for job in WORKFLOWS["ci-warehouse.yml"]["jobs"].values()
             for step in job["steps"] if "exit 1" in str(step.get("run", ""))]
    assert [s["name"] for s in stubs] == [
        "warehouse auth", "production artifacts",
        "warehouse auth", "production artifacts",
        "dbt build with full data", "produce the diff"]
    for step in stubs:
        assert ">&2" in step["run"], step["name"]


def test_every_piped_step_sets_bash_so_tee_cannot_swallow_a_failure():
    counts = {name: (TEMPLATES / name).read_text(encoding="utf-8").count("shell: bash")
              for name in WORKFLOWS}
    assert counts == {"ci.yml": 2, "ci-warehouse.yml": 1}


def test_the_findings_are_fenced_so_the_job_summary_can_be_read():
    """A finding is tab separated; unfenced, the summary renders the lot as one paragraph."""
    piped = [step for workflow in WORKFLOWS.values() for job in workflow["jobs"].values()
             for step in job["steps"] if "tee -a" in str(step.get("run", ""))]
    assert len(piped) == 3
    for step in piped:
        run = step["run"]
        assert "GITHUB_STEP_SUMMARY" in run, step["name"]
        assert run.count("```") == 2, step["name"]
        # A trap, so the fence closes even when the command blocks and -e ends
        # the step - an unclosed fence swallows everything printed after it.
        assert "trap " in run and run.index("trap ") < run.index("tee -a"), step["name"]


def test_the_workflow_hands_compare_every_diff_in_one_call():
    """C7 blocks on a pre-registered model with no diff, and only sees what it was given."""
    steps = _runs(WORKFLOWS["ci-warehouse.yml"]["jobs"]["diff"])
    assert re.search(r'python "\$SLP" compare \\\n\s+--base .+ \\\n\s+diff/\*\.json', steps), steps


def test_the_readme_and_the_workflows_ask_for_the_same_jsonschema():
    """Draft 2020-12 needs jsonschema 4; a floor in one place and not the other
    means the machine that installs from the README is not the machine CI is.

    Every install path names both pins, so no job can reach a gate with whatever
    an adapter happened to pull in.
    """
    for name in WORKFLOWS:
        lines = [line for line in (TEMPLATES / name).read_text(encoding="utf-8").splitlines()
                 if "pip install" in line and not line.strip().startswith("#")]
        assert lines, name
        for line in lines:
            assert '"pyyaml"' in line and '"jsonschema>=4"' in line, "%s: %s" % (name, line)
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


def test_the_gate_and_its_flag_live_in_one_file():
    """Control 5B: required on the pull requests the bot opens; advisory where CODEOWNERS decides.

    The opener of a pull request is an identity the platform authenticates, unlike
    a commit's author. A variable nobody set must not make the gate optional, so
    an empty AGENT_LOGIN means required everywhere.

    The flag and the steps that read it stay in one file. Copied into a second
    workflow that has no env block, `env.AGENT_PR != 'true'` reads the empty
    string as true: the advisory branch runs, continue-on-error applies, and the
    required gate quietly never runs at all.
    """
    assert [n for n, w in WORKFLOWS.items() if "AGENT_PR" in str(w.get("env", {}))] == ["ci.yml"]
    assert {n for n, w in WORKFLOWS.items() for job in w["jobs"].values()
            for s in job["steps"] if str(s.get("name", "")).startswith("slp gate")} == {"ci.yml"}
    flag = WORKFLOWS["ci.yml"]["env"]["AGENT_PR"]
    assert "vars.AGENT_LOGIN == ''" in flag
    assert "github.event.pull_request.user.login == vars.AGENT_LOGIN" in flag
    gates = [s for s in WORKFLOWS["ci.yml"]["jobs"]["ci"]["steps"]
             if str(s.get("name", "")).startswith("slp gate")]
    assert [g["name"] for g in gates] == ["slp gate", "slp gate (advisory)"]
    required, advisory = gates
    assert required["if"] == "env.AGENT_PR == 'true'" and "continue-on-error" not in required
    assert advisory["if"] == "env.AGENT_PR != 'true'" and advisory["continue-on-error"] is True
    assert "advisory" in advisory["run"] and "CODEOWNERS decides" in advisory["run"]


def test_the_tools_come_from_the_base_branch_everywhere_they_run():
    """A pull request that edits tools/ must not be judged by its own edit.

    The step is duplicated rather than extracted into a composite action, because
    `uses: ./...` loads from the pull request's own tree - the exact boundary this
    step exists to defend. Duplication that is not identical is drift, so the
    copies are compared here.
    """
    copies = []
    for name, workflow in WORKFLOWS.items():
        for job_id, job in workflow["jobs"].items():
            where = "%s: %s" % (name, job_id)
            names = [s.get("name", "") for s in job["steps"]]
            commands = [i for i, n in enumerate(names) if n.startswith("slp ")]
            base = [s for s in job["steps"] if s.get("name") == "the tools from the base branch"]
            if not commands:
                assert not base, "%s fetches tools it never runs" % where
                continue
            assert len(base) == 1, where
            run = base[0]["run"]
            assert "github.event.pull_request.base.sha" in run and "git archive" in run, where
            assert 'echo "SLP=' in run and "GITHUB_ENV" in run, where
            # It fails open only in the one case where there is nothing to fall
            # back to, and says so on stderr.
            assert "is not on the base branch yet" in run and ">&2" in run, where
            # And it comes before the first command that uses it.
            assert names.index("the tools from the base branch") < min(commands), where
            copies.append(run)
    assert len(copies) == 2 and len(set(copies)) == 1
