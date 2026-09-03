"""The wrapper carries the entry's central claim, so it is tested like it does."""

import pytest
import yaml

from elenchos.provision.wrapper import EmptyScript, strip_fences, wrap


def run_body_of(step_yaml):
    """Parse the step the way a runner would, and hand back the shell it would execute."""
    parsed = yaml.safe_load(step_yaml)
    assert isinstance(parsed, list) and len(parsed) == 1
    return parsed[0]["run"]


def test_wraps_plain_script_into_parseable_yaml():
    step = wrap("echo hello\nexit 0")
    assert run_body_of(step) == "echo hello\nexit 0\n"


def test_column_zero_lines_survive_because_they_are_indented():
    """Experiment A's single biggest failure: five of twenty answers died on this."""
    script = "python3 - <<'PY'\nimport sys\nsys.exit(1)\nPY"
    assert run_body_of(wrap(script)) == script + "\n"


def test_step_name_containing_a_colon_stays_valid_yaml():
    """`name: No security step carries continue-on-error: true` is invalid YAML unquoted.

    The hand-written oracle hit this too, which is how it was found.
    """
    step = wrap("exit 0", name="No security step carries continue-on-error: true")
    parsed = yaml.safe_load(step)
    assert parsed[0]["name"] == "No security step carries continue-on-error: true"


def test_markdown_fences_are_stripped():
    assert strip_fences("```bash\necho hi\n```") == "echo hi"


def test_blank_lines_inside_the_script_are_preserved_not_indented():
    body = run_body_of(wrap("echo one\n\necho two"))
    assert body == "echo one\n\necho two\n"


def test_empty_script_raises_rather_than_producing_a_step_that_always_passes():
    """Silence must not become a green check. That is the defect the product sells."""
    for empty in ("", "   \n\n", "```\n```"):
        with pytest.raises(EmptyScript):
            wrap(empty)


def test_wrapper_does_not_repair_logic():
    """Anything beyond indentation would be a repair the kill test never measured."""
    broken = "if [ -f x ; then\n  exit 1\nfi"
    assert run_body_of(wrap(broken)) == broken + "\n"
