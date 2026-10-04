from datetime import datetime


def test_authorization_expires_after_7_days(client, pay, clock):
    """Pré-autorização deve expirar após 7 dias e não pode ser capturada."""
    # Cria pré-autorização
    response = pay(capture=False)
    payment_id = response.get_json()["id"]

    # Avança 7 dias
    clock.advance(days=7)

    # Roda a rotina de expiração
    expire_response = client.post("/jobs/expire-authorizations")
    expired_ids = expire_response.get_json()["expired"]

    # Verifica se o pagamento foi expirado
    assert payment_id in expired_ids, f"Pagamento {payment_id} não foi expirado"

    # Tenta capturar - deveria falhar com 409
    capture_response = client.post(f"/payments/{payment_id}/capture")
    assert capture_response.status_code == 409, f"Esperado 409, obtido {capture_response.status_code}"


def test_authorization_expires_after_more_than_7_days(client, pay, clock):
    """Pré-autorização com 7+ dias deve ser expirada pela rotina."""
    # Cria pré-autorização
    response = pay(capture=False)
    payment_id = response.get_json()["id"]

    # Avança 8 dias (mais que 7)
    clock.advance(days=8)

    # Roda a rotina de expiração
    expire_response = client.post("/jobs/expire-authorizations")
    expired_ids = expire_response.get_json()["expired"]

    # Verifica se o pagamento foi expirado
    assert payment_id in expired_ids, f"Pagamento {payment_id} não foi expirado após 8 dias"


def test_authorization_still_valid_before_7_days(client, pay, clock):
    """Pré-autorização com menos de 7 dias NÃO deve expirar."""
    # Cria pré-autorização
    response = pay(capture=False)
    payment_id = response.get_json()["id"]

    # Avança 6 dias (menos que 7)
    clock.advance(days=6)

    # Roda a rotina de expiração
    expire_response = client.post("/jobs/expire-authorizations")
    expired_ids = expire_response.get_json()["expired"]

    # Verifica que o pagamento NÃO foi expirado
    assert payment_id not in expired_ids, f"Pagamento {payment_id} foi expirado antes de 7 dias"

    # Deveria conseguir capturar
    capture_response = client.post(f"/payments/{payment_id}/capture")
    assert capture_response.status_code == 200, f"Deveria conseguir capturar, obtido {capture_response.status_code}"
