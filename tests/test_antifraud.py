from conftest import DECLINED_CARD


def decline_three_times(pay):
    for _ in range(3):
        assert pay(amount="6000.00").status_code == 402  # acima do limite


def test_three_declines_block_the_card(pay):
    decline_three_times(pay)

    resp = pay()

    assert resp.status_code == 429
    assert "error" in resp.get_json()


def test_block_only_affects_that_card(pay):
    for _ in range(3):
        pay(card_number=DECLINED_CARD)

    assert pay(card_number=DECLINED_CARD).status_code == 429
    assert pay().status_code == 201


def test_block_ends_after_one_hour(pay, clock):
    decline_three_times(pay)

    clock.advance(minutes=59)
    assert pay().status_code == 429
    clock.advance(minutes=1)
    assert pay().status_code == 201


def test_declines_spread_over_more_than_ten_minutes_do_not_block(pay, clock):
    pay(amount="6000.00")
    clock.advance(minutes=6)
    pay(amount="6000.00")
    clock.advance(minutes=6)  # a 1ª recusa já tem 12 minutos
    pay(amount="6000.00")

    assert pay().status_code == 201


def test_pix_does_not_go_through_antifraud(pay):
    decline_three_times(pay)

    assert pay(method="pix").status_code == 201
