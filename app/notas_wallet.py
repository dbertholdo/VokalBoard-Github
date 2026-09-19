"""
Fundação antifraude do sistema de Notas — P5 Etapa 1 (18/09/2026).

Funções reaproveitáveis para QUALQUER crédito/débito de Notas daqui em
diante (loja, urgência, assinatura, recompensas automáticas), seguindo
as regras fixas já registradas no plano ("Antifraude na loja e na
assinatura", P5):

  1. Saldo nunca fica negativo por corrida (race condition):
     `debit_notas_atomic()` trava a linha do usuário (`SELECT ... FOR
     UPDATE`) ANTES de somar o ledger e decidir — nunca lê o saldo
     numa consulta e debita numa segunda sem lock, senão duas compras
     simultâneas no mesmo saldo baixo poderiam ambas passar.
  2. Preço nunca vem do cliente: quem chama `debit_notas_atomic()`
     sempre passa um `amount` calculado no servidor (uma constante,
     uma config, uma tabela de preços) — isso é responsabilidade de
     quem chama, não deste módulo, mas o módulo nunca aceita um valor
     "total" ou "preço final" vindo direto de Form()/JS.
  3. Idempotência: `credit_notas()`/`debit_notas_atomic()` aceitam
     `idempotency_key` opcional — uma chamada repetida com a mesma
     chave (ex.: duplo clique, F5, retry de rede) nunca gera uma
     segunda linha no `credit_ledger`. Reforçado por um índice único
     parcial no banco (`idx_credit_ledger_user_idempotency`), não só
     por uma checagem em Python — evita duplicidade mesmo sob corrida
     entre duas chamadas concorrentes com a mesma chave.

Quem NÃO precisa passar por aqui: o resgate de itens do catálogo em
`app/routers/notas_routes.py` (`redeem_notas()`) já trava a linha do
usuário e faz um efeito colateral (estender `profile_highlighted_until`)
na MESMA transação do débito — deliberadamente deixado como está nesta
etapa (fora de escopo, sem teste automatizado prévio cobrindo esse
fluxo, risco desnecessário mexer agora). Fica como um bom próximo passo
reaproveitar este módulo lá também, quando o catálogo crescer.
"""
from decimal import Decimal

from sqlalchemy import text

from app.database import engine, fetch_one


def format_notas(value) -> str:
    """
    Formata um valor de Notas pra exibição: inteiro sem casas decimais
    ("3", "-3"), fracionado com vírgula e 2 casas ("0,50") — mesmo
    padrão de vírgula decimal já usado pro dinheiro em app/fees.py.
    """
    value = Decimal(value)
    if value == value.to_integral_value():
        return str(int(value))
    return f"{value:.2f}".replace(".", ",")


def get_credit_balance(user_id: int) -> Decimal:
    row = fetch_one(
        "SELECT COALESCE(SUM(delta), 0) AS balance FROM credit_ledger WHERE user_id = :id",
        {"id": user_id},
    )
    return row["balance"] if row else Decimal("0")


def count_credits_since(user_id: int, reason: str, since) -> int:
    """Quantas linhas de crédito (delta > 0) com esse `reason` esse
    usuário recebeu desde `since` — usado por regras de teto/antifraude
    de recompensas automáticas (ex.: no máx. 3 vagas recompensadas por
    semana)."""
    row = fetch_one(
        """
        SELECT COUNT(*) AS n FROM credit_ledger
        WHERE user_id = :uid AND reason = :reason AND delta > 0 AND created_at >= :since
        """,
        {"uid": user_id, "reason": reason, "since": since},
    )
    return row["n"] if row else 0


