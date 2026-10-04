"""Documentação OpenAPI 3 da API, servida pela própria aplicação.

- `GET /openapi.json`: a especificação.
- `GET /docs`: Swagger UI (carrega os assets de um CDN, então precisa de internet).

Isto é só documentação: nenhuma rota de negócio passa por aqui.
"""

from flask import Blueprint, jsonify

docs = Blueprint("docs", __name__)

CARD_OK = "4111111111111111"
CARD_OK_2 = "5555444433331111"
CARD_DECLINED = "4000000000000002"

ERROR_SCHEMA = {
    "type": "object",
    "properties": {"error": {"type": "string", "example": "Lojista 9 não encontrado"}},
}


def _error(description: str, example: str) -> dict:
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Error"},
                "example": {"error": example},
            }
        },
    }


PAYMENT_EXAMPLE = {
    "id": 1,
    "merchant_id": 1,
    "method": "credit",
    "amount": "250.00",
    "installments": 3,
    "card_last4": "1111",
    "status": "CAPTURED",
    "created_at": "2026-03-02T10:00:00",
    "captured_amount": "250.00",
    "captured_at": "2026-03-02T10:00:00",
    "fee": "9.98",
    "net_amount": "240.02",
    "refunded_amount": "0.00",
}

AUTHORIZED_EXAMPLE = {
    **PAYMENT_EXAMPLE,
    "id": 2,
    "amount": "300.00",
    "installments": 1,
    "status": "AUTHORIZED",
    "captured_amount": "0.00",
    "captured_at": None,
    "fee": "0.00",
    "net_amount": "0.00",
}

SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "PayFlow API",
        "version": "1.0.0",
        "description": (
            "Gateway de pagamentos (treino). Valores monetários são strings com 2 casas "
            '("59.90"); na entrada aceitam string ou número. Datas e horas são locais, '
            'sem fuso ("2026-03-02T10:00:00").\n\n'
            "Lojistas cadastrados: `1` (Loja Aurora) e `2` (Café Central).\n\n"
            f"Cartões de teste: `{CARD_OK}` e `{CARD_OK_2}` aprovados, "
            f"`{CARD_DECLINED}` recusado (qualquer cartão terminado em `0002` é recusado). "
            "Autorizações acima de R$ 5.000,00 também são recusadas.\n\n"
            "Os dados ficam em memória e voltam ao estado inicial quando a API reinicia."
        ),
    },
    "servers": [{"url": "http://127.0.0.1:5000", "description": "Local"}],
    "tags": [
        {"name": "Lojistas", "description": "Dados, agenda de recebíveis e saldo"},
        {"name": "Pagamentos", "description": "Criação, captura, cancelamento e estorno"},
        {"name": "Rotinas", "description": "Jobs chamados pelo agendador"},
    ],
    "components": {
        "schemas": {
            "Error": ERROR_SCHEMA,
            "Merchant": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 1},
                    "name": {"type": "string", "example": "Loja Aurora"},
                },
            },
            "Money": {
                "type": "string",
                "description": "Valor com 2 casas decimais",
                "example": "250.00",
            },
            "Payment": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "merchant_id": {"type": "integer"},
                    "method": {"type": "string", "enum": ["pix", "debit", "credit"]},
                    "amount": {"$ref": "#/components/schemas/Money"},
                    "installments": {"type": "integer"},
                    "card_last4": {"type": "string", "nullable": True, "example": "1111"},
                    "status": {
                        "type": "string",
                        "enum": [
                            "AUTHORIZED",
                            "CAPTURED",
                            "VOIDED",
                            "EXPIRED",
                            "PARTIALLY_REFUNDED",
                            "REFUNDED",
                        ],
                    },
                    "created_at": {
                        "type": "string",
                        "format": "date-time",
                        "example": "2026-03-02T10:00:00",
                    },
                    "captured_amount": {"$ref": "#/components/schemas/Money"},
                    "captured_at": {
                        "type": "string",
                        "format": "date-time",
                        "nullable": True,
                        "example": "2026-03-02T10:00:00",
                    },
                    "fee": {"$ref": "#/components/schemas/Money"},
                    "net_amount": {"$ref": "#/components/schemas/Money"},
                    "refunded_amount": {"$ref": "#/components/schemas/Money"},
                },
                "example": PAYMENT_EXAMPLE,
            },
            "CreatePaymentRequest": {
                "type": "object",
                "required": ["merchant_id", "amount", "method"],
                "properties": {
                    "merchant_id": {"type": "integer", "example": 1},
                    "amount": {
                        "description": "String ou número, positivo, com até 2 casas",
                        "oneOf": [{"type": "string"}, {"type": "number"}],
                        "example": "250.00",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["pix", "debit", "credit"],
                        "example": "credit",
                    },
                    "installments": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 12,
                        "default": 1,
                        "description": "No crédito, 1 a 12. PIX e débito só aceitam 1.",
                        "example": 3,
                    },
                    "card_number": {
                        "type": "string",
                        "description": "16 dígitos. Obrigatório no débito e no crédito; ignorado no PIX.",
                        "example": CARD_OK,
                    },
                    "capture": {
                        "type": "boolean",
                        "default": True,
                        "description": (
                            "No crédito, `false` faz só a pré-autorização (AUTHORIZED). "
                            "PIX e débito são sempre capturados na hora."
                        ),
                        "example": True,
                    },
                },
            },
            "AmountBody": {
                "type": "object",
                "properties": {"amount": {"$ref": "#/components/schemas/Money"}},
            },
            "Receivable": {
                "type": "object",
                "properties": {
                    "payment_id": {"type": "integer", "example": 1},
                    "installment": {
                        "type": "integer",
                        "nullable": True,
                        "description": "Número da parcela no crédito; `null` nos outros lançamentos",
                        "example": 1,
                    },
                    "amount": {"$ref": "#/components/schemas/Money"},
                    "settle_date": {
                        "type": "string",
                        "format": "date",
                        "example": "2026-04-01",
                    },
                    "kind": {"type": "string", "enum": ["SALE", "REFUND"], "example": "SALE"},
                },
            },
            "Balance": {
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "integer", "example": 1},
                    "date": {"type": "string", "format": "date", "example": "2026-03-02"},
                    "available": {"$ref": "#/components/schemas/Money"},
                    "pending": {"$ref": "#/components/schemas/Money"},
                },
                "example": {
                    "merchant_id": 1,
                    "date": "2026-03-02",
                    "available": "0.00",
                    "pending": "240.02",
                },
            },
            "RefundResponse": {
                "type": "object",
                "properties": {
                    "refunded": {"$ref": "#/components/schemas/Money"},
                    "payment": {"$ref": "#/components/schemas/Payment"},
                },
            },
            "ExpireResponse": {
                "type": "object",
                "properties": {
                    "expired": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Ids das autorizações marcadas como EXPIRED",
                        "example": [3, 5],
                    }
                },
            },
        },
        "parameters": {
            "MerchantId": {
                "name": "merchant_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer", "example": 1},
            },
            "PaymentId": {
                "name": "payment_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer", "example": 1},
            },
            "IdempotencyKey": {
                "name": "Idempotency-Key",
                "in": "header",
                "required": False,
                "description": (
                    "Chave de idempotência, válida por lojista. Mesma chave e mesmo corpo "
                    "devolvem o pagamento original com 200."
                ),
                "schema": {"type": "string", "example": "pedido-1"},
            },
        },
    },
    "paths": {
        "/merchants/{merchant_id}": {
            "get": {
                "tags": ["Lojistas"],
                "summary": "Dados do lojista",
                "parameters": [{"$ref": "#/components/parameters/MerchantId"}],
                "responses": {
                    "200": {
                        "description": "Lojista encontrado",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Merchant"},
                                "example": {"id": 1, "name": "Loja Aurora"},
                            }
                        },
                    },
                    "404": _error("Lojista inexistente", "Lojista 9 não encontrado"),
                },
            }
        },
        "/merchants/{merchant_id}/receivables": {
            "get": {
                "tags": ["Lojistas"],
                "summary": "Agenda de recebíveis, por data",
                "description": (
                    "PIX liquida no mesmo dia da captura (inclusive fim de semana), débito em D+1 "
                    "e crédito em uma parcela por mês (D+30×i). No débito e no crédito, data em "
                    "sábado ou domingo vai para a segunda-feira seguinte. Estornos entram como "
                    "lançamento negativo com `kind: REFUND`."
                ),
                "parameters": [{"$ref": "#/components/parameters/MerchantId"}],
                "responses": {
                    "200": {
                        "description": "Lançamentos ordenados por data de liquidação",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Receivable"},
                                },
                                "example": [
                                    {
                                        "payment_id": 1,
                                        "installment": 1,
                                        "amount": "80.02",
                                        "settle_date": "2026-04-01",
                                        "kind": "SALE",
                                    },
                                    {
                                        "payment_id": 1,
                                        "installment": 2,
                                        "amount": "80.00",
                                        "settle_date": "2026-05-01",
                                        "kind": "SALE",
                                    },
                                    {
                                        "payment_id": 1,
                                        "installment": 3,
                                        "amount": "80.00",
                                        "settle_date": "2026-06-01",
                                        "kind": "SALE",
                                    },
                                ],
                            }
                        },
                    },
                    "404": _error("Lojista inexistente", "Lojista 9 não encontrado"),
                },
            }
        },
        "/merchants/{merchant_id}/balance": {
            "get": {
                "tags": ["Lojistas"],
                "summary": "Saldo disponível e a receber",
                "description": (
                    "`available` é a soma do que vence até a data, inclusive; `pending` é o que "
                    "vence depois. Sem `date`, usa hoje."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/MerchantId"},
                    {
                        "name": "date",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "format": "date",
                            "example": "2026-12-31",
                        },
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Saldo na data",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Balance"}
                            }
                        },
                    },
                    "400": _error("Data inválida", "Data inválida: '31-12-2026' (use AAAA-MM-DD)"),
                    "404": _error("Lojista inexistente", "Lojista 9 não encontrado"),
                },
            }
        },
        "/payments": {
            "post": {
                "tags": ["Pagamentos"],
                "summary": "Cria o pagamento",
                "description": (
                    "Retorna 201 na criação e 200 quando a `Idempotency-Key` repetida com o mesmo "
                    "corpo devolve o pagamento original. Uma tentativa que falhou (400, 402 ou 429) "
                    "não gasta a chave."
                ),
                "parameters": [{"$ref": "#/components/parameters/IdempotencyKey"}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CreatePaymentRequest"},
                            "examples": {
                                "credito_parcelado": {
                                    "summary": "Crédito 3x, captura imediata",
                                    "value": {
                                        "merchant_id": 1,
                                        "amount": "250.00",
                                        "method": "credit",
                                        "installments": 3,
                                        "card_number": CARD_OK,
                                    },
                                },
                                "pre_autorizacao": {
                                    "summary": "Crédito à vista, só pré-autorização",
                                    "value": {
                                        "merchant_id": 1,
                                        "amount": "300.00",
                                        "method": "credit",
                                        "card_number": CARD_OK,
                                        "capture": False,
                                    },
                                },
                                "debito": {
                                    "summary": "Débito (sempre capturado na hora)",
                                    "value": {
                                        "merchant_id": 1,
                                        "amount": "59.90",
                                        "method": "debit",
                                        "card_number": CARD_OK_2,
                                    },
                                },
                                "pix": {
                                    "summary": "PIX (sem cartão)",
                                    "value": {
                                        "merchant_id": 2,
                                        "amount": "120.00",
                                        "method": "pix",
                                    },
                                },
                                "recusado": {
                                    "summary": "Cartão recusado pela operadora (402)",
                                    "value": {
                                        "merchant_id": 1,
                                        "amount": "100.00",
                                        "method": "credit",
                                        "card_number": CARD_DECLINED,
                                    },
                                },
                            },
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Pagamento criado",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Payment"},
                                "examples": {
                                    "capturado": {"value": PAYMENT_EXAMPLE},
                                    "pre_autorizado": {"value": AUTHORIZED_EXAMPLE},
                                },
                            }
                        },
                    },
                    "200": {
                        "description": "Repetição com a mesma chave e o mesmo corpo",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Payment"},
                                "example": PAYMENT_EXAMPLE,
                            }
                        },
                    },
                    "400": _error("Dados inválidos", "method deve ser pix, debit ou credit"),
                    "402": _error("Recusa da operadora", "Pagamento recusado pela operadora"),
                    "404": _error("Lojista inexistente", "Lojista 9 não encontrado"),
                    "409": _error(
                        "Requisição com a mesma chave em andamento",
                        "Requisição com essa Idempotency-Key ainda em andamento",
                    ),
                    "422": _error(
                        "Mesma chave com corpo diferente",
                        "Idempotency-Key já usada com outro corpo",
                    ),
                    "429": _error("Cartão bloqueado pelo antifraude", "Cartão bloqueado"),
                },
            }
        },
        "/payments/{payment_id}": {
            "get": {
                "tags": ["Pagamentos"],
                "summary": "Detalhe do pagamento",
                "parameters": [{"$ref": "#/components/parameters/PaymentId"}],
                "responses": {
                    "200": {
                        "description": "Pagamento encontrado",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Payment"}
                            }
                        },
                    },
                    "404": _error("Pagamento inexistente", "Pagamento 99 não encontrado"),
                },
            }
        },
        "/payments/{payment_id}/capture": {
            "post": {
                "tags": ["Pagamentos"],
                "summary": "Captura total ou parcial",
                "description": (
                    "Sem corpo captura o valor todo; com `amount` captura parte dele (no máximo o "
                    "valor autorizado). O que não for capturado é liberado no cartão do cliente. "
                    "Só um pagamento `AUTHORIZED` pode ser capturado."
                ),
                "parameters": [{"$ref": "#/components/parameters/PaymentId"}],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/AmountBody"},
                            "examples": {
                                "parcial": {
                                    "summary": "Captura parcial",
                                    "value": {"amount": "180.00"},
                                },
                                "total": {"summary": "Captura total (sem corpo)", "value": {}},
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Pagamento capturado",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Payment"}
                            }
                        },
                    },
                    "400": _error(
                        "Valor inválido ou acima do autorizado",
                        "Valor de captura acima do autorizado",
                    ),
                    "404": _error("Pagamento inexistente", "Pagamento 99 não encontrado"),
                    "409": _error(
                        "Pagamento não está AUTHORIZED",
                        "Pagamento 1 não está autorizado (status CAPTURED)",
                    ),
                },
            }
        },
        "/payments/{payment_id}/void": {
            "post": {
                "tags": ["Pagamentos"],
                "summary": "Cancela a pré-autorização",
                "parameters": [{"$ref": "#/components/parameters/PaymentId"}],
                "responses": {
                    "200": {
                        "description": "Pagamento cancelado (status VOIDED)",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Payment"},
                                "example": {**AUTHORIZED_EXAMPLE, "status": "VOIDED"},
                            }
                        },
                    },
                    "404": _error("Pagamento inexistente", "Pagamento 99 não encontrado"),
                    "409": _error(
                        "Pagamento não está AUTHORIZED",
                        "Pagamento 1 não está autorizado (status CAPTURED)",
                    ),
                },
            }
        },
        "/payments/{payment_id}/refund": {
            "post": {
                "tags": ["Pagamentos"],
                "summary": "Estorno total ou parcial",
                "description": (
                    "Sem corpo estorna o saldo restante. Só para pagamentos capturados. Pode haver "
                    "vários estornos parciais, mas a soma não pode passar do valor capturado. "
                    "O valor é debitado da agenda no mesmo dia e a taxa não é devolvida."
                ),
                "parameters": [{"$ref": "#/components/parameters/PaymentId"}],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/AmountBody"},
                            "examples": {
                                "parcial": {
                                    "summary": "Estorno parcial",
                                    "value": {"amount": "25.00"},
                                },
                                "total": {"summary": "Estorno total (sem corpo)", "value": {}},
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Estorno aplicado",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RefundResponse"},
                                "example": {
                                    "refunded": "25.00",
                                    "payment": {
                                        **PAYMENT_EXAMPLE,
                                        "status": "PARTIALLY_REFUNDED",
                                        "refunded_amount": "25.00",
                                    },
                                },
                            }
                        },
                    },
                    "400": _error("Valor inválido", "Valor monetário inválido: '-1'"),
                    "404": _error("Pagamento inexistente", "Pagamento 99 não encontrado"),
                    "409": _error(
                        "Pagamento não capturado ou soma acima do capturado",
                        "Estorno não permitido para o pagamento 2",
                    ),
                },
            }
        },
        "/jobs/expire-authorizations": {
            "post": {
                "tags": ["Rotinas"],
                "summary": "Rotina diária de expiração",
                "description": (
                    "Marca como `EXPIRED` as autorizações pendentes com 7 dias ou mais e devolve "
                    "os ids expirados. O agendador chama uma vez por dia."
                ),
                "responses": {
                    "200": {
                        "description": "Ids expirados",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ExpireResponse"},
                                "example": {"expired": [3, 5]},
                            }
                        },
                    }
                },
            }
        },
    },
}

SWAGGER_UI_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PayFlow API</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.17.14/swagger-ui.min.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.17.14/swagger-ui-bundle.min.js"></script>
  <script>
    window.ui = SwaggerUIBundle({
      url: "/openapi.json",
      dom_id: "#swagger-ui",
      deepLinking: true,
      tryItOutEnabled: true,
      displayRequestDuration: true,
      defaultModelsExpandDepth: 1,
    });
  </script>
</body>
</html>
"""


@docs.get("/openapi.json")
def openapi_spec():
    return jsonify(SPEC)


@docs.get("/docs")
def swagger_ui():
    return SWAGGER_UI_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}
