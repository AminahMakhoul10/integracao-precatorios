# Diagnóstico, prevenção e dúvidas

## Diagnóstico (gravidade decrescente)

1. **Reexecução pode duplicar pagamentos e versões atualizadas.** Em pagamentos.json, ev-002 aparece duas vezes (registros 2 e 4); ev-001 reaparece no registro 9 com valor 15.500 e atualizado_em posterior ao registro 1 (15.000). O enunciado diz que após falha o arquivo é reexecutado e os valores são somados. Efeito: total pago inflado ou versão substituída somada. Causa direta da divergência.
2. **Contrato não representa os dados reais e falhas são silenciosas.** A documentação descreve valor numérico, datas ISO e tipo sempre pagamento; amostra tem ev-002 como "2.500,50", data 10/04/2025, estorno ev-007 e atualizado_em. O enunciado diz que erros são ignorados sem aviso. Eventos podem sumir ou ser interpretados errado. A falha silenciosa e leiaute desatualizado são causas-raiz.
3. **Semântica e integridade de pagamentos inconsistentes.** schema.sql não torna evento_id único apesar da documentação. tipo aceita estorno mas valor > 0 exige convenção de sinal não documentada. ev-007 é estorno de 5.000; ev-009 é pagamento de -200 e viola o esquema. O total depende de regra não acordada. Causa estrutural: contrato, lógica e banco discordam.
4. **Chaves e CSV diferem da documentação.** hub.csv linha 3 traz CNJ sem pontuação; tribunal.csv linha 3 tem a versão pontuada. Comparação literal não associa. O tribunal usa ponto e vírgula e decimal brasileiro (linha 2: 45.000,00), embora a documentação diga vírgula e ponto decimal. Causa: leiaute real não documentado; consequência: falso desencontro ou parsing incorreto.
5. **Cadastros conflitantes e ausentes.** Processo 0023456: hub R$31.000 versus tribunal R$30.000 (linha 3 de ambos). Processo 0045678: hub diz Município de Santos, tribunal diz União. 0067890 aparece apenas no tribunal; 0056789 apenas no hub. Como não sabemos se lista semanal é completa, ausência não prova exclusão. Processo manual em Excel e falta de fonte prevalente são causas operacionais.
6. **Prazos e fusos ambíguos/incorretos.** hub.csv linha 2 dá 2027 para apresentação em 2025-04-02; pela regra do enunciado deveria ser 2026-12-31. Linha 3, apresentação 2025-04-03/prazo 2027, é coerente. Para 0045678, 2025-04-02T23:30-03 é 3 de abril em UTC mas dia 2 local; para 0056789, 2025-04-03T01:00Z é dia 2 em UTC-03. Não há fuso definido para o corte legal. 0034567, apresentado em 2024-02-29, teria prazo 2025-12-31. Não recalcular prazos ambíguos sem confirmação.
7. **Registros inválidos.** ev-004 (registro 5) tem valor nulo; ev-005 (registro 6) tem processo sem máscara; ev-010 (registro 12) processo vazio; ev-009 valor negativo. Precisam ser rejeitados/quarentenados e reportados, nunca ignorados.
8. **Encoding/nome divergentes.** hub.csv mostra texto mojibake "MunicÃ­pio..." e caixa/acentuação diferente do tribunal. Comparação textual exata falha. Corrigir exportação UTF-8; normalização ajuda a comparar, mas não deve alterar nome oficial sem autoridade.

## Saída da limpeza

limpar_case.py associa processos pelos 20 dígitos, lê o CSV conforme o delimitador/decimal observado e usa Decimal. Em evento repetido escolhe a versão com atualizado_em maior; contabiliza estorno como redução líquida. Eventos inválidos são reportados. Conflitos cadastrais ficam no relatório; campos de cadastro do tribunal são provisórios e itens só de uma fonte permanecem com origem registrada. Datas apresentadas/prazos do hub são preservados para revisão. Timestamps são convertidos para data UTC como regra técnica provisória, não como decisão legal.

## Prevenção

- Arquivos imutáveis em staging, hash, nome, horário e versão do leiaute; validar por inteiro antes de transacionar; rejeitar/quarentenar com relatório por registro.
- Conciliação automatizada por CNJ normalizado, valor, ente e presença; divergências exigem revisão, sem edição no Excel.
- Versionar contrato: encoding, delimitador, decimal, datas, fuso, unicidade, atualizações e estornos.
- Importação idempotente: evento_id único; versão atualizada substitui com auditoria, nunca soma novamente. Transação por arquivo. Total derivado de eventos validados.
- NUMERIC/Decimal, validações e alertas para rejeições, divergências e atraso.
- Guardar timestamp original e data legal local acordada; função única e testada para prazo.

SQL conceitual (deduplicar registros antigos antes da restrição):

    ALTER TABLE precatorio
      ALTER COLUMN numero_processo TYPE VARCHAR(25),
      ADD COLUMN apresentado_em TIMESTAMPTZ,
      ADD COLUMN prazo_pagamento DATE,
      ADD COLUMN origem_atualizacao TIMESTAMPTZ;

    ALTER TABLE pagamento
      ADD CONSTRAINT pagamento_evento_id_uk UNIQUE (evento_id),
      ADD COLUMN atualizado_em TIMESTAMPTZ,
      ADD COLUMN arquivo_id BIGINT;

    CREATE TABLE importacao_arquivo (
      id BIGSERIAL PRIMARY KEY,
      sha256 CHAR(64) NOT NULL UNIQUE,
      nome TEXT NOT NULL,
      leiaute TEXT NOT NULL,
      recebido_em TIMESTAMPTZ NOT NULL DEFAULT now(),
      status TEXT NOT NULL CHECK (status IN ('recebido','validado','importado','rejeitado')),
      relatorio JSONB
    );

    CREATE TABLE pagamento_rejeitado (
      id BIGSERIAL PRIMARY KEY,
      arquivo_id BIGINT REFERENCES importacao_arquivo(id),
      registro JSONB NOT NULL,
      motivo TEXT NOT NULL,
      criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
    );

Restrição única não define a política de atualização: comparar atualizado_em e auditar versões anteriores (idealmente eventos imutáveis).

## Perguntas antes de produção

1. Evento repetido com atualizado_em maior substitui? Pode mudar processo, data, tipo ou valor? Há cancelamentos?
2. Estorno referencia evento original? Vem positivo? Como representar parcial e múltiplos estornos?
3. Qual leiaute oficial (separador, encoding, decimal, datas, fuso, obrigatoriedade)? Amostra reflete casos válidos?
4. Apresentação é data civil local ou instante? Qual fuso define o corte de 2 de abril?
5. Regra do prazo é literalmente a do enunciado? Prazo 2027 do primeiro registro é exceção ou erro? Há feriados/prorrogações?
6. Lista semanal é fotografia completa ou delta? O que significa ausência?
7. Qual fonte prevalece em valor/ente e quem aprova divergência?
8. CNJ sem máscara é permitido após validação do dígito? Qual referência de validação?
