# Relatorio de Ajuste de Ciclos Iniciados em Setembro

Data: 2026-04-08

## Escopo
- Validar o caso do associado `JUSTINO DA SILVA LEAL` (`CPF 45125260304`).
- Confirmar a origem do ciclo iniciado em setembro.
- Confirmar se dezembro pode permanecer em `previsao`.
- Levantar todos os contratos com `ciclo 1` iniciado em setembro para ajuste para outubro.

## Conclusao do caso Justino

### O que os artefatos mostram
- O primeiro aparecimento do Justino nos arquivos de retorno disponiveis ocorre em `10/2025`, nao em setembro.
- Evidencia:
  - [docs/Relatorio_D2102-10-2025 inicio.txt:190](/mnt/d/apps/abasev2/abasev2/docs/Relatorio_D2102-10-2025%20inicio.txt#L190)
- O legado sincronizou o pagamento inicial do contrato dele com `paid_at = 2025-09-06 15:00:00+00:00`.
- Evidencia:
  - [sync_legacy_initial_payments_20260321T150647.json:1130](/mnt/d/apps/abasev2/abasev2/backend/media/relatorios/legacy_import/sync_legacy_initial_payments_20260321T150647.json#L1130)
- A auditoria do enriquecimento legada materializou o `primeiro_ciclo_ativado_em = 2025-09-06T15:00:00+00:00` com origem `tesouraria_pagamento`.
- Evidencia:
  - [post_import_legacy_enrichment_20260321T150647.json:51717](/mnt/d/apps/abasev2/abasev2/backend/media/relatorios/legacy_import/post_import_legacy_enrichment_20260321T150647.json#L51717)
- O proprio relatorio de auditoria marca o contrato do Justino como:
  - `ciclo_com_lacuna`
  - `lacuna_regularizada_fora_do_ciclo`
  - `renovacao_com_ciclo_incompleto`
- A mesma auditoria informa:
  - `2 competencia(s) vencida(s) seguem fora da composicao dos ciclos`
  - `1 competencia(s) foram regularizadas tardiamente e permanecem fora dos ciclos`
- Evidencia:
  - [post_import_legacy_enrichment_20260321T150647.json:51744](/mnt/d/apps/abasev2/abasev2/backend/media/relatorios/legacy_import/post_import_legacy_enrichment_20260321T150647.json#L51744)
- O pedido de renovacao legado do Justino esta associado ao trio `2025-10`, `2025-11`, `2025-12`.
- Evidencia:
  - [sync_legacy_media_assets_execute.json:61407](/mnt/d/apps/abasev2/abasev2/backend/media/relatorios/legacy_import/sync_legacy_media_assets_execute.json#L61407)
- Existe comprovante mensal legado canonizado para `2025/12` do Justino.
- Evidencia:
  - [sync_legacy_media_assets_execute.json:87663](/mnt/d/apps/abasev2/abasev2/backend/media/relatorios/legacy_import/sync_legacy_media_assets_execute.json#L87663)

### Resposta objetiva
- O contrato/ciclo do Justino aparece com inicio em setembro porque a importacao legada abriu o primeiro ciclo a partir da data do `pagamento inicial` da tesouraria (`2025-09-06`), e nao a partir do primeiro mes real do retorno.
- Pelos arquivos de retorno disponiveis e pelos anexos legados de renovacao, o ciclo operacional dele deveria comecar em `10/2025`, nao em `09/2025`.
- A parcela de `12/2025` nao deveria permanecer em `previsao`.
- Ha evidencia de pagamento mensal de `12/2025` para o Justino, entao essa competencia precisa estar como `descontada`/`quitada` ou, se o desconto nao ocorreu, como `nao_descontada`.
- Regra operacional travada para correcao:
  - parcelas passadas nao podem ficar em `previsao`
  - se o associado ja renovou, o `ciclo 1` deve ficar concluido/renovado sem competencia vencida em aberto dentro ou fora do ciclo
  - todos os contratos cujo `ciclo 1` foi aberto em `09/2025` devem ser ajustados para `10/2025`

## Resumo do levantamento
- Total de contratos com `primeiro_ciclo_ativado_em` em `09/2025`: `47`
- Desses 47:
  - `13` tem `renovacao_com_ciclo_incompleto`
  - `21` tem `lacuna_regularizada_fora_do_ciclo`
  - `11` tem `ciclo_futuro_ausente`
  - `29` ja aparecem com `ciclo 1 = ciclo_renovado`, mas ainda com lacuna historica
  - `12` ainda estao com `ciclo 1 = aberto`
  - `6` ainda estao com `ciclo 1 = apto_a_renovar`

## Casos do mesmo tipo do Justino

Criterio: `ciclo 1` iniciado em setembro e presenca de `renovacao_com_ciclo_incompleto`.

| CPF | Associado | Contrato | Inicio atual | Meses fora do ciclo |
| --- | --- | --- | --- | --- |
| 85461008372 | AUREA CRISTINA SOUSA RODRIGUES | CTR-20250902124951-1XLK0 | 2025-09-06 | 2 |
| 37303988300 | EDILSON PEREIRADO NASCIMENTO | CTR-20250903142218-X82A5 | 2025-09-06 | 3 |
| 18213448391 | EDITH FERREIRA DE SOUSA | CTR-20250902112647-8OZCL | 2025-09-06 | 2 |
| 45125260304 | JUSTINO DA SILVA LEAL | CTR-20250902111725-DIMIG | 2025-09-06 | 2 |
| 04018631316 | LEIDE PEREIRA DE SOUSA | CTR-20250902123842-ACN0F | 2025-09-06 | 3 |
| 00440511313 | LUCIANA SOARES DOS REIS | CTR-20250902152800-WZSZT | 2025-09-06 | 1 |
| 23947268300 | MANOEL DOMINGOS DE SOUSA | CTR-20250909183514-ZJUVG | 2025-09-07 | 3 |
| 73858951315 | MARIA DO AMPARO VASCONCELOS | CTR-20250902124450-T8QAJ | 2025-09-06 | 2 |
| 04366689391 | MARIA JOSE MAZULLO SANTIAGO | CTR-20250902031618-EWA3O | 2025-09-06 | 1 |
| 94659044300 | MEIRYSLANDIA RODRIGUES DE MOURA ALMEIDA | CTR-20250912144219-VVMJE | 2025-09-20 | 2 |
| 74711547304 | PEDRO MOURA ALMONDES | CTR-20250910165531-FPOOX | 2025-09-12 | 3 |
| 00020556357 | RAFAELA DE MOURA ALVES | CTR-20250910175917-CTCUV | 2025-09-07 | 2 |
| 04022234385 | ROSANGELA DE SOUSA SIQUEIRA | CTR-20250902124742-SBPY8 | 2025-09-06 | 1 |

## Lista completa dos contratos com ciclo 1 iniciado em setembro

Todos os contratos abaixo devem ser revisados para mover o inicio operacional do ciclo 1 para `10/2025`.

| CPF | Associado | Contrato | Inicio atual | Status do ciclo 1 | Meses fora do ciclo | Flags |
| --- | --- | --- | --- | --- | --- | --- |
| 28712196304 | ANDENORA FERNANDES GONDIM FARIAS | CTR-20250905141456-KEYRG | 2025-09-06 | apto_a_renovar | 3 | ciclo_futuro_ausente, ciclo_com_lacuna |
| 85461008372 | AUREA CRISTINA SOUSA RODRIGUES | CTR-20250902124951-1XLK0 | 2025-09-06 | ciclo_renovado | 2 | renovacao_incompleta, lacuna_regularizada, ciclo_com_lacuna |
| 10279820429 | CARLA GABRYELLE ALMEIDA DA SILVA | CTR-20250922165756-DEPWL | 2025-09-23 | apto_a_renovar | 3 | ciclo_futuro_ausente, ciclo_com_lacuna |
| 24034126353 | CONCEICAO DE MARIA PEREIRA DA SILVA | CTR-20250911122145-6LBBZ | 2025-09-19 | apto_a_renovar | 3 | ciclo_futuro_ausente, ciclo_com_lacuna |
| 37303988300 | EDILSON PEREIRADO NASCIMENTO | CTR-20250903142218-X82A5 | 2025-09-06 | ciclo_renovado | 3 | renovacao_incompleta, lacuna_regularizada, ciclo_com_lacuna |
| 18213448391 | EDITH FERREIRA DE SOUSA | CTR-20250902112647-8OZCL | 2025-09-06 | ciclo_renovado | 2 | renovacao_incompleta, lacuna_regularizada, ciclo_futuro_ausente, ciclo_com_lacuna |
| 22815295334 | ESTANISLAU FERREIRA DA SILVA | CTR-20250904145647-35H63 | 2025-09-06 | ciclo_renovado | 1 | ciclo_com_lacuna |
| 46330135304 | FATIMA GILDA FERREIRA ALMEIDA DE SOUSA | CTR-20250919195030-PFY2J | 2025-09-24 | ciclo_renovado | 2 | lacuna_regularizada, ciclo_com_lacuna |
| 22693297320 | FLORENTINO INACIO DE OLIVEIRA MENDES | CTR-20250909165407-ERIWV | 2025-09-06 | ciclo_renovado | 1 | lacuna_regularizada, ciclo_com_lacuna |
| 53647327387 | FRANCISCO DE ASSIS SOUSA MACHADO | CTR-20250922181818-QA87J | 2025-09-24 | apto_a_renovar | 3 | ciclo_futuro_ausente, ciclo_com_lacuna |
| 32784066304 | FRANCISCO JORGE DA SILVA | CTR-20250904172221-GZUSV | 2025-09-06 | ciclo_renovado | 2 | lacuna_regularizada, ciclo_com_lacuna |
| 44655681349 | FRANCISCO MAURICIO DE OLIVEIRA SANTOS | CTR-20250918171741-V7ZYC | 2025-09-10 | ciclo_renovado | 2 | lacuna_regularizada, ciclo_com_lacuna |
| 45089922349 | GISELE ALVES MARTINS | CTR-20250919141922-UOSFJ | 2025-09-14 | aberto | 4 | ciclo_com_lacuna |
| 20017928320 | HELIO BARBOSA RIBEIRO MAGALHAES | CTR-20250912124312-1DB4Y | 2025-09-21 | aberto | 4 | ciclo_com_lacuna |
| 44809506487 | JOSE ENOQUE DA SILVA | CTR-20250902174048-LBR17 | 2025-09-06 | ciclo_renovado | 2 | lacuna_regularizada, ciclo_com_lacuna |
| 04511018391 | JOSELIO TALEIRES | CTR-20250917190035-BHHEZ | 2025-09-19 | ciclo_renovado | 1 | lacuna_regularizada, ciclo_com_lacuna |
| 35336820300 | JOAO DE DEUS PEREIRA DA SILVA | CTR-20250916115113-1M5RQ | 2025-09-11 | aberto | 5 | ciclo_com_lacuna |
| 00362954348 | JULIO CESAR ALVES FEITOSA | CTR-20250903140511-WEW7A | 2025-09-06 | ciclo_renovado | 1 | ciclo_com_lacuna |
| 45125260304 | JUSTINO DA SILVA LEAL | CTR-20250902111725-DIMIG | 2025-09-06 | ciclo_renovado | 2 | renovacao_incompleta, lacuna_regularizada, ciclo_com_lacuna |
| 00059690348 | LAURA TORRES DE ALENCAR NETA | CTR-20250922191553-4IFNB | 2025-09-24 | aberto | 4 | ciclo_com_lacuna |
| 04018631316 | LEIDE PEREIRA DE SOUSA | CTR-20250902123842-ACN0F | 2025-09-06 | ciclo_renovado | 3 | renovacao_incompleta, lacuna_regularizada, ciclo_com_lacuna |
| 05675988378 | LETICIA DA COSTA LUSTOSA | CTR-20250903125819-LV5AD | 2025-09-06 | ciclo_renovado | 1 | ciclo_com_lacuna |
| 00351058362 | LORENA EUGENIA VELOSO CARVALHO | CTR-20250904132356-ZLHTR | 2025-09-06 | apto_a_renovar | 3 | ciclo_futuro_ausente, ciclo_com_lacuna |
| 00440511313 | LUCIANA SOARES DOS REIS | CTR-20250902152800-WZSZT | 2025-09-06 | ciclo_renovado | 1 | renovacao_incompleta, ciclo_futuro_ausente, ciclo_com_lacuna |
| 23947268300 | MANOEL DOMINGOS DE SOUSA | CTR-20250909183514-ZJUVG | 2025-09-07 | ciclo_renovado | 3 | renovacao_incompleta, lacuna_regularizada, ciclo_com_lacuna |
| 27391159387 | MARIA AMELIA DE SOUSA | CTR-20250919191159-R9PXK | 2025-09-13 | ciclo_renovado | 1 | ciclo_com_lacuna |
| 83882707372 | MARIA DA CRUZ RODRIGUES ALVES | CTR-20250904155956-CECRL | 2025-09-06 | aberto | 4 | ciclo_com_lacuna |
| 13189921334 | MARIA DA PAZ LIMA CAMPELO | CTR-20250930194858-BFC5V | 2025-09-06 | aberto | 4 | ciclo_com_lacuna |
| 13462857304 | MARIA DAS GRACAS GUIMARAES RIBEIRO | CTR-20250902174226-QGADF | 2025-09-06 | aberto | 4 | ciclo_com_lacuna |
| 09573496372 | MARIA DE FATIMA BARBOSA CARVALHO | CTR-20250905153210-KK43E | 2025-09-06 | ciclo_renovado | 2 | lacuna_regularizada, ciclo_com_lacuna |
| 27503941391 | MARIA DE NAZARETHE OLIVEIRA SALDANHA | CTR-20250909143806-GYTSU | 2025-09-05 | aberto | 0 |  |
| 73858951315 | MARIA DO AMPARO VASCONCELOS | CTR-20250902124450-T8QAJ | 2025-09-06 | ciclo_renovado | 2 | renovacao_incompleta, lacuna_regularizada, ciclo_com_lacuna |
| 04366689391 | MARIA JOSE MAZULLO SANTIAGO | CTR-20250902031618-EWA3O | 2025-09-06 | ciclo_renovado | 1 | renovacao_incompleta, ciclo_futuro_ausente, ciclo_com_lacuna |
| 06711154304 | MARIA VERBENA LEAL DE OLIVEIRA | CTR-20250902113923-XS7IB | 2025-09-06 | aberto | 4 | ciclo_com_lacuna |
| 33965706349 | MARILENE DA CONCEICAO LIMA DA SILVA | CTR-20250905173019-R4DH3 | 2025-09-06 | ciclo_renovado | 1 | lacuna_regularizada, ciclo_com_lacuna |
| 94659044300 | MEIRYSLANDIA RODRIGUES DE MOURA ALMEIDA | CTR-20250912144219-VVMJE | 2025-09-20 | ciclo_renovado | 2 | renovacao_incompleta, lacuna_regularizada, ciclo_futuro_ausente, ciclo_com_lacuna |
| 55318878334 | NIVIA MARIA GONCALVES DO NASCIMENTO | CTR-20250918131055-DNHVF | 2025-09-10 | ciclo_renovado | 2 | lacuna_regularizada, ciclo_com_lacuna |
| 74711547304 | PEDRO MOURA ALMONDES | CTR-20250910165531-FPOOX | 2025-09-12 | ciclo_renovado | 3 | renovacao_incompleta, ciclo_com_lacuna |
| 32748248368 | PEDRO PEREIRA DE OLIVEIRA | CTR-20250922171232-ANGRZ | 2025-09-07 | ciclo_renovado | 2 | lacuna_regularizada, ciclo_com_lacuna |
| 00020556357 | RAFAELA DE MOURA ALVES | CTR-20250910175917-CTCUV | 2025-09-07 | ciclo_renovado | 2 | renovacao_incompleta, lacuna_regularizada, ciclo_com_lacuna |
| 14525119349 | RAIMUNDO NONATO BORGES ABREU | CTR-20250905151554-9WDBB | 2025-09-06 | aberto | 4 | ciclo_com_lacuna |
| 83824049368 | ROSANA MARIA DE ARAUJO | CTR-20250905144406-9WXP0 | 2025-09-06 | ciclo_renovado | 2 | lacuna_regularizada, ciclo_com_lacuna |
| 04022234385 | ROSANGELA DE SOUSA SIQUEIRA | CTR-20250902124742-SBPY8 | 2025-09-06 | ciclo_renovado | 1 | renovacao_incompleta, ciclo_futuro_ausente, ciclo_com_lacuna |
| 20472048368 | TERESA CRISTINA CESAR COELHO RAMOS | CTR-20250910160901-GRGRP | 2025-09-10 | apto_a_renovar | 3 | ciclo_futuro_ausente, ciclo_com_lacuna |
| 36808920206 | VALDINAR DA SILVA OLIVEIRA FILHO | CTR-20250902111244-JDNVU | 2025-09-06 | aberto | 4 | ciclo_com_lacuna |
| 01843564319 | VALERIA CRISTINA DA SILVA CUNHA | CTR-20250915144734-FG6FG | 2025-09-23 | ciclo_renovado | 2 | lacuna_regularizada, ciclo_com_lacuna |
| 06319990350 | WILSON FERREIRA | CTR-20250908174646-ZQMBI | 2025-09-07 | aberto | 5 | ciclo_com_lacuna |

## Regra de ajuste proposta
- Ajustar todos os `47` contratos acima para que o `ciclo 1` comece em `10/2025`.
- Reprocessar a composicao do ciclo 1 com base em `10/2025`, `11/2025` e `12/2025` quando houver evidencias de renovacao desse trio.
- Remover `previsao` de qualquer competencia passada.
- Para competencias passadas, o status permitido deve ser:
  - `descontada`
  - `quitada`
  - `nao_descontada`
- Nos `13` casos com `renovacao_com_ciclo_incompleto`, encerrar o `ciclo 1` corretamente antes de manter o `ciclo 2` como valido.
