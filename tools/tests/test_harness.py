"""The test harness itself (SLP-23): if it lies, every other test lies with it."""

from conftest import assert_expected, expectation, findings, git, make_repo


def _tree(root, name, files):
    folder = root / name
    for path, text in files.items():
        target = folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return folder


def test_make_repo_makes_one_commit_per_tree_and_tags_the_first(tmp_path):
    before = _tree(tmp_path, "before", {"models/marts/a.yml": "models: []\n",
                                        "tests/gone.sql": "select 1\n"})
    after = _tree(tmp_path, "after", {"models/marts/a.yml": "models: []\n"})
    repo = make_repo(tmp_path, before, after)
    assert len(git(repo, "rev-list", "HEAD").split()) == 2
    assert git(repo, "rev-parse", "base").strip() == git(repo, "rev-list", "--max-parents=0", "HEAD").strip()
    # A tree is a whole snapshot: what it leaves out is deleted, so a fixture can
    # express a removed file.
    assert not (repo / "tests" / "gone.sql").exists()
    assert "tests/gone.sql" in git(repo, "ls-tree", "-r", "--name-only", "base")


def test_an_edit_of_the_same_size_still_reaches_the_commit(tmp_path):
    """git trusts size and mtime; two fixture trees are written in the same second."""
    before = _tree(tmp_path, "before", {"models/marts/a.yml": "models: [{name: aaa}]\n"})
    after = _tree(tmp_path, "after", {"models/marts/a.yml": "models: [{name: bbb}]\n"})
    repo = make_repo(tmp_path, before, after)
    assert "bbb" in git(repo, "show", "HEAD:models/marts/a.yml")


def test_two_runs_build_the_same_commits(tmp_path):
    """R4: the same fixture in, the same repository out, so the same output out."""
    tree = _tree(tmp_path, "tree", {"models/marts/a.yml": "models: []\n"})
    first = make_repo(tmp_path / "one", tree)
    second = make_repo(tmp_path / "two", tree)
    assert git(first, "rev-parse", "HEAD") == git(second, "rev-parse", "HEAD")


def test_findings_reads_the_output_format():
    line = "BLOCK\tmodels/marts/orders.yml\tfct_orders\ttest removed\t[G1]\n"
    assert findings("noise\n" + line + "slp gate: 1 block - BLOCKED\n") == [
        ("BLOCK", "models/marts/orders.yml", "fct_orders", "test removed", "G1")]


def test_the_folder_name_is_the_expectation(tmp_path):
    assert expectation(tmp_path / "G1_removed_unique")["exit"] == 1
    assert expectation(tmp_path / "G1_removed_unique")["rules"] == ["G1"]
    assert expectation(tmp_path / "G1_ok_test_added")["exit"] == 0
    assert expectation(tmp_path / "G1_ok_test_added")["absent"] == ["G1"]


def test_a_readme_can_say_what_the_name_cannot(tmp_path):
    folder = tmp_path / "I1_two_edits"
    folder.mkdir()
    (folder / "README.txt").write_text("counts edits, never blocks.\n"
                                       "expect exit 0\nexpect rules I1\nexpect count 1\n")
    want = expectation(folder)
    assert (want["exit"], want["rules"], want["count"]) == (0, ["I1"], 1)
    out = "INFO\tmodels/marts/a.yml\tfct_a\tchanged 2 times\t[I1]\n"
    assert len(assert_expected(folder, 0, out)) == 1
