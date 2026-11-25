# Diagnóstico, prevenção e dúvidas

## Diagnóstico por gravidade

As gravidades abaixo são uma avaliação técnica do impacto potencial neste case; não são classificações oficiais do Tribunal.

### 1. Reexecução de pagamentos pode duplicar valores — gravidade crítica

- **Evidência:** ENUNCIADO.md, fluxo operacional itens 1-2; dados/pagamentos.json, ev-002 nos registros 2 e 4 e ev-001 nos registros 1 e 9. ev-001 reaparece com valor 15.500 e atualizado_em posterior ao primeiro valor de 15.000.
- **Técnica e impacto:** o mesmo arquivo cobre sete dias e pode ser reexecutado após falha. Somar toda linha em cada execução duplica eventos; somar a nova versão de ev-001 acumula um valor atualizado como se fosse novo pagamento. O saldo pago pode ficar incorreto.
- **Causa/relação:** causa direta; o esquema não tem unicidade de evento_id e o fluxo soma sem controle de idempotência.
- **Solução:** registrar importações e versões; aplicar atualização do evento de modo idempotente, em transação, após confirmar com o tribunal o escopo de evento_id.

### 2. Eventos inválidos são descartados sem aviso — gravidade crítica

- **Evidência:** ENUNCIADO.md, fluxo item 5; pagamentos.json registro 5 ev-004 tem valor null, registro 11 ev-009 tem valor -200 com tipo pagamento e registro 12 ev-010 não tem processo.
- **Técnica e impacto:** ev-004 e ev-009 têm processo associado, mas não são importáveis por causa do valor inválido; ev-010 não tem processo para associação. Sem aviso e trilha, o operador não consegue explicar a diferença no total.
- **Causa/relação:** o descarte silencioso é causa operacional da divergência; os valores/campos inválidos são erros de origem ou de contrato ainda não esclarecidos.
- **Solução:** validar antes de gravar e mandar cada inválido para relatório/quarentena com arquivo, registro, conteúdo original e motivo; alertar a operação.

### 3. Semântica de estorno e valor negativo não está definida — gravidade alta

- **Evidência:** pagamentos.json, ev-007 é estorno de 5.000 para o processo de ev-006; ev-009 tem valor negativo mas tipo pagamento. DOCUMENTACAO_TRIBUNAL.md diz tipo sempre pagamento, enquanto schema.sql aceita pagamento/estorno e exige valor positivo.
- **Técnica e impacto:** não se sabe se estorno aponta para outro evento, se deve reduzir saldo, nem como tratar estorno parcial. Somar ou subtrair por suposição altera o valor pago.
- **Causa/relação:** causa estrutural: contrato, código operacional e schema descrevem regras diferentes.
- **Solução:** manter o evento e sua evidência, deixar total líquido pendente para o processo e confirmar tipo, referência, sinal e forma de compensação antes de contabilizar.

### 4. Leiaute e encoding recebidos não seguem a documentação — gravidade alta

- **Evidência:** DOCUMENTACAO_TRIBUNAL.md afirma UTF-8, CSV com vírgula e valor decimal com ponto. dados/tribunal.csv usa ponto e vírgula e valor 45.000,00 na linha 2; o nome Município contém byte ED (Windows-1252). hub.csv é UTF-8, mas contém texto mojibake “MunicÃ­pio”.
- **Técnica e impacto:** leitor estrito pode falhar, separar campos incorretamente ou comparar nomes sem correspondência.
- **Causa/relação:** causa-raiz provável: contrato de integração não foi atualizado; o Excel e a comparação literal agravam o problema.
- **Solução:** acordar e versionar encoding, separador e convenção monetária; conservar original, detectar formato explicitamente e reportar fallback.

### 5. HUB e tribunal apresentam divergências de cadastro — gravidade alta

