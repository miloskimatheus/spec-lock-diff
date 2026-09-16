"""The templates against the README they copy (SLP-20, SLP-21, SLP-22).

A template that drifts from the README is worse than no template: it looks
like the framework and enforces something else.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import jsonschema
import pytest
import yaml
from conftest import EXAMPLES, GIT_ENV, TOOLS, git, make_repo

import spec_lock_diff as slp

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
    # looks for CODEOWNERS, the other two files that pin dependencies, and the
    # file that pins the gate's own version when it is installed rather than
    # vendored - a package pin by another name.
    extra = {
        "/tools/",
        "/CODEOWNERS",
        "/.github/CODEOWNERS",
        "/package-lock.yml",
        "/dependencies.yml",
        "/.slp-version",
        "/tests/mutation_equivalents.yml",
    }
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
    for command in (
        "python tools/slp.py check",
        "python tools/slp.py gate --base",
        "dbt compile",
        "dbt test --select test_type:unit",
        "dbt build",
    ):
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
            "opened",
            "synchronize",
            "reopened",
            "ready_for_review",
        ], name
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
    assert warehouse["diff"]["timeout-minutes"] == 60  # Stage E: one full build


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

    Twenty-six of the thirty-five rules and the whole of Control 5B run on yml, git
    and one line of sql. If this file ever grows a warehouse step, an adopter's
    first pull request is red again and the ladder loses the rung that makes
    starting cheap.
    """
    runs = _runs(WORKFLOWS["ci.yml"]["jobs"]["ci"])
    assert "exit 1" not in runs
    assert "dbt" not in runs
    installs = [
        line.strip()
        for line in runs.splitlines()
        if "pip install" in line and not line.strip().startswith("#")
    ]
    # Two, and both are the gate: its dependencies, and - when the base branch
    # pins a version rather than vendoring tools/ - the gate itself.
    assert installs == [
        'pip install "pyyaml" "jsonschema>=4"',
        'pip install --quiet "spec-lock-diff==$version"',
    ]


def test_the_warehouse_workflow_fails_closed_until_it_is_edited():
    """Every step that needs a credential or a decision of yours exits 1 saying so.

    A template shipped unedited must not look like a pass: an empty Stage E that
    reports green is the green badge on nothing the framework exists to prevent.
    """
    stubs = [
        step
        for job in WORKFLOWS["ci-warehouse.yml"]["jobs"].values()
        for step in job["steps"]
        if "exit 1" in str(step.get("run", ""))
    ]
    assert [s["name"] for s in stubs] == [
        "warehouse auth",
        "production artifacts",
        "warehouse auth",
        "production artifacts",
        "dbt build with full data",
        "produce the diff",
    ]
    for step in stubs:
        assert ">&2" in step["run"], step["name"]


def test_every_piped_step_sets_bash_so_tee_cannot_swallow_a_failure():
    counts = {
        name: (TEMPLATES / name).read_text(encoding="utf-8").count("shell: bash")
        for name in WORKFLOWS
    }
    assert counts == {"ci.yml": 2, "ci-warehouse.yml": 2}


def test_the_findings_are_fenced_so_the_job_summary_can_be_read():
    """A finding is tab separated; unfenced, the summary renders the lot as one paragraph."""
    piped = [
        step
        for workflow in WORKFLOWS.values()
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "tee -a" in str(step.get("run", ""))
    ]
    assert len(piped) == 4
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
        lines = [
            line
            for line in (TEMPLATES / name).read_text(encoding="utf-8").splitlines()
            if "pip install" in line and not line.strip().startswith("#")
        ]
        # The gate installed by version carries the two pins in its own metadata,
        # which test_packaging holds to the same allowlist. Every other install
        # names them here, so no job can reach a gate with whatever an adapter
        # happened to pull in.
        deps = [line for line in lines if "spec-lock-diff==" not in line]
        assert deps, name
        for line in deps:
            assert '"pyyaml"' in line and '"jsonschema>=4"' in line, "%s: %s" % (name, line)
    for name in ("README.md", "README.pt-br.md"):
        assert '"jsonschema>=4"' in (TOOLS / name).read_text(encoding="utf-8"), name


