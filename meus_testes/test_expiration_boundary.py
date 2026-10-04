from datetime import datetime, timedelta


def test_authorization_expires_exactly_at_7_days(client, pay, clock):
    """Pré-autorização criada às 14:30 deve expirar às 14:30 de 7 dias depois."""
    # Cria pré-autorização às 14:30 de segunda
    clock.set(datetime(2026, 3, 2, 14, 30, 0))
    response = pay(capture=False)
    payment_id = response.get_json()["id"]

    # Avança exatamente 7 dias (para 14:30 de segunda seguinte)
    clock.advance(days=7)

    # Roda a rotina de expiração
    expire_response = client.post("/jobs/expire-authorizations")
    expired_ids = expire_response.get_json()["expired"]

    # Deve estar expirada
    assert payment_id in expired_ids, f"Pagamento {payment_id} deveria estar expirado após exatamente 7 dias"


def test_authorization_does_not_expire_before_7_days(client, pay, clock):
    """Pré-autorização criada às 14:30 NÃO deve expirar aos 23:59 (6d 9h 29m depois)."""
    # Cria pré-autorização às 14:30 de segunda
    clock.set(datetime(2026, 3, 2, 14, 30, 0))
    response = pay(capture=False)
    payment_id = response.get_json()["id"]

    # Avança 6 dias e 23 horas e 59 minutos (falta 1 minuto para 7 dias)
    clock.advance(days=6, hours=23, minutes=59)

    # Roda a rotina de expiração
    expire_response = client.post("/jobs/expire-authorizations")
    expired_ids = expire_response.get_json()["expired"]

    # Não deveria estar expirada
    assert payment_id not in expired_ids, f"Pagamento {payment_id} expirou antes de 7 dias"

    # Deveria conseguir capturar
    capture_response = client.post(f"/payments/{payment_id}/capture")
    assert capture_response.status_code == 200, f"Deveria conseguir capturar, obtido {capture_response.status_code}"


def test_authorization_expires_just_after_7_days(client, pay, clock):
    """Pré-autorização criada às 14:30 deve expirar 1 minuto após 7 dias completos."""
    # Cria pré-autorização às 14:30 de segunda
    clock.set(datetime(2026, 3, 2, 14, 30, 0))
    response = pay(capture=False)
    payment_id = response.get_json()["id"]

    # Avança 7 dias + 1 minuto
    clock.advance(days=7, minutes=1)

    # Roda a rotina de expiração
    expire_response = client.post("/jobs/expire-authorizations")
    expired_ids = expire_response.get_json()["expired"]

    # Deveria estar expirada
    assert payment_id in expired_ids, f"Pagamento {payment_id} deveria estar expirado após 7 dias e 1 minuto"


def test_authorization_does_not_expire_one_second_before_7_days(client, pay, clock):
    """Pré-autorização criada às 14:30:00 NÃO deve expirar às 14:29:59 de 7 dias depois."""
    # Cria pré-autorização às 14:30:00 de segunda
    clock.set(datetime(2026, 3, 2, 14, 30, 0))
    response = pay(capture=False)
    payment_id = response.get_json()["id"]

    # Avança 6 dias, 23 horas, 59 minutos e 59 segundos (1 segundo antes de 7 dias)
    clock.set(datetime(2026, 3, 9, 14, 29, 59))

    # Roda a rotina de expiração
    expire_response = client.post("/jobs/expire-authorizations")
    expired_ids = expire_response.get_json()["expired"]

    # Não deveria estar expirada
    assert payment_id not in expired_ids, f"Pagamento {payment_id} expirou 1 segundo antes de 7 dias"
