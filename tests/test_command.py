import pytest

from fake_ssh.command import CommandFailure
from fake_ssh.command import CommandResult
from fake_ssh.command import command_handler_wrapper


@pytest.mark.parametrize(
    "command_result, expected_command_result_wrapped",
    [
        (
            CommandResult(stdout="a", stderr="b", returncode=2),
            CommandResult(stdout="a", stderr="b", returncode=2),
        ),
        ("file1", CommandResult(stdout="file1")),
        (None, CommandResult()),
    ],
)
def test_command_handler_wrapper_success(command_result, expected_command_result_wrapped):
    assert command_handler_wrapper(lambda command: command_result)("") == expected_command_result_wrapped


def throw(exception):
    raise exception


@pytest.mark.parametrize(
    "exception, expected_command_result_wrapped",
    [
        (
            CommandFailure(stderr="b", returncode=2),
            CommandResult(stderr="b", returncode=2),
        ),
        (
            ValueError("bad value"),
            CommandResult(stderr="bad value", returncode=1),
        ),
    ],
)
def test_command_handler_wrapper_failure(exception, expected_command_result_wrapped):
    assert command_handler_wrapper(lambda command: throw(exception))("") == expected_command_result_wrapped


def test_command_handler_illegal_output():
    with pytest.raises(TypeError):
        command_handler_wrapper(lambda command: object())("")  # noqa
