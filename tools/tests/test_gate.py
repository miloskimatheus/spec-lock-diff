"""gate: one folder per case under fixtures/gate/.

Each case is a small repository built from its `before`, `mid` and `after`
trees, one commit each. The folder name and its README.txt say what must
happen, so adding a rule means adding a folder - never editing this file.
"""

import pytest

import slp
from conftest import FIXTURES, assert_expected, cases, git, make_repo, run_slp

TREES = ("before", "mid", "after")
# The plumbing tests need a repository, not a rule: this one changes nothing.
QUIET = FIXTURES / "gate" / "gate_ok_identical"


def build(case, tmp_path):
    """The repository one fixture describes, and its first commit as `base`."""
    return make_repo(tmp_path, *[case / name for name in TREES if (case / name).is_dir()])


@pytest.mark.parametrize("case", cases("gate"), ids=lambda p: p.name)
def test_gate_case(case, tmp_path):
    repo = build(case, tmp_path)
    code, out, err = run_slp(["gate", "--base", "base"], repo)
    assert_expected(case, code, out, err)


def test_replacing_mains_pre_registration_is_not_an_edit(tmp_path):
    """README §3 Stage B: a pre-registration belongs to one pull request. I1 counts this PR's edits."""
    repo = build(FIXTURES / "gate" / "I1_stale_replaced_then_edited", tmp_path)
    _, out, _ = run_slp(["gate", "--base", "base"], repo)
    assert "pre-registration was modified 1 time after it was first written" in out, out


def test_a_spec_first_written_on_the_branch_is_pointed_at(tmp_path):
    """I4 names the commit, so the Author can find the six fields they are asked to have read."""
    repo = build(FIXTURES / "gate" / "I4_spec_first_written_on_branch", tmp_path)
    second = git(repo, "rev-parse", "--short", "HEAD").strip()
    _, out, _ = run_slp(["gate", "--base", "base"], repo)
    assert "meta.spec was first written on this branch, in commit %s by Fixture;" % second in out, out


def test_nothing_changed_says_so(tmp_path):
    repo = build(QUIET, tmp_path)
    code, out, _ = run_slp(["gate", "--base", "base"], repo)
    assert (code, out) == (0, "slp gate: OK (no changes)\n")


def test_head_at_the_merge_base_is_not_a_pull_request(tmp_path):
    repo = build(QUIET, tmp_path)
    code, out, _ = run_slp(["gate", "--base", "HEAD"], repo)
    assert (code, out) == (0, "slp gate: OK (no commits)\n")


def test_outside_a_git_repository_it_refuses_to_judge(tmp_path):
    """R3: no history means nothing to compare, which is an error, not a pass."""
    (tmp_path / "models" / "marts").mkdir(parents=True)
    code, _, err = run_slp(["gate", "--base", "main"], tmp_path)
    assert code == 2
    assert err.startswith("ERROR git merge-base") and "not a git repository" in err


def test_a_base_that_does_not_exist_is_an_error(tmp_path):
    repo = build(QUIET, tmp_path)
    code, _, err = run_slp(["gate", "--base", "no-such-branch"], repo)
    assert code == 2
    assert err.startswith("ERROR git merge-base")


def test_a_merge_commit_in_the_range_is_walked_first_parent(tmp_path):
    """A branch merged into the PR must not make the walk explode or double count."""
    repo = build(QUIET, tmp_path)
    git(repo, "checkout", "-q", "-b", "side", "base")
    (repo / "models" / "marts" / "side.yml").write_text(
        "models:\n  - name: fct_side\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "side commit")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    code, out, _ = run_slp(["gate", "--base", "base"], repo)
    assert code == 0, out
    # first-parent: the two commits on main, not the one that arrived through the merge
    assert out == "slp gate: OK (2 commits)\n"


def test_the_inventory_is_the_same_for_the_same_commit(tmp_path):
    """The rules compare inventories, so an inventory must be a pure function of a commit."""
    repo = build(QUIET, tmp_path)
    head = git(repo, "rev-parse", "HEAD").strip()
    assert slp.inventory(repo, head) == slp.inventory(repo, head)


def test_the_inventory_holds_what_the_rules_compare(tmp_path):
    repo = build(QUIET, tmp_path)
    inv = slp.inventory(repo, "HEAD")
    assert inv["tests"] == {("fct_orders", "order_id", "unique", "{}"): [{}]}
    assert inv["where"] == {"fct_orders": "models/marts/fct_orders.yml"}
    assert list(inv["models"]) == ["fct_orders"]
    assert inv["units"] == {} and inv["files"] == {} and inv["packages"] == {}


def test_a_light_inventory_reads_only_the_yml_files(tmp_path):
    """The commit walk needs specs and pre-registrations, not every file hash."""
    repo = build(QUIET, tmp_path)
    (repo / "packages.yml").write_text("packages: []\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add packages")
    assert slp.inventory(repo, "HEAD")["packages"] != {}
    assert slp.inventory(repo, "HEAD", full=False)["packages"] == {}


def test_every_file_at_one_commit_is_read_in_one_git_process(tmp_path, monkeypatch):
    """One process per file made the commit walk quadratic in a real project."""
    repo = build(QUIET, tmp_path)
    for n in range(12):
        (repo / "models" / "marts" / ("m%02d.yml" % n)).write_text(
            "models:\n  - name: fct_m%02d\n" % n, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "twelve more models")
    calls = []
    real = slp.subprocess.run
    monkeypatch.setattr(slp.subprocess, "run",
                        lambda *a, **k: (calls.append(a[0][3]), real(*a, **k))[1])
    slp.inventory(repo, "HEAD")
    # ls-tree, then one cat-file for the thirteen yml and the one sql.
    assert calls == ["ls-tree", "cat-file"], calls


def test_a_file_with_multibyte_characters_is_read_whole(tmp_path):
    """cat-file sizes blobs in bytes; splitting the stream by characters loses them."""
    repo = build(QUIET, tmp_path)
    (repo / "models" / "marts" / "acentos.yml").write_text(
        'models:\n  - name: fct_reconciliação\n    description: "não é ascii"\n',
        encoding="utf-8")
    (repo / "models" / "marts" / "after.yml").write_text(
        "models:\n  - name: fct_after\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "accents")
    inv = slp.inventory(repo, "HEAD")
    # The file after the multibyte one still parses, which it cannot if the
    # stream was cut in the wrong place.
    assert "fct_reconciliação" in inv["where"] and "fct_after" in inv["where"]
