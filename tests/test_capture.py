def test_capture_full_authorization(client, pay):
    payment_id = pay(capture=False).get_json()["id"]

    resp = client.post(f"/payments/{payment_id}/capture")

    assert resp.status_code == 200
    payment = resp.get_json()
    assert payment["status"] == "CAPTURED"
    assert payment["captured_amount"] == "100.00"
    assert payment["fee"] == "2.99"


def test_partial_capture(client, pay, clock):
    payment_id = pay(amount="300.00", capture=False).get_json()["id"]
    clock.advance(days=2)

    payment = client.post(f"/payments/{payment_id}/capture", json={"amount": "180.00"}).get_json()

    assert payment["status"] == "CAPTURED"
    assert payment["amount"] == "300.00"
    assert payment["captured_amount"] == "180.00"
    assert payment["fee"] == "5.38"
    assert payment["net_amount"] == "174.62"
    assert payment["captured_at"] == "2026-03-04T10:00:00"


def test_capture_above_authorized_returns_400(client, pay):
    payment_id = pay(capture=False).get_json()["id"]

    resp = client.post(f"/payments/{payment_id}/capture", json={"amount": "100.01"})

    assert resp.status_code == 400


def test_capture_twice_returns_409(client, pay):
    payment_id = pay().get_json()["id"]

    assert client.post(f"/payments/{payment_id}/capture").status_code == 409


def test_void_authorization(client, pay):
    payment_id = pay(capture=False).get_json()["id"]

    resp = client.post(f"/payments/{payment_id}/void")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "VOIDED"
    assert client.post(f"/payments/{payment_id}/capture").status_code == 409


def test_void_after_capture_returns_409(client, pay):
    payment_id = pay().get_json()["id"]

    assert client.post(f"/payments/{payment_id}/void").status_code == 409


def test_expire_job_expires_old_authorization(client, pay, clock):
    payment_id = pay(capture=False).get_json()["id"]
    clock.advance(days=7)

    resp = client.post("/jobs/expire-authorizations")

    assert resp.status_code == 200
    assert resp.get_json() == {"expired": [payment_id]}
    assert client.get(f"/payments/{payment_id}").get_json()["status"] == "EXPIRED"
    assert client.post(f"/payments/{payment_id}/capture").status_code == 409


def test_expire_job_keeps_recent_authorizations(client, pay, clock):
    old = pay(capture=False).get_json()["id"]
    clock.advance(days=3)
    recent = pay(capture=False).get_json()["id"]
    clock.advance(days=4)  # a primeira tem 7 dias; a segunda, 4

    assert client.post("/jobs/expire-authorizations").get_json() == {"expired": [old]}
    assert client.get(f"/payments/{recent}").get_json()["status"] == "AUTHORIZED"
    assert client.post(f"/payments/{recent}/capture").status_code == 200