def test_the_rule_count_in_the_readmes_is_the_number_of_rules():
    """A count nobody checks is a count that drifts the first time a rule lands."""
    said = {
        7: "seven",
        24: "twenty-four",
        25: "twenty-five",
        26: "twenty-six",
        27: "twenty-seven",
        28: "twenty-eight",
        29: "twenty-nine",
        30: "thirty",
        31: "thirty-one",
        32: "thirty-two",
        33: "thirty-three",
        34: "thirty-four",
        35: "thirty-five",
    }
    words = {
        "twenty-four": "vinte e quatro",
        "twenty-five": "vinte e cinco",
        "twenty-six": "vinte e seis",
        "twenty-seven": "vinte e sete",
        "twenty-eight": "vinte e oito",
        "twenty-nine": "vinte e nove",
        "thirty": "trinta",
        "thirty-one": "trinta e uma",
        "thirty-two": "trinta e duas",
        "thirty-three": "trinta e três",
        "thirty-four": "trinta e quatro",
        "thirty-five": "trinta e cinco",
    }
    english = said.get(len(slp.RULE_IDS))
    assert english, "no word for %d rules; add it here" % len(slp.RULE_IDS)
    assert "%s rules" % english in (TOOLS / "README.md").read_text(encoding="utf-8")
    assert "%s regras" % words[english] in (TOOLS / "README.pt-br.md").read_text(encoding="utf-8")


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
    assert {
        n
        for n, w in WORKFLOWS.items()
        for job in w["jobs"].values()
        for s in job["steps"]
        if str(s.get("name", "")).startswith("slp gate")
    } == {"ci.yml"}
    flag = WORKFLOWS["ci.yml"]["env"]["AGENT_PR"]
    assert "vars.AGENT_LOGIN == ''" in flag
    assert "github.event.pull_request.user.login == vars.AGENT_LOGIN" in flag
    gates = [
        s
        for s in WORKFLOWS["ci.yml"]["jobs"]["ci"]["steps"]
        if str(s.get("name", "")).startswith("slp gate")
    ]
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


def test_the_mutation_check_runs_from_the_base_branch_too():
    """The same boundary for the one template that is not the tools.

    .github/mutate_model.py is a protected path, which makes a change to it a
    change a human reads; running the base branch's copy is what makes a pull
    request that edits it not the judge of its own edit, the way the tools are
    not.
    """
    steps = WORKFLOWS["ci-warehouse.yml"]["jobs"]["build"]["steps"]
    step = [s for s in steps if s.get("name") == "mutation check"]
    assert len(step) == 1
    run = step[0]["run"]
    assert 'git show "$base:.github/mutate_model.py"' in run
    assert 'python "$RUNNER_TEMP/mutate_model.py"' in run
    assert "python .github/mutate_model.py" not in run
    # It fails open only when there is nothing to fall back to, and says so on stderr.
    assert "is not on the base branch yet" in run and ">&2" in run


