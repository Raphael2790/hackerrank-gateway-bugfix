# PayFlow: desafio de correção de bugs (gateway de pagamentos)

Você entrou no time de um gateway de pagamentos. A API (Flask + Python) já está em produção recebendo pagamentos
de lojistas, mas o suporte abriu alguns chamados. Sua tarefa é **encontrar e corrigir os bugs** sem quebrar o que
já funciona.

Há **3 bugs** no código de `app/`: um fácil, um médio e um difícil (os chamados não estão em ordem de dificuldade).
Não altere os testes e não renomeie arquivos, funções ou rotas existentes.

## Chamados do suporte

1. **#2207**: "A bandeira recusou a liquidação de várias capturas feitas **mais de 7 dias depois da autorização**.
   Pelo nosso sistema essas autorizações já deveriam ter expirado, mas algumas continuaram `AUTHORIZED` mesmo
   depois da rotina diária, e o lojista conseguiu capturar. Não aconteceu com todas as autorizações antigas
   desse lojista."
2. **#2214**: "Lojistas reclamam que vendas **no débito feitas na sexta-feira** aparecem como saldo disponível no
   **sábado**, mas o banco só repassa na segunda. As vendas de sábado aparecem certinho para segunda."
3. **#2229**: "Depois de um erro no pagamento, alguns clientes não conseguem mais finalizar a compra: o app recebe
   `409` (requisição em andamento) ou `422` (chave usada com outro corpo) para sempre. O app sempre repete a
   tentativa com a **mesma `Idempotency-Key`**, como manda a nossa documentação. Curiosamente, quando o cartão é
   recusado pela operadora (402), a nova tentativa funciona."

## Regras de negócio

### Valores, datas e lojistas
- Valores monetários usam `Decimal` e saem no JSON como string com 2 casas (`"59.90"`). Na entrada podem vir como
  string (`"59.90"`) ou número (`59.9`), sempre positivos e com no máximo 2 casas decimais (senão, 400).
- Datas e horas usam o horário local, sem fuso: `"2026-03-02T10:00:00"` e `"2026-03-02"`.
- Há 2 lojistas cadastrados: `1` (Loja Aurora) e `2` (Café Central). Lojista inexistente: 404.

### Criação do pagamento
`POST /payments` com `{"merchant_id": 1, "amount": "150.00", "method": "credit", "installments": 3, "card_number": "4111111111111111", "capture": true}`

- `method`: `pix`, `debit` ou `credit`.
- `installments`: no crédito, de 1 a 12 (padrão 1). PIX e débito não parcelam: só aceitam 1.
- `card_number`: obrigatório no débito e no crédito, com 16 dígitos. É ignorado no PIX.
- `capture` (padrão `true`): no crédito, `false` faz só a **pré-autorização** (status `AUTHORIZED`), para capturar
  depois. PIX e débito são sempre capturados na hora (status `CAPTURED`).
- Resposta: **201** com o pagamento. Erros: dados inválidos **400**, recusa da operadora **402**, cartão bloqueado
  pelo antifraude **429**.

### Operadora (simulada)
- Cartões terminados em `0002` são sempre recusados (402).
- Autorizações acima de **R$ 5.000,00** são recusadas por limite (402).
- Cartões de teste: `4111111111111111` e `5555444433331111` são aprovados; `4000000000000002` é recusado.

### Antifraude (só para cartão; o PIX não passa por ele)
- **3 recusas** da operadora com o mesmo cartão em **até 10 minutos** bloqueiam o cartão por **1 hora**, contada a
  partir da 3ª recusa.
- Durante o bloqueio, qualquer tentativa com esse cartão recebe **429**, não vai para a operadora e não conta como
  recusa.

### Idempotência
- `POST /payments` aceita o header `Idempotency-Key`. A chave vale **por lojista**: lojistas diferentes podem usar
  a mesma chave.