def credit_notas(
    user_id: int,
    amount: Decimal | str | int,
    reason: str,
    reference_id: int | None = None,
    idempotency_key: str | None = None,
    admin_note: str | None = None,
) -> bool:
    """
    Credita Notas (delta positivo). Retorna True se creditou, False se
    `idempotency_key` já tinha sido usado antes pra esse usuário (nesse
    caso NADA é inserido de novo — não é um erro, é o comportamento
    esperado de idempotência).

    `admin_note` (opcional): justificativa em texto livre digitada por
    um Admin — usado só pela concessão avulsa
    (/financeiro/conceder, P6, 19/09/2026); None pra qualquer outro
    crédito automático do sistema.
    """
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("credit_notas: amount precisa ser positivo")
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO credit_ledger (user_id, delta, reason, reference_id, idempotency_key, admin_note)
                VALUES (:uid, :delta, :reason, :ref_id, :key, :note)
                ON CONFLICT (user_id, idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
                RETURNING id
                """
            ),
            {
                "uid": user_id, "delta": amount, "reason": reason, "ref_id": reference_id,
                "key": idempotency_key, "note": admin_note,
            },
        )
        inserted = result.first()
    return inserted is not None


def debit_notas_atomic(
    user_id: int,
    amount: Decimal | str | int,
    reason: str,
    reference_id: int | None = None,
    idempotency_key: str | None = None,
    admin_note: str | None = None,
) -> bool:
    """
    Debita Notas (delta negativo) SÓ SE o saldo atual alcançar `amount`
    — tudo dentro da mesma transação que trava a linha do usuário.
    Retorna False sem debitar nada se o saldo for insuficiente. Se
    `idempotency_key` já tiver sido usado antes por esse usuário,
    retorna True sem debitar de novo (idempotente — já foi processado).

    `admin_note`: mesmo significado que em credit_notas() acima.
    """
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("debit_notas_atomic: amount precisa ser positivo")
    with engine.begin() as conn:
        # Trava a linha do usuário — serializa débitos concorrentes do
        # MESMO usuário, então a leitura do saldo logo abaixo (dentro
        # desta mesma transação) já reflete qualquer débito que tenha
        # acabado de ser confirmado por outra requisição concorrente.
        conn.execute(text("SELECT id FROM users WHERE id = :id FOR UPDATE"), {"id": user_id})
        if idempotency_key:
            already = conn.execute(
                text("SELECT id FROM credit_ledger WHERE user_id = :uid AND idempotency_key = :key"),
                {"uid": user_id, "key": idempotency_key},
            ).first()
            if already:
                return True
        balance = conn.execute(
            text("SELECT COALESCE(SUM(delta), 0) FROM credit_ledger WHERE user_id = :id"),
            {"id": user_id},
        ).scalar_one()
        if balance < amount:
            return False
        conn.execute(
            text(
                """
                INSERT INTO credit_ledger (user_id, delta, reason, reference_id, idempotency_key, admin_note)
                VALUES (:uid, :delta, :reason, :ref_id, :key, :note)
                """
            ),
            {
                "uid": user_id, "delta": -amount, "reason": reason, "ref_id": reference_id,
                "key": idempotency_key, "note": admin_note,
            },
        )
    return True


def refund_ledger_entry(ledger_id: int, admin_id: int | None) -> tuple[bool, int | None]:
    """Reembolsa UMA linha de débito específica do credit_ledger,
    creditando o mesmo valor de volta pro mesmo usuário. Extraído pra
    cá (18/09/2026) porque agora tem DOIS pontos de entrada — o botão
    "Reembolsar" em /admin/users/{id} (nível Admin) e a tela dedicada
    de estornos em /financeiro/estornos (nível God Mode) — e a regra
    (só débito, só idempotente, nunca um valor vindo do formulário)
    não pode viver duas vezes.

    Retorna (sucesso, user_id) — user_id é None se a linha não existir
    ou não for um débito (não reembolsável); nesse caso nada é
    creditado.
    """
    entry = fetch_one("SELECT id, user_id, delta FROM credit_ledger WHERE id = :id", {"id": ledger_id})
    if not entry or entry["delta"] >= 0:
        return False, None

    amount = -entry["delta"]
    credited = credit_notas(
        entry["user_id"], amount, reason="admin_refund", reference_id=ledger_id,
        idempotency_key=f"admin_refund_{ledger_id}",
    )
    return credited, entry["user_id"]
