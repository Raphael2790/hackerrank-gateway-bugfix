def test_full_refund(client, pay):
    payment_id = pay().get_json()["id"]

    resp = client.post(f"/payments/{payment_id}/refund")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["refunded"] == "100.00"
    assert data["payment"]["status"] == "REFUNDED"
    assert data["payment"]["refunded_amount"] == "100.00"


def test_partial_refunds(client, pay):
    payment_id = pay().get_json()["id"]
    url = f"/payments/{payment_id}/refund"

    assert client.post(url, json={"amount": "30.00"}).get_json()["payment"]["status"] == "PARTIALLY_REFUNDED"
    assert client.post(url, json={"amount": "70.00"}).get_json()["payment"]["status"] == "REFUNDED"
    assert client.post(url, json={"amount": "0.01"}).status_code == 409


def test_refund_above_available_returns_409(client, pay):
    payment_id = pay().get_json()["id"]

    resp = client.post(f"/payments/{payment_id}/refund", json={"amount": "100.01"})

    assert resp.status_code == 409


def test_refund_of_authorization_returns_409(client, pay):
    payment_id = pay(capture=False).get_json()["id"]

    assert client.post(f"/payments/{payment_id}/refund").status_code == 409


def test_refund_is_debited_from_merchant_balance(client, pay):
    payment_id = pay(method="pix").get_json()["id"]  # 99,01 disponível hoje

    client.post(f"/payments/{payment_id}/refund", json={"amount": "40.00"})

    entries = client.get("/merchants/1/receivables").get_json()
    assert entries[-1] == {
        "payment_id": payment_id,
        "installment": None,
        "amount": "-40.00",
        "settle_date": "2026-03-02",
        "kind": "REFUND",
    }
    assert client.get("/merchants/1/balance").get_json()["available"] == "59.01"
