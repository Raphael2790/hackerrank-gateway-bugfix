from conftest import DECLINED_CARD, OTHER_APPROVED_CARD


def test_replay_returns_original_payment(client, pay):
    first = pay(key="pedido-1")
    replay = pay(key="pedido-1")

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.get_json() == first.get_json()
    assert client.get("/payments/2").status_code == 404  # não cobrou de novo


def test_same_key_with_different_body_returns_422(pay):
    assert pay(key="pedido-1").status_code == 201

    assert pay(key="pedido-1", amount="150.00").status_code == 422


def test_keys_are_scoped_by_merchant(pay):
    first = pay(key="pedido-1", merchant_id=1)
    second = pay(key="pedido-1", merchant_id=2)

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.get_json()["id"] != second.get_json()["id"]


def test_retry_after_declined_card_with_same_key(pay):
    assert pay(key="pedido-1", card_number=DECLINED_CARD).status_code == 402

    assert pay(key="pedido-1", card_number=OTHER_APPROVED_CARD).status_code == 201


def test_retry_after_card_block_with_same_key(pay, clock):
    for _ in range(3):
        assert pay(amount="6000.00").status_code == 402
    assert pay(key="pedido-1").status_code == 429

    clock.advance(hours=1)

    assert pay(key="pedido-1").status_code == 201
