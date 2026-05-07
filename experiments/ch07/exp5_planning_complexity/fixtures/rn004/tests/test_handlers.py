import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.handlers import handle_user_request, handle_post_request
from src.api import fetch_user, fetch_post, fetch_comment
from src.middleware import authenticate, audit_log
from src.cli import render_user, render_comment


def test_handle_user():
    user = handle_user_request(1)
    assert user["id"] == 1


def test_handle_post():
    post = handle_post_request(2)
    assert post["id"] == 2


def test_fetch_comment_direct():
    comment = fetch_comment(3)
    assert comment["id"] == 3


def test_authenticate():
    assert authenticate(5) is True


def test_audit_log():
    log = audit_log(7)
    assert log["audited_user"] == "user_7"


def test_render_user():
    assert render_user(9) == "user: user_9"


def test_render_comment():
    assert render_comment(11) == "comment: comment_11"
