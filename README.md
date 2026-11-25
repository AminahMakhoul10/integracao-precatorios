# Integração de precatórios

Ferramenta de linha de comando para normalizar e conciliar os arquivos do case. Os dados recebidos são preservados; resultados e ocorrências são gravados separadamente.

## Requisitos e instalação

- Python 3.10 ou superior.
- Apenas biblioteca padrão; não é necessário instalar dependências. requirements.txt documenta isso.

## Estrutura

- dados/: arquivos originais do case.
- src/: leitura, parsing, conciliação, pagamentos e geração de saída.
- tests/: testes unitários e de integração.
- migrations/001_melhorias.sql: proposta PostgreSQL; não aplicada.
- ANALISE.md: diagnóstico, prevenção e dúvidas de negócio.
- schema.sql: esquema original, mantido sem alterações.

## Como executar

Na pasta case-candidato:

    python -m src.main --input dados --output saida
    python -m unittest discover -s tests -v

O programa também pode ser chamado com python -m src. A pasta saida é criada automaticamente e está no .gitignore.

## Saídas

- precatorios.json: registros conciliados com valores e nomes originais por fonte, resultado da comparação normalizada, apresentação original/local, prazo e estado de pendências.
- pagamentos.json: eventos efetivos; versões empatadas em conflito ou bloqueadas por atualização inválida não são selecionadas.
- historico_pagamentos.json: versões válidas de eventos, inclusive duplicatas exatas.
- relatorio.json: correções de formato, rejeições, duplicidades e pendências com referência ao registro de origem.

total_pagamentos_validos soma eventos tipo pagamento aceitos. total_pago_liquido fica nulo quando há estorno, versão conflitante ou registro inválido que possa alterar o total; não foi assumida regra de compensação para estorno.

## Funcionamento e decisões provisórias

O leitor reconhece separador CSV por cabeçalho, tenta UTF-8 e usa Windows-1252 somente se UTF-8 falhar. Valores usam Decimal. Processos são associados pelos 20 dígitos, sem validação do dígito verificador CNJ. A versão válida mais recente de evento_id é usada quando não há empate conflitante nem atualização inválida mais nova. Timestamps de apresentação preservam texto, offset e data civil local; não são convertidos a UTC para decidir prazo. Prazos são calculados apenas quando a entrada é uma data civil sem ambiguidade.

Estornos são mantidos no histórico e nas ocorrências, mas não alteram totais enquanto tribunal/operação não esclarecerem a referência e a compensação. Para comparar entes, caixa, acentos e espaços repetidos nas extremidades ou entre palavras são normalizados; isso afeta somente a comparação. Os nomes originais continuam lado a lado na saída. Diferenças como Município de Santos e União continuam como divergência pendente.

## IA e conferência

Usei IA como apoio à análise, estruturação e revisão do código. Conferi o diagnóstico nos arquivos originais, validei as regras do enunciado com testes de resultados esperados, executei a integração e conferi que entradas continuam byte a byte iguais após rodar.

## Limitações

- Não valida o dígito verificador CNJ.
- Unicidade global de evento_id, semântica de estorno, completude da lista semanal, prevalência das fontes e fuso legal ainda precisam de confirmação.
- A migration é conceitual e não foi executada em banco real.