- **Evidência:** hub.csv linha 3 traz valor 31.000 para processo 0023456; tribunal.csv linha 3 traz 30.000. Para 0045678, hub diz Município de Santos e tribunal diz União. Processo 0056789 só aparece no hub; 0067890 só no tribunal.
- **Técnica e impacto:** a comparação atual por texto exato perde correspondência de processo sem máscara; valor ou ente incorreto afeta exposição e priorização. Ausência pode significar delta, não exclusão.
- **Causa/relação:** a diferença de máscara e grafia contribui para falsos desencontros; conflito de valor/ente e ausência podem ser dados distintos ou arquivos de escopos diferentes.
- **Solução:** normalizar a chave para comparar, manter lado a lado a origem de cada campo e encaminhar conflitos/ausências para conciliação humana. Não eleger fonte sem regra acordada.

### 6. Prazo do HUB não segue a regra literal em ao menos um caso — gravidade alta

- **Evidência:** enunciado determina apresentação até 2 de abril -> 31/12 do ano seguinte; após 2 de abril -> 31/12 do ano subsequente ao seguinte. hub.csv linha 2 dá 2027-12-31 para apresentação em 2025-04-02; pela regra literal resulta 2026-12-31. hub.csv linha 3 (2025-04-03 e prazo 2027) é coerente.
- **Técnica e impacto:** prazo incorreto pode mudar a ordem de prioridade da carteira.
- **Causa/relação:** possível erro de cálculo ou regra/exceção não documentada; falta teste e comparação automatizada.
- **Solução:** usar função isolada testada e sinalizar diferença frente ao prazo HUB. Não substituir o prazo operacional até investigar exceções.

### 7. Apresentações com timestamp têm corte legal ambíguo — gravidade alta

- **Evidência:** apresentacoes.json traz 0045678 como 2025-04-02T23:30:00-03:00 e 0056789 como 2025-04-03T01:00:00Z.
- **Técnica e impacto:** o instante pode cair em dias civis diferentes conforme o fuso escolhido; a regra de corte de 2 de abril não define o fuso aplicável. Usar UTC automaticamente pode classificar prazo errado.
- **Causa/relação:** causa-raiz: contrato não define se apresentação é data civil ou instante nem o fuso jurídico.
- **Solução:** preservar timestamp e offset, manter prazo pendente e solicitar regra/fuso oficial. Não converter a UTC para decidir o corte.

### 8. CNJ sem máscara e grafia variável dos nomes — gravidade moderada

- **Evidência:** hub.csv linha 3 e pagamentos.json ev-005 usam 00234562120208260053 sem pontuação, enquanto tribunal.csv linha 3 usa 0023456-21.2020.8.26.0053. hub.csv linha 2 usa MUNICIPIO DE SAO PAULO e tribunal.csv linha 2 usa Município de São Paulo.
- **Técnica e impacto:** comparação textual exata não associa processo. As duas grafias do Município de São Paulo diferem em caixa e acentos, mas são equivalentes após a normalização limitada da comparação. O risco de normalizar é ocultar uma divergência se nomes oficiais distintos diferirem somente por esses aspectos.
- **Causa/relação:** consequência de formatos/exportações heterogêneos; falta de chave canônica na conciliação.
- **Solução:** comparar processos pelos 20 dígitos e nomes após normalizar caixa, acentos e espaços; manter sempre os nomes originais e registrar como informativa qualquer diferença só de grafia. Nomes com conteúdo diferente, como Município de Santos e União, continuam pendentes. Confirmar cadastro oficial antes de corrigir nomes.

### 9. Integridade do banco é insuficiente para auditoria e idempotência — gravidade moderada

- **Evidência:** schema.sql usa CHAR(20), não torna pagamento.evento_id único e não armazena atualizado_em ou identificação do arquivo.
- **Técnica e impacto:** não há proteção de duplicação nem trilha para descobrir qual arquivo/versão criou um saldo. CHECK tipo aceita estorno, mas não documenta seu cálculo.
- **Causa/relação:** causa estrutural que permite repetição e limita auditoria; relaciona-se aos itens 1 e 3.
- **Solução:** proposta separada em migrations/001_melhorias.sql, condicionando unicidade ao contrato do tribunal e preservando o schema original.

## Tratamento implementado