- Mesma chave e **mesmo corpo**: a API não cobra de novo e devolve o pagamento original, com **200**.
- Mesma chave e **corpo diferente**: **422**.
- Enquanto a primeira requisição com a chave ainda está sendo processada, uma repetição recebe **409**.
- **Uma tentativa que falhou (400, 402 ou 429) não gasta a chave**: o cliente pode repetir a requisição com a
  mesma chave, com o mesmo corpo ou com o corpo corrigido (por exemplo, com outro cartão).

### Captura, cancelamento e expiração
- `POST /payments/<id>/capture` captura uma pré-autorização: o valor todo (sem corpo) ou parte dele
  (`{"amount": "80.00"}`, no máximo o valor autorizado; acima disso, 400). O que não for capturado é liberado no
  cartão do cliente.
- `POST /payments/<id>/void` cancela uma pré-autorização (status `VOIDED`).
- Autorizações **expiram 7 dias depois de criadas**. A rotina `POST /jobs/expire-authorizations` (o agendador a
  chama uma vez por dia) marca como `EXPIRED` **todas** as autorizações pendentes com 7 dias ou mais e devolve os
  ids expirados: `{"expired": [3, 5]}`.
- Só um pagamento `AUTHORIZED` pode ser capturado ou cancelado. Em qualquer outro status: **409**.

### Taxas (MDR)
Cobradas do lojista sobre o valor capturado e arredondadas para o centavo (meio centavo arredonda para cima):

| Meio                        | Taxa  |
|-----------------------------|-------|
| PIX                         | 0,99% |
| Débito                      | 1,99% |
| Crédito à vista (1x)        | 2,99% |
| Crédito parcelado (2 a 12x) | 3,99% |

`net_amount` (valor líquido) = valor capturado − taxa.

### Agenda de recebíveis e saldo
- Na captura, o valor líquido entra na agenda do lojista:
  - **PIX**: no mesmo dia da captura, inclusive sábado e domingo.
  - **Débito**: no dia seguinte à captura (D+1).
  - **Crédito**: uma parcela por mês, a parcela *i* em D+30×*i* (i = 1..N). O valor líquido é dividido igualmente,
    arredondando para baixo no centavo; os centavos que sobram vão para a primeira parcela.
- No débito e no crédito, se a data cair em **sábado ou domingo**, o repasse vai para a **segunda-feira seguinte**.
  Não há feriados.
- `GET /merchants/<id>/balance?date=AAAA-MM-DD` (sem `date`, usa hoje): `available` é a soma do que vence até a
  data, inclusive; `pending` é o que vence depois.

### Estorno
- `POST /payments/<id>/refund` com `{"amount": "25.00"}`; sem corpo, estorna o saldo restante. Só para pagamentos
  capturados (senão, 409). Pode haver vários estornos parciais, mas a soma não pode passar do valor capturado (409).
- Status: `PARTIALLY_REFUNDED` ou, quando a soma chega ao valor capturado, `REFUNDED`.
- O valor estornado é **debitado da agenda do lojista no mesmo dia** (lançamento negativo com `"kind": "REFUND"`).
  A taxa não é devolvida.

## Endpoints

| Método | Rota                                       | Descrição                                                   |
|--------|--------------------------------------------|-------------------------------------------------------------|
| GET    | `/merchants/<id>`                          | dados do lojista                                            |
| GET    | `/merchants/<id>/receivables`              | agenda de recebíveis, por data                              |
| GET    | `/merchants/<id>/balance?date=AAAA-MM-DD`  | saldo disponível e a receber                                |
| POST   | `/payments`                                | cria o pagamento (header opcional `Idempotency-Key`): 201, ou 200 numa repetição |
| GET    | `/payments/<id>`                           | detalhe do pagamento                                        |
| POST   | `/payments/<id>/capture`                   | captura total ou parcial                                    |
| POST   | `/payments/<id>/void`                      | cancela a pré-autorização                                   |
| POST   | `/payments/<id>/refund`                    | estorno total ou parcial                                    |
| POST   | `/jobs/expire-authorizations`              | rotina diária de expiração                                  |

