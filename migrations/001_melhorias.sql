-- Migration conceitual PostgreSQL; revisar dados legados antes de aplicar.
-- A restrição de evento_id só é apropriada se o tribunal garantir unicidade global.

ALTER TABLE precatorio
    ALTER COLUMN numero_processo TYPE VARCHAR(25);

CREATE TABLE importacao_arquivo (
    id BIGSERIAL PRIMARY KEY,
    sha256 CHAR(64) NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    leiaute TEXT NOT NULL,
    recebido_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL CHECK (status IN ('recebido', 'validado', 'importado', 'rejeitado')),
    relatorio JSONB
);

ALTER TABLE pagamento
    ADD COLUMN atualizado_em TIMESTAMPTZ,
    ADD COLUMN arquivo_id BIGINT REFERENCES importacao_arquivo(id);

-- Não aplicar UNIQUE global antes de confirmar o escopo de evento_id.
-- Se o tribunal confirmar unicidade global e as colisões legadas forem tratadas,
-- a equipe poderá habilitar o índice abaixo e usar ON CONFLICT na ingestão:
-- CREATE UNIQUE INDEX pagamento_evento_id_uk ON pagamento (evento_id);

CREATE TABLE pagamento_versao (
    id BIGSERIAL PRIMARY KEY,
    pagamento_id BIGINT NOT NULL REFERENCES pagamento(id),
    evento_id TEXT NOT NULL,
    registro JSONB NOT NULL,
    atualizado_em TIMESTAMPTZ NOT NULL,
    importacao_id BIGINT NOT NULL REFERENCES importacao_arquivo(id),
    registrado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pagamento_rejeitado (
    id BIGSERIAL PRIMARY KEY,
    importacao_id BIGINT NOT NULL REFERENCES importacao_arquivo(id),
    registro JSONB NOT NULL,
    motivo TEXT NOT NULL,
    registrado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A ingestão deve inserir importacao_arquivo, versões, eventos e atualização
-- de status em uma única transação. NUMERIC(15,2) existente continua adequado.
-- apresentado_em não é adicionado até que a fonte/tipo/fuso legal sejam acordados.
-- sha256 UNIQUE em importacao_arquivo evita reprocessar o mesmo arquivo byte a byte.
-- Idempotência entre arquivos sobrepostos requer uma chave de evento confirmada.