src/ lê os quatro arquivos originais, usa Decimal, reconhece separador CSV e fallback para Windows-1252, e normaliza processos pela sequência de 20 dígitos. Não valida dígito verificador. Compara nomes de entes usando chave_nome para ignorar caixa, acentos e espaços redundantes, mas preserva grafias originais por fonte e emite ocorrência informativa se elas diferirem apenas na forma. Nomes com diferença lexical permanecem divergências pendentes; assim, Município de Santos e União não são tratados como equivalentes.

Datas civis são usadas para calcular prazo pela regra literal. Timestamps conservam o original, offset e data local; o prazo fica pendente. Prazo calculado e prazo HUB são comparados quando a apresentação é data civil inequívoca.

Histórico válido fica em historico_pagamentos.json. Uma versão de evento só é efetiva quando tem atualizado_em mais novo sem empate conflitante e sem versão inválida tão nova. Duplicatas idênticas são contadas uma vez. Eventos inválidos aparecem no relatório. Estornos são preservados e não subtraídos; o total líquido fica nulo para processos afetados por estorno, empate conflitante ou pagamento inválido. Isso evita apresentar uma hipótese como regra confirmada.

## Prevenção operacional e técnica

- Guardar arquivos recebidos imutáveis com hash, nome, versão do leiaute, horário e resultado da importação.
- Validar o arquivo inteiro antes da transação; gravar inválidos em quarentena e alertar o operador.
- Automatizar conciliação por chave CNJ normalizada, mostrando origem e diferenças sem editar arquivos no Excel.
- Tornar importação idempotente após definir o escopo de evento_id. Atualizar evento por atualizado_em e preservar versões anteriores.
- Calcular totais a partir dos eventos aceitos; marcar incompleto se um pagamento inválido ou estorno pendente puder afetá-los.
- Fazer transação por arquivo e registrar sucesso/falha para permitir reexecução segura.
- Confirmar CSV, encoding, decimal, formatos de data, fuso da apresentação e semântica de estorno com o tribunal.

## SQL preventivo

migrations/001_melhorias.sql é conceitual e não foi aplicada. Ela amplia a coluna do processo, registra arquivos importados com SHA-256, associa pagamento ao arquivo, guarda atualizado_em e propõe histórico e quarentena. NUMERIC(15,2) existente já é apropriado. O SHA-256 único evita cadastrar o mesmo arquivo byte a byte mais de uma vez. O índice global de evento_id está apenas como SQL comentado opcional e só pode ser habilitado após confirmar escopo e resolver colisões legadas. Idempotência entre arquivos sobrepostos depende de chave de evento confirmada. A aplicação deve usar transação e tratamento ON CONFLICT compatível com a política acordada; a migration não altera schema.sql.

## Dúvidas antes de produção

1. **evento_id é globalmente único entre todos os arquivos e períodos?** Necessário para definir uma chave idempotente e decidir se o índice global opcional pode ser habilitado.
2. **Uma versão com atualizado_em maior substitui a anterior?** Define se valores alterados são substituições ou eventos adicionais.
3. **Como tratar duas versões com atualizado_em empatado?** Sem ordenação adicional, não há base segura para escolher uma versão.
4. **Estorno referencia evento original? Valor é positivo? Como representar parcial/cancelamento?** Sem isso o líquido não pode ser calculado com segurança.
5. **Qual é o leiaute oficial real de cada arquivo (encoding, delimitador, decimal e data)?** A amostra contradiz a documentação e o parser de produção precisa do contrato correto.
6. **Qual fuso/data civil define o corte jurídico em 2 de abril?** Necessário para não calcular prazo incorretamente nos dois timestamps.
7. **O prazo HUB de 2025-04-02 para 2027 é erro ou há exceção à regra do enunciado?** É necessário saber se o prazo calculado pode substituir o usado na operação.
8. **tribunal.csv é fotografia completa ou delta semanal?** Define se processo ausente pode ser removido ou deve apenas gerar alerta.
9. **Qual fonte é oficial para valor e ente, e quem aprova correções?** Resolve os conflitos concretos sem escolha arbitrária.
10. **CNJ sem máscara é aceito e qual validador confirma o dígito?** Normalização por 20 dígitos associa registros, mas não garante validade do identificador.