## Como executar o projeto

### 1. Preparar o ambiente (uma vez só)

Pré-requisito: Python 3.11 ou mais novo.

```powershell
cd C:\Users\rsssh\repos\hackerrank-gateway-bugfix
python -m venv .venv                  # (já criado; só precisa se apagar a pasta .venv)
.venv\Scripts\Activate.ps1            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

> Se o PowerShell bloquear o `Activate.ps1`, rode antes
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, ou use `.venv\Scripts\python -m pytest`
> sem ativar o ambiente.

### 2. Rodar os testes

```powershell
pytest                                            # todos os testes visíveis (pasta tests/)
pytest -v                                         # mostra o nome de cada teste
pytest tests/test_capture.py                      # só um arquivo
pytest tests/test_capture.py::test_partial_capture   # só um teste
pytest -k refund                                  # testes cujo nome contém "refund"
pytest -x                                         # para no primeiro teste que falhar
pytest --tb=short                                 # traceback mais curto
```

Na versão com bugs, **2 testes visíveis falham**. Isso é esperado.

### 3. Controlar o tempo e criar pagamentos nos testes

Nos testes, a API usa um relógio parado em **segunda-feira, 02/03/2026, 10:00**. A fixture `clock` (do
`conftest.py`) faz o tempo andar:

```python
from datetime import datetime


def test_exemplo(client, pay, clock):
    pay(capture=False)                      # pré-autorização às 10:00 de segunda
    clock.advance(days=7, hours=2)          # anda 7 dias e 2 horas
    clock.set(datetime(2026, 3, 6, 15, 0))  # ou pula direto para sexta, 15:00
```

A fixture `pay(...)` cria um pagamento pela API e devolve a resposta. O padrão é lojista 1, R$ 100,00 no crédito
à vista, cartão aprovado e captura imediata; troque o que quiser: `pay(method="debit")`,
`pay(amount="250.00", installments=3)`, `pay(capture=False)`, `pay(key="pedido-1")` (envia a `Idempotency-Key`).

### 4. Subir a API e testar na mão

```powershell
flask --app app run --debug           # http://127.0.0.1:5000 (recarrega quando você salva um arquivo)
```

Fora dos testes, a API usa o relógio real do computador. Em outro terminal (os dados ficam em memória e voltam ao
estado inicial quando a API reinicia):

```powershell
curl.exe http://127.0.0.1:5000/merchants/1
curl.exe -X POST http://127.0.0.1:5000/payments -H "Content-Type: application/json" -H "Idempotency-Key: pedido-1" -d '{\"merchant_id\": 1, \"amount\": \"250.00\", \"method\": \"credit\", \"installments\": 3, \"card_number\": \"4111111111111111\"}'
curl.exe -X POST http://127.0.0.1:5000/payments -H "Content-Type: application/json" -d '{\"merchant_id\": 1, \"amount\": \"300.00\", \"method\": \"credit\", \"card_number\": \"4111111111111111\", \"capture\": false}'
curl.exe -X POST http://127.0.0.1:5000/payments/2/capture -H "Content-Type: application/json" -d '{\"amount\": \"180.00\"}'
curl.exe http://127.0.0.1:5000/merchants/1/receivables
curl.exe "http://127.0.0.1:5000/merchants/1/balance?date=2026-12-31"
curl.exe -X POST http://127.0.0.1:5000/jobs/expire-authorizations
```

Ou, no PowerShell puro:

```powershell
$base = "http://127.0.0.1:5000"
$body = '{"merchant_id": 1, "amount": "250.00", "method": "credit", "installments": 3, "card_number": "4111111111111111"}'
$payment = Invoke-RestMethod -Method Post "$base/payments" -ContentType "application/json" -Headers @{ "Idempotency-Key" = "pedido-1" } -Body $body
$payment
Invoke-RestMethod "$base/merchants/1/receivables"
```

## Como validar se as correções estão OK

Assim como na plataforma, a solução é avaliada por **testes automatizados**, e a nota é o percentual de testes que
passam.

- `tests/`: testes **visíveis**. É o que você recebe junto com o desafio.
- `hidden_tests/`: testes **ocultos**, que cobrem casos de borda e regras que os testes visíveis não pegam.
  **Não abra essa pasta** (nem deixe sua IA abrir) até achar que terminou.

Siga esta ordem:

```powershell
# 1) Os testes visíveis passam?
pytest

