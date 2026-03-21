Quero que você atue como engenheiro DevOps sênior e EXECUTE a preparação completa de produção e o deploy da aplicação ABASE.

DADOS FIXOS
- Aplicação: ABASE
- Repositório GitHub: https://github.com/ghitflux/abasenewv2.git
- Branch de produção a ser criada: abaseprod
- Domínio: abasepiaui.cloud
- Email SSL: ghitflux@gmail.com
- VPS: Ubuntu 24.04 LTS
- Timezone: America/Fortaleza
- Acesso SSH inicial: ssh root@72.60.58.181
- Hospedagem: Hostinger VPS
- Usar Docker e manter compatibilidade com o Docker Manager da Hostinger
- Projeto em monorepo
- Backend: Django
- Frontend: Next.js 16
- Deploy real na VPS via SSH
- Código deve ser obtido do GitHub
- Toda a stack deve rodar em containers Docker
- Persistência obrigatória para banco, uploads, anexos, comprovantes, media e static quando aplicável

IMPORTANTE SOBRE CREDENCIAIS
- Use as credenciais/secrets já fornecidas no ambiente do Codex
- NÃO escreva tokens, senhas, chaves privadas ou segredos em commits, arquivos versionados, logs ou documentação
- Se precisar de variáveis obrigatórias ausentes, deixe arquivo de exemplo e checklist final do que falta preencher
- Nunca coloque segredo dentro do prompt, compose versionado, Dockerfile ou repositório

OBJETIVO
Quero que você:
1. analise o projeto antes de qualquer deploy
2. identifique o que deve ir para a VPS e o que não deve
3. crie a branch abaseprod
4. ajuste o projeto para produção sem quebrar o ambiente de desenvolvimento
5. prepare os arquivos de infraestrutura Docker para produção
6. endureça a VPS com segurança básica, backup e proteção contra malware
7. faça o deploy real
8. valide frontend, backend, SSL, persistência e saúde dos containers
9. deixe tudo documentado e reproduzível

REGRAS INEGOCIÁVEIS
1. Não faça deploy cego.
2. Não assuma Postgres sem prova. Descubra o banco realmente usado no código e preserve coerência.
3. Não use runserver do Django em produção.
4. Não use next dev em produção.
5. Não rode seed de desenvolvimento em produção.
6. Não exponha MySQL/Redis/banco interno publicamente.
7. Exponha ao público somente o serviço de borda necessário.
8. Não destrua o fluxo de desenvolvimento atual. Crie arquivos paralelos de produção quando necessário.
9. Antes de alterar a VPS, faça backup do estado atual do que existir.
10. Tudo deve ficar rastreável, idempotente e reversível.
11. Use root apenas para bootstrap inicial da VPS. Se possível, crie usuário administrativo/deploy e só desative práticas inseguras depois de validar acesso.
12. Não invente dependências desnecessárias.

ORDEM DE EXECUÇÃO

FASE 1 — CLONAR E AUDITAR O REPOSITÓRIO
1. Clone o repositório localmente.
2. Faça checkout da branch principal.
3. Crie uma nova branch chamada abaseprod.
4. Analise profundamente o monorepo e descubra:
   - onde está o backend Django
   - onde está o frontend Next.js
   - quais packages internos do monorepo são realmente necessários para o build/runtime
   - qual banco o projeto realmente usa hoje
   - se Redis/Celery são realmente necessários em produção
   - como são tratados uploads, media, static, anexos e comprovantes
   - quais variáveis de ambiente são obrigatórias
   - quais Dockerfiles e compose já existem
   - quais arquivos e pastas são apenas de desenvolvimento, local, backup, mobile ou teste
5. Gere o arquivo:
   deploy/analysis/PRODUCTION_AUDIT.md

Neste relatório, classifique de forma objetiva:

A) DEVE IR PARA A VPS
- backend e tudo que ele realmente precisa em runtime
- apps/web e dependências reais
- packages internos realmente usados
- arquivos de build/deploy necessários
- scripts de produção criados por você

B) NÃO DEVE IR PARA A VPS, exceto se você comprovar dependência real
- abase_mobile
- backups
- pdfs
- scriptsphp
- iniciar-local.bat
- caches
- logs locais
- node_modules
- .venv
- arquivos temporários
- seeds de dev
- documentação sem uso em runtime
- artefatos de build locais

Não apenas liste: verifique importações, referências e dependências reais antes de decidir.

