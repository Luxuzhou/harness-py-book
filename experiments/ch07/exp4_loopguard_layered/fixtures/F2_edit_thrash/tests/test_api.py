import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from api import (process_user, process_order, process_payment,
                 process_shipment, process_refund)


def test_user_default():
    assert process_user({"id": 1})["status"] == "pending"


def test_user_active():
    assert process_user({"id": 1, "active": True})["status"] == "active"


def test_order_default():
    assert process_order({"id": 1})["status"] == "pending"


def test_payment_default():
    """关键测试：payment 的初始 status 应该是 'init' 而非 'pending'。"""
    assert process_payment({"id": 1})["status"] == "init"


def test_payment_complete():
    assert process_payment({"id": 1, "amount": 100})["status"] == "complete"


def test_shipment_default():
    assert process_shipment({"id": 1})["status"] == "pending"


def test_refund_default():
    assert process_refund({"id": 1})["status"] == "pending"