# 2) Os testes "da plataforma" (visíveis + ocultos) passam?
pytest tests hidden_tests

# 3) Você mexeu só no código, e não nos testes? (as duas saídas têm que vir vazias)
git status --short tests hidden_tests conftest.py pytest.ini
git diff --stat -- tests hidden_tests conftest.py pytest.ini

# 4) Revise o que mudou: cada correção deve ser pequena e no lugar certo
git diff
```

O treino está concluído quando **`pytest tests hidden_tests` termina com tudo passando** e o passo 3 não mostra
nada.

Dicas:
- Passar só nos testes visíveis normalmente **não** basta. Corrija a **regra de negócio** descrita acima, não o
  caso específico de um teste.
- Para cada chamado, escreva primeiro um teste que reproduz o problema, numa pasta sua (ex.:
  `meus_testes/test_chamados.py`, rodando com `pytest meus_testes`). Veja o teste falhar, corrija o código e veja o
  teste passar. As fixtures `client`, `pay` e `clock` do `conftest.py` também funcionam ali.
- `pytest` sozinho (ou `pytest .`) nunca roda os testes ocultos; eles só rodam quando você pede
  `pytest tests hidden_tests`.
- Para recomeçar do zero: `git stash` (guarda suas mudanças) ou `git checkout -- app` (descarta as mudanças).

## Usando a IA (Claude Code) neste treino

- Abra **esta pasta** como raiz no VS Code (Arquivo > Abrir Pasta... > `hackerrank-gateway-bugfix`) ou rode
  `claude` de dentro dela. As travas abaixo só valem para sessões iniciadas aqui.
- O `CLAUDE.md` faz do Claude Code um par de programação que **escreve código para você** (testes de reprodução,
  prints de investigação e as correções que você decidir) e **dá dicas**, mas **não entrega as respostas** (qual é
  o bug, onde está, qual é a correção) e **não lê** os testes ocultos, o gabarito nem os rastros da criação do
  desafio. Dicas são por nível e por chamado: peça `dica 1 #2214`, depois `dica 2 #2214`, e assim por diante (vão
  até o nível 4; a correção é sempre decisão sua).
- Travas técnicas, além das instruções: `.claude/settings.json` bloqueia a leitura de `hidden_tests/`,
  `.gabarito/` e dos rastros da criação do desafio, e bloqueia a edição dos testes, do `conftest.py`, do
  `pytest.ini` e das próprias travas; o hook `.claude/hooks/trava_treino.py` barra comandos e arquivos que citem
  essas pastas ou façam buscas recursivas pelo terminal; o `.ignore` tira essas pastas das buscas (inclusive do
  Ctrl+Shift+F do VS Code).
- Para conferir se está tudo ativo: no Claude Code, rode `/permissions` (devem aparecer as regras de "deny") e
  `/hooks` (deve aparecer o `PreToolUse`). Depois peça "leia hidden_tests/test_hidden.py": ele deve recusar ou ser
  bloqueado.
- Não edite nem apague `CLAUDE.md` e `.claude/` durante o treino. Quando terminar, se quiser discutir tudo
  livremente com a IA (inclusive os testes ocultos), apague ou renomeie esses dois.
- Limite: as travas não são um sandbox do sistema operacional. Um script que abra arquivos sem citar o caminho
  passaria; por isso o `CLAUDE.md` também proíbe isso.

## Gabarito

Só leia depois de terminar:

```bash
python -c "import base64;print(base64.b64decode(open('.gabarito/GABARITO.b64').read()).decode())"
```