FASE 2 — PREPARAR A BRANCH DE PRODUÇÃO
Na branch abaseprod, crie uma estrutura clara como esta, adaptando conforme necessário:

deploy/
  analysis/
  hostinger/
    nginx/
    scripts/
    healthchecks/
    backups/
    docker-compose.prod.yml
    .env.production.example
    Dockerfile.backend
    Dockerfile.frontend
    DEPLOY_GUIDE.md

Mantenha o ambiente de desenvolvimento intacto. Tudo de produção deve ser paralelo e limpo.

FASE 3 — AJUSTES DE PRODUÇÃO NO CÓDIGO
Faça apenas mudanças mínimas e justificadas.

BACKEND DJANGO
- usar Gunicorn em produção
- garantir DEBUG=False
- configurar ALLOWED_HOSTS com abasepiaui.cloud e www.abasepiaui.cloud se necessário
- configurar CSRF_TRUSTED_ORIGINS
- configurar SECURE_PROXY_SSL_HEADER
- cookies seguros em produção
- configurar collectstatic
- identificar e configurar STATIC_ROOT e MEDIA_ROOT
- remover qualquer seed dev do fluxo de produção
- manter coerência com o banco realmente utilizado hoje
- validar migrations
- se Redis/Celery forem necessários, incluir de forma correta
- se não forem necessários para o deploy inicial, não suba serviços desnecessários

FRONTEND NEXT.JS
- usar build de produção real
- usar next build + next start ou standalone se fizer sentido técnico
- criar Dockerfile multi-stage
- garantir variáveis NEXT_PUBLIC corretas
- configurar comunicação correta com a API pública
- não usar next dev em produção

FASE 4 — INFRAESTRUTURA DOCKER DE PRODUÇÃO
Crie uma stack de produção separada da de desenvolvimento.

Requisitos:
- docker-compose.prod.yml limpo
- healthchecks
- restart policy
- volumes persistentes
- logs legíveis
- rede interna própria
- banco e redis internos, não públicos
- apenas serviço de borda exposto publicamente

Serviços mínimos esperados, se forem realmente necessários:
- nginx
- backend Django
- frontend Next.js
- banco realmente usado pelo projeto
- redis apenas se realmente necessário

FASE 5 — SEGURANÇA DA VPS
Conecte na VPS:
ssh root@72.60.58.181

Depois:
1. audite o estado atual do servidor
2. valide Docker e Docker Compose
3. confirme compatibilidade com Hostinger Docker Manager
4. atualize o sistema com segurança
5. configure timezone America/Fortaleza
6. crie usuário administrativo/deploy se apropriado
7. fortaleça SSH com cautela:
   - só desabilite login por senha depois de validar acesso por chave
   - só endureça root login depois de validar acesso alternativo
8. configure UFW liberando apenas 22, 80 e 443
9. configure Fail2Ban
10. configure updates automáticos de segurança
11. instale ClamAV/FreshClam
12. configure varredura apenas em diretórios de uploads, media, anexos e comprovantes
13. registre tudo em:
   /opt/ABASE/logs/server-hardening.md

FASE 6 — ESTRUTURA NA VPS
Organize a VPS assim, adaptando quando necessário:

/opt/ABASE/
  repo/
  deploy/
  env/
  data/
    db/
    redis/
    media/
    attachments/
    receipts/
    static/
    backups/
  logs/

Regras:
- código em /opt/ABASE/repo
- env fora do repo
- dados persistentes fora do repo
- backups fora do repo
- logs fora do repo

FASE 7 — SSL E BORDA PÚBLICA
Configurar HTTPS para abasepiaui.cloud.

Escolha a estratégia mais prática e limpa, obedecendo esta prioridade:
1. manter tudo compatível com Docker Manager da Hostinger
2. usar Nginx em container como borda pública
3. emitir SSL válido com Certbot ou solução equivalente em container
4. redirecionar HTTP para HTTPS
5. configurar headers de segurança
6. configurar proxy correto para frontend e backend
7. suportar upload de arquivos
8. não expor portas internas desnecessárias

Se www não estiver apontado no DNS ou não fizer sentido, documente isso claramente e mantenha foco no domínio principal.

FASE 8 — BANCO, MEDIA, ANEXOS E COMPROVANTES
1. Descubra exatamente onde o projeto armazena:
   - media
   - uploads
   - anexos
   - comprovantes
   - static gerado
