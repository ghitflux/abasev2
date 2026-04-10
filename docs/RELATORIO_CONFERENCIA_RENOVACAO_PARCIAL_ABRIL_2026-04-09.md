# Relatório de Conferência da Renovação Parcial de Abril

Data da conferência: 09/04/2026

Arquivo conferido:
- `Controle e Conciliação de Mensalidades_ABASE - RENOVAÇÃO PARCIAL ABRIL.csv`

## Observação inicial
- O arquivo recebido contém `188` associados na base de dados do CSV.
- O número informado de `189` não confere com o conteúdo atual do arquivo.

## Critério usado
- `fev./26`: se a célula está preenchida, o sistema deve ter a competência `02/2026` como resolvida (`descontado`, `liquidada` ou `quitada`).
- `mar./26`: se a célula está preenchida, o sistema deve ter a competência `03/2026` como resolvida (`descontado`, `liquidada` ou `quitada`).
- `abr./26 = PASSIVEL DE RENOVAÇÃO`: o associado deve seguir com status operacional de apto a renovar e sem renovação efetivada no contrato operacional atual.
- `abr./26 = RENOVOU DIA dd/mm/aaaa`: o sistema deve registrar uma renovação efetivada na mesma data.
- `abr./26 = EM PROCESSO DE RENOVAÇÃO DIA 06/04`: o sistema deve registrar renovação em andamento, ainda sem efetivação.

## Resultado geral
- Corretos: `57`
- Incorretos: `131`

## Quebra por status esperado no CSV
- `Passível de renovação`: `30` corretos, `67` incorretos
- `Renovou`: `27` corretos, `63` incorretos
- `Em processo`: `0` corretos, `1` incorreto

## Principais divergências encontradas
- `101` com divergência de status de abril
- `40` com divergência na competência de março
- `20` associados ausentes no sistema
- `1` com divergência na competência de fevereiro
- `1` com divergência de valor em março

## Lista parcial dos associados ausentes no sistema
- CPFs abaixo mantidos exatamente como vieram no CSV. Alguns parecem ter perdido zero à esquerda no arquivo de origem.
- `9945431315` `DIVALDO SOARES LOUREIRO`
- `9573496372` `MARIA DE FATIMA BARBOSA CARVAL`
- `1181773385` `RODRIGO VENTURA DE CASTRO`
- `4022234385` `ROSANGELA DE SOUSA SIQUEIRA`
- `684770318` `DEMERVAL SOUSA E SILVA`
- `9688722391` `EDMILSON GOMES PEREIRA`
- `416897398` `MAX ROSBERK ROCHA OLIVEIRA`
- `9718826300` `MARIA LINDALVA DE SOUSA SOARES`
- `7921454372` `MARIA DE FATIMA PEREIRA DA COS`
- `9683771300` `VERBERT EDUARDO VERAS LIMA`
- `7893515368` `RITA CECILIA GONDIM VERAS`
- `4705033353` `DEOCLECIO FRANCISCO DE ARAUJO`
- `4732243304` `FRANCISCO ARAUJO DA SILVEIRA`
- `4511018391` `JOSELIO TALEIRES`
- `4710975353` `FRANCISCO MORAIS DOS SANTOS`
- `4366689391` `MARIA JOSE MAZULLO SANTIAGO`
- `3442333830` `ANTONIO PEREIRA DE MORAIS`
- `7883684353` `EDVALDO DA CUNHA COSTA`
- `6541062315` `MARIA LUIZA MUNIZ GUIMARAES`
- `3028801353` `MARIA DAS GRACAS PORTELA VELOS`

## Leitura operacional do resultado
- O maior problema não está no valor da mensalidade de fevereiro e março.
- O maior problema está no `status de abril`, ou seja, o CSV diz que o associado ainda está passível ou que renovou em uma data específica, mas o contrato operacional atual não reflete isso corretamente.
- Também existe um bloco relevante de `20` CPFs do CSV que hoje não aparecem no cadastro ativo do sistema.
