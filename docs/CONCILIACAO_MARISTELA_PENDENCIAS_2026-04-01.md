# Pendências da Conciliação Maristela em 2026-04-01

Base usada nesta análise:
- [planilha_manual_maristela.xlsx](/mnt/d/apps/abasev2/abasev2/anexos_legado/Conciliacao/planilha_manual_maristela.xlsx)
- [dry_run_summary.json](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/dry_run_summary.json)
- [planilha_sem_match.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/planilha_sem_match.csv)
- [excecoes_conciliacao.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/excecoes_conciliacao.csv)

Status atual:
- a conciliação já foi aplicada na base
- o dry-run pós-execução fechou com `0` correções planejadas
- o residual aberto é apenas de linhas sem match e competências sem parcela correspondente

## Resumo Executivo

Pendências finais:
- `74` linhas sem match único
- `824` exceções de conciliação
- `822` exceções `parcela_not_found`
- `2` exceções `parcela_conflict`

Leitura operacional:
- as `74` linhas sem match não devem ser corrigidas automaticamente sem decisão manual
- as `822` competências sem parcela não são divergência de valor; são ausência estrutural de parcela na competência pedida pela planilha
- o maior bloco do problema está em `2026-03`, não em outubro/dezembro

## Linhas Sem Match

Distribuição:
- `62` linhas com `CPF` e `matrícula` preenchidos, mas sem correspondente único no sistema
- `4` linhas com `matrícula` ambígua porque a mesma matrícula orgão aparece em dois associados diferentes
- `8` linhas que não são associados; são a legenda/rodapé da própria planilha

### Grupo 1: Rodapé e legenda da planilha

Essas `8` linhas não exigem ajuste de base. O problema é só de parse da planilha atual.

Linhas:
- `643`: `Legenda do Status`
- `644`: `1 - Lançado e Efetivado`
- `645`: `2 - Não Lançado por Falta de Margem Temporariaente`
- `646`: `3 - Não Lançado por Outros Motivos(Ex.Matricula não encontrada, mud de orgão`
- `647`: `4 - Lançado com Valor Diferente`
- `648`: `5 - Não Lançado por Problemas Técnicos`
- `649`: `6 - Lançamento com Erros`
- `650`: `S - Não Lançado: Compra de Dívida ou Suspensão SEAD`

Solução recomendada:
- no próximo ciclo, ajustar o parser para parar de ler quando encontrar `Legenda do Status`
- não há decisão de negócio pendente aqui

### Grupo 2: Matrícula ambígua

Esses `4` casos precisam de saneamento cadastral antes de qualquer nova conciliação automática.

1. Linha `13`
   Planilha: `LETICIA DA COSTA LUSTOSA`, CPF `05675988378`, matrícula `3715825`
   Conflito no sistema:
   - associado `49`: `LETICIA DA COSTA LUSTOSA`, CPF `05675988378`, `matricula_orgao=371582-5`
   - associado `57`: `LORENA EUGENIA VELOSO CARVALHO`, CPF `00351058362`, `matricula_orgao=371582-5`
   Decisão necessária:
   - corrigir a matrícula órgão de um dos dois registros
   - depois rerodar a linha, que tende a casar corretamente pelo CPF da Letícia

2. Linha `32`
   Planilha: `ALICE PEREIRA DAMASCENO`, CPF `10568590325`, matrícula `467138`
   Conflito no sistema:
   - associado `44`: `ALICE PEREIRA DAMASCENO`, CPF `10568590325`, `matricula_orgao=46713-8`
   - associado `46`: `MARIA DAS GRAÇAS GUIMARÃES RIBEIRO`, CPF `13462857304`, `matricula_orgao=46713-8`
   Decisão necessária:
   - corrigir duplicidade de matrícula órgão
   - depois rerodar a conciliação da linha

3. Linha `75`
   Planilha: `MARIA VALDENIR FERREIRA`, CPF `69767165304`, matrícula `164511X`
   Conflito no sistema:
   - associado `359`: `MARIA VALDENIR FERREIRA`, CPF `69767165304`, `matricula_orgao=164511-X`
   - associado `358`: `VALDINAR MARIA FERREIRA`, CPF `35053062315`, `matricula_orgao=164511-X`
   Decisão necessária:
   - revisar qual associado ficou com matrícula órgão incorreta
   - manter a matrícula ligada ao CPF que bate com a planilha

