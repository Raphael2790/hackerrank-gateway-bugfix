from datetime import datetime


def test_cannot_capture_after_7_days_without_running_expiration_job(client, pay, clock):
    """Tenta capturar uma pré-autorização após 7 dias SEM rodar a rotina de expiração.
    Deveria falhar com 409 porque a autorização expirou (mesmo que status ainda seja AUTHORIZED)."""

    # Cria pré-autorização às 10:00 de segunda
    clock.set(datetime(2026, 3, 2, 10, 0, 0))
    response = pay(capture=False)
    payment_id = response.get_json()["id"]

    # Avança 7 dias
    clock.advance(days=7)

    # Tenta capturar DIRETO (sem rodar /jobs/expire-authorizations)
    # A captura deveria falhar porque a autorização expirou
    capture_response = client.post(f"/payments/{payment_id}/capture")

    print(f"Status: {capture_response.status_code}")
    print(f"Response: {capture_response.get_json()}")

    # Esperado: 409 (autorização expirada)
    assert capture_response.status_code == 409, \
        f"Deveria retornar 409 (autorização expirada), obtido {capture_response.status_code}"


def test_can_capture_before_7_days(client, pay, clock):
    """Deveria conseguir capturar uma pré-autorização ANTES de 7 dias."""

    # Cria pré-autorização
    clock.set(datetime(2026, 3, 2, 10, 0, 0))
    response = pay(capture=False)
    payment_id = response.get_json()["id"]

    # Avança 6 dias (menos que 7)
    clock.advance(days=6)

    # Tenta capturar
    capture_response = client.post(f"/payments/{payment_id}/capture")

    # Deveria funcionar (200)
    assert capture_response.status_code == 200, \
        f"Deveria conseguir capturar antes de 7 dias, obtido {capture_response.status_code}"


def test_cannot_capture_more_than_7_days_later(client, pay, clock):
    """Tenta capturar após mais de 7 dias. Deveria falhar."""

    # Cria pré-autorização
    clock.set(datetime(2026, 3, 2, 10, 0, 0))
    response = pay(capture=False)
    payment_id = response.get_json()["id"]

    # Avança 8 dias
    clock.advance(days=8)

    # Tenta capturar
    capture_response = client.post(f"/payments/{payment_id}/capture")

    # Deveria falhar (409)
    assert capture_response.status_code == 409, \
        f"Deveria falhar após 8 dias, obtido {capture_response.status_code}"