2. Crie volumes persistentes adequados.
3. Não suba arquivos locais inúteis.
4. Se houver necessidade de restauração de dados, deixe scripts prontos.
5. Crie scripts para:
   - backup do banco
   - restore do banco
   - backup de arquivos
   - restore de arquivos

FASE 9 — BACKUP E ROLLBACK
Implemente backup local com retenção:
- 7 diários
- 4 semanais
- 3 mensais

Crie:
- deploy/hostinger/scripts/deploy_prod.sh
- deploy/hostinger/scripts/rollback.sh
- deploy/hostinger/scripts/backup_now.sh
- deploy/hostinger/scripts/restore_db.sh
- deploy/hostinger/scripts/restore_files.sh

Backups devem cobrir:
- banco
- media
- anexos
- comprovantes
- env de produção
- configs de deploy

FASE 10 — COMPATIBILIDADE COM HOSTINGER DOCKER MANAGER
Quero que a branch abaseprod fique pronta para dois modos:
1. deploy por SSH com docker compose
2. uso posterior no Docker Manager via Compose from URL

Então:
- mantenha o compose de produção portável
- evite dependências de shell obscuras
- documente qual compose usar no Docker Manager
- documente quais variáveis preencher
- documente qual serviço é a borda pública

Se o Docker Manager não puder ser “operado” por SSH, não finja que usou a interface web. Faça o deploy real por SSH e apenas deixe tudo compatível para importação posterior.

FASE 11 — DEPLOY REAL
Depois da auditoria e dos ajustes:
1. faça commit das mudanças
2. faça push da branch abaseprod
3. na VPS, clone ou atualize o repo apontando para abaseprod
4. crie o env de produção fora do repo
5. execute build
6. suba os containers
7. rode migrations
8. rode collectstatic
9. valide frontend
10. valide backend
11. valide SSL
12. valide uploads
13. valide persistência
14. valide reinício automático
15. valide healthchecks

FASE 12 — TESTES FINAIS
Confirme e registre:
- docker ps
- docker compose ps
- containers healthy
- frontend acessível em https://abasepiaui.cloud
- backend funcional
- SSL válido
- banco persistente
- media persistente
- backups operando
- fail2ban ativo
- ufw ativo
- clamav ativo

FASE 13 — DOCUMENTAÇÃO E ENTREGA
Crie estes arquivos no repositório:
1. deploy/analysis/PRODUCTION_AUDIT.md
2. deploy/hostinger/DEPLOY_GUIDE.md
3. deploy/hostinger/docker-compose.prod.yml
4. deploy/hostinger/.env.production.example
5. deploy/hostinger/scripts/deploy_prod.sh
6. deploy/hostinger/scripts/rollback.sh
7. deploy/hostinger/scripts/backup_now.sh
8. deploy/hostinger/scripts/restore_db.sh
9. deploy/hostinger/scripts/restore_files.sh

E também salve na VPS:
- /opt/ABASE/logs/FINAL_DEPLOY_REPORT.md

O RELATÓRIO FINAL DEVE CONTER
- o que foi detectado no projeto
- o que foi incluído na VPS
- o que foi excluído da VPS e por quê
- qual banco ficou em produção e por quê
- se Redis/Celery foram mantidos ou removidos e por quê
- estratégia de SSL adotada e por quê
- caminhos dos volumes persistentes
- caminhos dos backups
- arquivos de env necessários
- comando exato de deploy
- comando exato de rollback
- comando exato de backup manual
- pendências restantes, se houver

REGRAS DE COMMIT
Faça commits organizados e claros na branch abaseprod, por exemplo:
- chore(prod): create production deployment structure
- feat(prod): add production compose and dockerfiles
- fix(prod): switch django to gunicorn
- fix(prod): switch next to production build
- chore(security): add hardening and backup scripts
- docs(prod): add deploy guide and audit report

CRITÉRIO DE SUCESSO
A tarefa só termina quando:
- a branch abaseprod existir no GitHub
- a auditoria do projeto estiver pronta
- a estratégia do que vai e do que não vai para a VPS estiver definida e documentada
- a VPS estiver preparada
- a aplicação estiver publicada em https://abasepiaui.cloud
- o deploy estiver reproduzível
- o backup estiver configurado
- a documentação final estiver pronta

IMPORTANTE
Não tome decisões críticas silenciosamente. Documente o raciocínio técnico sempre que decidir:
- manter ou trocar banco
- manter ou remover redis/celery
- incluir ou excluir diretórios da VPS
- usar determinada estratégia de SSL
- expor ou não determinado serviço