4. Linha `467`
   Planilha: `MARIA APARECIDA PINHEIRO DE SO...`, CPF `47927526391`, matrícula `075859X`
   Conflito no sistema:
   - associado `41`: `MARIA APARECIDA PINHEIRO DE SOUSA BRITO`, CPF `47927526391`, `matricula_orgao=075859-X`
   - associado `43`: `LUCIANA SOARES DOS REIS`, CPF `00440511313`, `matricula_orgao=075859-X`
   Decisão necessária:
   - corrigir a matrícula órgão duplicada
   - só depois reprocessar a linha

Solução recomendada para esse grupo:
- tratar primeiro a duplicidade de `matricula_orgao`
- não forçar conciliação enquanto dois associados diferentes continuarem usando a mesma matrícula

### Grupo 3: Sem match real

Esse grupo tem `62` linhas com CPF e matrícula preenchidos, mas sem associado único no sistema. Aqui há dois caminhos possíveis, e a decisão é de negócio:

1. O associado existe na planilha, mas não foi importado para a base atual.
2. O associado existe na base com CPF ou matrícula divergente do que está na planilha manual.

Solução recomendada para esse grupo:
- conferir primeiro se o CPF da planilha existe em algum acervo auxiliar ou cadastro legado não importado
- quando o CPF existir no sistema com matrícula divergente, corrigir o cadastro mestre antes de rerodar a linha
- quando o associado realmente não existir na base, decidir se ele deve ser criado/importado ou mantido fora da conciliação

Lista completa:
- usar [planilha_sem_match.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/planilha_sem_match.csv)

## Competências Sem Parcela

Distribuição geral das `822` exceções `parcela_not_found`:
- `553` casos de `lacuna_no_intervalo_de_parcelas`
- `179` casos de `competencia_depois_ultima_parcela`
- `90` casos de `competencia_antes_primeira_parcela`

Interpretação:
- `lacuna_no_intervalo_de_parcelas`: a competência faltante cai entre a primeira e a última parcela já existentes do associado
- `competencia_depois_ultima_parcela`: a planilha pede um mês posterior à última parcela existente no sistema
- `competencia_antes_primeira_parcela`: a planilha pede um mês anterior à primeira parcela existente no sistema

### Matriz por competência

`2025-10-01`
- `1` lacuna no intervalo
- `7` antes da primeira parcela

`2025-12-01`
- `32` lacunas no intervalo
- `24` antes da primeira parcela
- `2` depois da última parcela

`2026-01-01`
- `76` lacunas no intervalo
- `27` antes da primeira parcela
- `5` depois da última parcela

`2026-02-01`
- `40` lacunas no intervalo
- `16` antes da primeira parcela
- `19` depois da última parcela

`2026-03-01`
- `404` lacunas no intervalo
- `16` antes da primeira parcela
- `153` depois da última parcela

Leitura operacional:
- março concentra a maior parte do problema
- o maior bloco de março não é “contrato acabou”; é lacuna interna de calendário
- isso indica forte evidência de ciclos/parcelas faltando no miolo da esteira, não só ausência de renovação

### Exemplos reais por categoria

`lacuna_no_intervalo_de_parcelas`
- `MARIA DO SOCORRO RUBEN PEREIRA`, CPF `20168942372`
  Competência faltante: `2026-03`
  Intervalo existente no sistema: `2026-02` até `2026-05`
- `VALDIRENE PINHEIRO DIAS AVENDAÑO REATEGUI`, CPF `24051772349`
  Competência faltante: `2026-03`
  Intervalo existente no sistema: `2026-02` até `2026-05`
- `CILENE LOPES MADEIRA`, CPF `62414070315`
  Competência faltante: `2026-03`
  Intervalo existente no sistema: `2025-09` até `2026-04`

Leitura:
- existe parcela antes e depois da competência pedida
- a decisão aqui tende a ser reconstrução do calendário/ciclo, não recusa da planilha