def _template(name):
    """A template as a module. It is a template, so it is not importable by name."""
    spec = importlib.util.spec_from_file_location(name[:-3], TEMPLATES / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _converter():
    return _template("diff_to_json.py")


ONE_ROW = (
    "row_delta,removed_pks,gross_revenue_changed,gross_revenue_delta_pct,"
    "window_column,window_start,window_end\n"
    "8400,0,17,0.42,order_date,2025-01-01,2025-02-01\n"
)


def _built(text, model="fct_orders"):
    import io

    convert = _converter()
    return convert.build(convert.read_row(io.StringIO(text)), model)


def test_the_converter_writes_what_the_schema_demands():
    """The last hand-written step between a query and `compare`, held to the contract.

    README section 5 used to ask the reader to translate one result row into this
    JSON themselves - which column goes in altered_columns, which number is a
    percentage, where the nullif already put a null. Getting it wrong is a diff
    `compare` refuses (`C0`) or, worse, one it reads as nothing having changed.
    """
    diff = _built(ONE_ROW)
    jsonschema.Draft202012Validator(
        json.loads((slp.SCHEMA_DIR / "diff.schema.json").read_text(encoding="utf-8"))
    ).validate(diff)
    assert diff["altered_columns"] == ["gross_revenue"]
    assert diff["metrics"] == {"gross_revenue": {"delta_pct": 0.42}}
    assert diff["window"]["column"] == "order_date"


def test_a_metric_that_did_not_move_is_not_an_altered_column():
    """`<metric>_changed` is a count, and only a count above zero is a difference."""
    diff = _built(ONE_ROW.replace(",17,", ",0,"))
    assert diff["altered_columns"] == []
    assert diff["metrics"]["gross_revenue"]["delta_pct"] == 0.42


def test_a_percentage_of_zero_stays_null():
    """When production is 0 the percentage does not exist, and nullif writes nothing.

    An empty cell must not become 0.0: that is a number nobody can evaluate being
    read as a number that passed. `compare` blocks on the null, which is the point.
    """
    diff = _built(ONE_ROW.replace(",0.42,", ",,"))
    assert diff["metrics"]["gross_revenue"] == {"delta_pct": None}


def test_a_model_production_does_not_have_carries_its_value():
    """No production side, so no percentage; the interval is on the value instead."""
    diff = _built("row_delta,removed_pks,gross_revenue_value\n14203118,0,14203118.40\n")
    assert diff["metrics"]["gross_revenue"] == {"delta_pct": None, "value": 14203118.40}


def test_json_and_csv_are_read_the_same_way():
    """Whatever your warehouse client writes, the row is the row."""
    as_json = json.dumps(
        {
            "row_delta": 8400,
            "removed_pks": 0,
            "gross_revenue_changed": 17,
            "gross_revenue_delta_pct": 0.42,
            "window_column": "order_date",
            "window_start": "2025-01-01",
            "window_end": "2025-02-01",
        }
    )
    assert _built(as_json) == _built(ONE_ROW)


def test_a_critical_models_two_numbers_travel_together():
    diff = _built(
        "row_delta,removed_pks,reconciliation_model_value,"
        "reconciliation_external_value\n312,0,1000000.0,1000200.0\n",
        "fct_invoices",
    )
    assert diff["reconciliation"] == {"model_value": 1000000.0, "external_value": 1000200.0}


@pytest.mark.parametrize(
    "row",
    [
        "",
        "row_delta\n8400\n",  # no removed_pks
        "row_delta,removed_pks\n8400,-1\n",  # keys cannot un-remove
        "row_delta,removed_pks\nplenty,0\n",  # not a number
        "row_delta,removed_pks\n8400,0\n8401,0\n",  # two rows, one model
    ],
)
def test_what_it_cannot_convert_it_refuses(row):
    """Fail closed, as slp does: a diff nobody could write is not an empty diff."""
    with pytest.raises(SystemExit):
        _built(row)


def test_the_converter_output_is_a_diff_compare_accepts(tmp_path):
    """End to end: the row a query returns, through the converter, into the gate."""
    project = tmp_path / "project"
    (project / "models" / "marts").mkdir(parents=True)
    (project / "models" / "marts" / "fct_orders.sql").write_text("select 1", encoding="utf-8")
    (project / "models" / "marts" / "fct_orders.yml").write_text(
        (
            TOOLS
            / "tests"
            / "fixtures"
            / "check"
            / "prereg_ok"
            / "models"
            / "marts"
            / "fct_orders.yml"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    diff = tmp_path / "fct_orders.json"
    diff.write_text(json.dumps(_built(ONE_ROW)), encoding="utf-8")
    from conftest import run_slp

    code, out, err = run_slp(["compare", "--project-dir", str(project), str(diff)], tmp_path)
    assert code == 0, out + err
    assert "row_delta 8400, declared 0..12000" in out


# --- templates/tcr.sh: the loop of Rule 5 ---


def _loop_repo(tmp_path):
    """A repository with a stub tool and a stub dbt, both driven by environment variables."""
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    (repo / "tools" / "slp.py").write_text(
        'import os, sys\nsys.exit(int(os.environ.get("STUB_SLP", "0")))\n', encoding="utf-8"
    )
    shutil.copy(str(TEMPLATES / "tcr.sh"), str(repo / "tcr.sh"))
    stubs = tmp_path / "bin"
    stubs.mkdir()
    (stubs / "dbt").write_text('#!/bin/sh\nexit "${STUB_DBT:-0}"\n', encoding="utf-8")
    (stubs / "dbt").chmod(0o755)
    (stubs / "python").symlink_to(sys.executable)
    git(repo, "init", "-q", "-b", "main", "--template=")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the model as main has it")
    return repo, stubs


def _loop(repo, stubs, dbt="0", message="a step"):
    env = dict(os.environ, PATH="%s:%s" % (stubs, os.environ["PATH"]), STUB_DBT=dbt, **GIT_ENV)
    return subprocess.run(
        ["bash", "tcr.sh", message], cwd=str(repo), env=env, capture_output=True, text=True
    )


def test_the_loop_commits_on_green_and_reverts_on_red(tmp_path):
    """Rule 5: all green, it commits; anything red, the working tree goes back."""
    repo, stubs = _loop_repo(tmp_path)
    (repo / "models").mkdir()
    (repo / "models" / "a.sql").write_text("select 1\n", encoding="utf-8")
    done = _loop(repo, stubs, message="a model")
    assert done.returncode == 0 and "tcr: green, committed" in done.stdout, done.stderr
    assert git(repo, "log", "--format=%s").splitlines()[0] == "a model"
    (repo / "models" / "a.sql").write_text("select 2\n", encoding="utf-8")
    (repo / "models" / "b.sql").write_text("select 3\n", encoding="utf-8")
    done = _loop(repo, stubs, dbt="1")
    assert done.returncode == 1 and "strike 1 of 5" in done.stderr
    assert (repo / "models" / "a.sql").read_text(encoding="utf-8") == "select 1\n"
    assert not (repo / "models" / "b.sql").exists()  # a new file goes too
    assert git(repo, "status", "--short") == ""


def test_the_fifth_red_in_a_row_stops_the_loop_and_a_green_resets_it(tmp_path):
    repo, stubs = _loop_repo(tmp_path)
    for strike in range(1, 5):
        done = _loop(repo, stubs, dbt="1")
        assert done.returncode == 1 and "strike %d of 5" % strike in done.stderr
    done = _loop(repo, stubs, dbt="1")
    assert done.returncode == 3 and "five reverts in a row; stop and ask a human" in done.stderr
    (repo / "tools" / "note.txt").write_text("green again\n", encoding="utf-8")
    assert _loop(repo, stubs).returncode == 0
    assert not (repo / ".git" / "slp-tcr-strikes").exists()
    assert _loop(repo, stubs, dbt="1").returncode == 1  # the count started over


def test_the_loop_never_builds():
    """A build scans the sample window; the loop runs many times. The build runs once, in CI."""
    text = (TEMPLATES / "tcr.sh").read_text(encoding="utf-8")
    assert "dbt build" not in text.replace("`dbt build`", "")
    assert "dbt test --select test_type:unit" in text and "exit 3" in text


# --- templates/spec_draft.sql: aggregates, never rows ---


def test_the_draft_queries_return_aggregates_and_never_a_row():
    """Control 4: an agent may run these; a query that returns rows is not one of them."""
    text = (TEMPLATES / "spec_draft.sql").read_text(encoding="utf-8").lower()
    assert "select *" not in text and not re.search(r"\blimit\b", text)
    for statement in [s for s in text.split(";") if "select" in s]:
        assert re.search(r"\b(count|countif|sum|approx_count_distinct|total_rows)\b", statement), (
            statement
        )


# --- templates/mutate_model.py: the mutation check of Stage D ---

RICH = (
    "select distinct a, sum(b) as s, coalesce('x', 0) as c\n"
    "from {{ ref('x') }} x\n"
    "left join {{ ref('y') }} y on x.id = y.id -- != in a comment\n"
    "where x.d is not null and (x.e > 3 or x.f not in ('a', 'b'))\n"
    "group by 1\n"
)


def test_the_mutants_of_a_model_are_deterministic_and_leave_comments_alone():
    mm = _template("mutate_model.py")
    sql = (EXAMPLES / "quickstart" / "models" / "marts" / "fct_orders.sql").read_text(
        encoding="utf-8"
    )
    sql += "-- where status != 'x' {{ ref('ghost') }}\n"
    first = [(m.id, m.original, m.replacement, m.line) for m in mm.sites(sql)]
    assert first == [(m.id, m.original, m.replacement, m.line) for m in mm.sites(sql)]
    assert first == [
        ("where/1", "status != 'cancelled'", "true", 7),
        ("cmp/1", "!=", "=", 7),
        ("literal/1", "'cancelled'", "'cancelled_'", 7),
    ]


def test_every_operator_finds_its_site_in_a_rich_model():
    mm = _template("mutate_model.py")
    by_op = {}
    for mutant in mm.sites(RICH):
        by_op.setdefault(mutant.op, []).append((mutant.original, mutant.replacement))
    assert sorted(by_op) == [
        "agg",
        "cmp",
        "coalesce",
        "distinct",
        "join",
        "literal",
        "not",
        "where",
    ]
    assert by_op["coalesce"] == [("coalesce('x', 0)", "'x'")]
    assert by_op["join"] == [("left join", "inner join")]
    assert ("(x.e > 3 or x.f not in ('a', 'b'))", "true") in by_op["where"]
    assert ("is not null", "is null") in by_op["not"] and ("not in", "in") in by_op["not"]
    assert ("!=", "=") not in by_op["cmp"]  # the one in the comment


def test_the_batch_is_one_model_per_mutant_with_the_unit_tests_cloned():
    mm = _template("mutate_model.py")
    sql = (EXAMPLES / "quickstart" / "models" / "marts" / "fct_orders.sql").read_text(
        encoding="utf-8"
    )
    yml = (EXAMPLES / "quickstart" / "models" / "marts" / "fct_orders.yml").read_text(
        encoding="utf-8"
    )
    units = yaml.safe_load(yml)["unit_tests"]
    mutants = mm.sites(sql)
    files = mm.layout("fct_orders", sql, units, mutants, "models/marts")
    doc = yaml.safe_load(files["models/marts/__mutants__/schema.yml"])
    assert len(doc["unit_tests"]) == len(mutants) * len(units)
    assert len(set(u["name"] for u in doc["unit_tests"])) == len(doc["unit_tests"])
    for unit in doc["unit_tests"]:
        assert mm.TAG in unit["config"]["tags"] and unit["given"][0]["input"] == "ref('stg_orders')"
    for mutant in mutants:
        text = files["models/marts/__mutants__/%s.sql" % mutant.name]
        assert text != sql and mutant.replacement in text


def test_verdicts_come_from_run_results():
    mm = _template("mutate_model.py")
    mutants = mm.sites("select a from {{ ref('t') }} where a != 1 and b > 2\n")
    mm.layout("m", "", [{"name": "u", "model": "m"}], mutants, "models/marts")
    results = {
        "results": [
            {
                "unique_id": "unit_test.p.%s.u__%s" % (mutants[0].name, mutants[0].name),
                "status": "fail",
            },
            {
                "unique_id": "unit_test.p.%s.u__%s" % (mutants[1].name, mutants[1].name),
                "status": "pass",
            },
            {
                "unique_id": "unit_test.p.%s.u__%s" % (mutants[2].name, mutants[2].name),
                "status": "error",
            },
        ]
    }
    mm.verdicts(results, mutants)
    assert [m.verdict for m in mutants[:3]] == ["killed", "survived", "killed"]
    assert all(m.verdict == "survived" for m in mutants[3:])


def _stub_dbt(folder):
    """A dbt that runs nothing: it reads the cloned unit tests and writes their verdicts.

    Every cloned unit test fails, except on the mutant models STUB_SURVIVORS names.
    """
    folder.mkdir()
    (folder / "dbt").write_text(
        "#!%s\n"
        "import glob, json, os, pathlib, yaml\n"
        "survivors = os.environ.get('STUB_SURVIVORS', '').split(',')\n"
        "results = []\n"
        "for schema in glob.glob('models/**/__mutants__/schema.yml', recursive=True):\n"
        "    for unit in yaml.safe_load(open(schema))['unit_tests']:\n"
        "        status = 'pass' if unit['model'] in survivors else 'fail'\n"
        "        results.append({'unique_id': 'unit_test.p.%%s.%%s'"
        " %% (unit['model'], unit['name']),"
        " 'status': status})\n"
        "pathlib.Path('target').mkdir(exist_ok=True)\n"
        "json.dump({'results': results}, open('target/run_results.json', 'w'))\n" % sys.executable,
        encoding="utf-8",
    )
    (folder / "dbt").chmod(0o755)


def _changed_quickstart(tmp_path, equivalents=None, unit_tests=True):
    """The quickstart as main has it, then a pull request that changes fct_orders.sql."""
    before, after = tmp_path / "before", tmp_path / "after"
    for tree in (before, after):
        shutil.copytree(str(EXAMPLES / "quickstart"), str(tree))
        shutil.rmtree(str(tree / "diff"))
    if equivalents is not None:
        (before / "tests").mkdir()
        (before / "tests" / "mutation_equivalents.yml").write_text(equivalents, encoding="utf-8")
        shutil.copytree(str(before / "tests"), str(after / "tests"))
    sql = after / "models" / "marts" / "fct_orders.sql"
    sql.write_text(
        sql.read_text(encoding="utf-8").replace("select\n", "select  -- reformatted\n"),
        encoding="utf-8",
    )
    if not unit_tests:
        yml = after / "models" / "marts" / "fct_orders.yml"
        yml.write_text(
            yml.read_text(encoding="utf-8").split("\nunit_tests:")[0] + "\n", encoding="utf-8"
        )
    repo = make_repo(tmp_path, before, after)
    stubs = tmp_path / "bin"
    _stub_dbt(stubs)
    return repo, stubs


def test_the_mutation_check_end_to_end_with_a_stub_dbt(tmp_path, monkeypatch, capsys):
    """One dbt invocation, the temporary models gone after it; a survivor blocks, a listed one
    informs.
    """
    mm = _template("mutate_model.py")
    listed = (
        "- model: fct_orders\n  operator: literal\n  original: \"'cancelled'\"\n"
        "  occurrence: 1\n  reason: the fixture has no other status\n"
    )
    repo, stubs = _changed_quickstart(tmp_path, equivalents=listed)
    monkeypatch.setenv("PATH", "%s:%s" % (stubs, os.environ["PATH"]))
    monkeypatch.setenv("STUB_SURVIVORS", "fct_orders__literal_1,fct_orders__cmp_1")
    code = mm.main(["--base", "base", "--project-dir", str(repo), "--out", "mutation"])
    out = capsys.readouterr().out
    assert code == 1, out
    assert (
        "BLOCK\tmodels/marts/fct_orders.sql\tfct_orders\tmutant cmp/1: != -> = at line 7 survived"
        in out
    )
    assert (
        "INFO\tmodels/marts/fct_orders.sql\tfct_orders\tmutant literal/1: 'cancelled' -> "
        "'cancelled_' at line 7 survived and is listed as equivalent: "
        "the fixture has no other status" in out
    )
    assert out.splitlines()[-1] == "mutate: 1 block - BLOCKED"
    assert not (repo / "models" / "marts" / "__mutants__").exists()
    written = json.loads((repo / "mutation" / "fct_orders.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(
        json.loads((slp.SCHEMA_DIR / "mutation.schema.json").read_text(encoding="utf-8"))
    ).validate(written)
    assert (written["killed"], written["survived"], written["equivalent"]) == (1, 1, 1)
    monkeypatch.setenv("STUB_SURVIVORS", "fct_orders__literal_1")
    code = mm.main(["--base", "base", "--project-dir", str(repo), "--out", "mutation"])
    assert (
        code == 0
        and capsys.readouterr().out.splitlines()[-1]
        == "mutate: OK (2 killed, 1 equivalent, in 1 model)"
    )


def test_a_changed_model_with_no_unit_test_blocks_before_dbt_runs(tmp_path, monkeypatch, capsys):
    mm = _template("mutate_model.py")
    repo, stubs = _changed_quickstart(tmp_path, unit_tests=False)
    monkeypatch.setenv("PATH", "%s:%s" % (stubs, os.environ["PATH"]))
    code = mm.main(["--base", "base", "--project-dir", str(repo)])
    out = capsys.readouterr().out
    assert code == 1 and "the sql changed and the model has no unit test" in out
    assert not (repo / "target").exists()  # dbt never ran


def test_a_dry_run_lists_the_mutants_and_writes_nothing(tmp_path, capsys):
    mm = _template("mutate_model.py")
    repo, _ = _changed_quickstart(tmp_path)
    assert mm.main(["--base", "base", "--project-dir", str(repo), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert (
        "fct_orders\tcmp/1" in out
        and out.splitlines()[-1] == "mutate: 1 changed model listed, nothing run"
    )
    assert not (repo / "mutation").exists() and not (repo / "target").exists()