`competencia_depois_ultima_parcela`
- `LEILA RUTH ALVES COSTA`, CPF `83216065391`
  Competência faltante: `2026-03`
  Última parcela existente: `2026-02`
- `ANA LINA SILVA DOS REIS`, CPF `67337643349`
  Competência faltante: `2026-03`
  Última parcela existente: `2026-02`
- `CARLOS HENRIQUE RIBEIRO DE SOUSA`, CPF `39563243315`
  Competência faltante: `2026-03`
  Última parcela existente: `2026-02`

Leitura:
- aqui há duas hipóteses válidas:
  - o contrato realmente não deveria mais produzir parcela após fevereiro
  - a renovação/continuidade existe na planilha, mas o sistema não abriu a próxima competência

`competencia_antes_primeira_parcela`
- `ANTONIO JOSE DE OLIVEIRA`, CPF `13248898372`
  Competência faltante: `2025-12`
  Primeira parcela existente: `2026-01`
- `VALMIR DE ALBUQUERQUE PAULINO`, CPF `37211420120`
  Competência faltante: `2026-01`
  Primeira parcela existente: `2026-02`
- `WLADIMIR SANTANA RIBEIRO`, CPF `82939039372`
  Competência faltante: `2025-12`
  Primeira parcela existente: `2026-01`

Leitura:
- o contrato entrou na base com início posterior ao que a planilha considera
- a decisão é confirmar se a competência histórica deve ser retrocriada no sistema ou se a planilha está apontando para um vínculo anterior ao contrato atual

### Casos de conflito de parcela

Há `2` exceções `parcela_conflict`, ambas para o mesmo associado:

`JEAN DOUGLAS RODRIGUES REIS`, CPF `71339477300`, matrícula `112926X`
- competência `2025-12`
- competência `2026-01`

Conflito encontrado:
- contrato `CTR-20260114102948-FZJ2I`
- contrato `CTR-20250919170719-2YAMN`

Leitura:
- o associado possui duas parcelas válidas na mesma competência em contratos diferentes
- antes de qualquer nova conciliação é preciso decidir qual contrato é o canônico para dezembro/2025 e janeiro/2026

## Solução Recomendada, Sem Aplicar Nada Agora

Ordem sugerida de tratamento:

1. Higienizar a planilha de entrada
   - ignorar automaticamente a legenda/rodapé

2. Resolver ambiguidade cadastral
   - corrigir as 4 duplicidades de `matricula_orgao`

3. Tratar `sem match` real
   - revisar as `62` linhas que têm CPF e matrícula, mas não existem na base
   - decidir caso a caso entre:
     - criar/importar associado faltante
     - corrigir CPF/matrícula do cadastro atual
     - manter a linha fora do sistema

4. Tratar `lacuna_no_intervalo_de_parcelas`
   - esse é o maior bloco e o mais forte candidato a correção sistêmica
   - a solução provável é reconstrução de ciclo/competência faltante por contrato, não baixa manual simples

5. Tratar `competencia_antes_primeira_parcela` e `competencia_depois_ultima_parcela`
   - aqui a decisão depende de negócio
   - é preciso confirmar se a planilha está olhando o mesmo contrato/ciclo que a base atual representa

6. Resolver os 2 conflitos de parcela
   - definir contrato canônico
   - remover ou neutralizar a duplicidade de competência

## Arquivos Para Decisão Manual

Pendências linha a linha:
- [planilha_sem_match.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/planilha_sem_match.csv)
- [excecoes_conciliacao.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/excecoes_conciliacao.csv)

Pendências em JSON:
- [planilha_sem_match.json](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/planilha_sem_match.json)
- [excecoes_conciliacao.json](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/excecoes_conciliacao.json)

Associados fora da planilha:
- [sistema_fora_da_planilha.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/sistema_fora_da_planilha.csv)
- [sistema_fora_da_planilha_priorizados.csv](/mnt/d/apps/abasev2/abasev2/backups/maristela_sheet_20260401T152454_verify3/sistema_fora_da_planilha_priorizados.csv)
