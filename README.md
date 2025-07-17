Segue uma lista com alguns dos comandos principais do uv e uma breve explicação para cada um:

uv init [nome_do_projeto]
Inicializa um novo projeto, criando a estrutura necessária e um ambiente virtual.

uv add [pacote]
Adiciona uma nova dependência ao projeto e a instala automaticamente no ambiente.

uv run [comando/script]             
Executa comandos ou scripts dentro do ambiente isolado do projeto. Pode ser usado para rodar testes, ferramentas ou o próprio aplicativo.

uv lock
Gera ou atualiza o lockfile universal, garantindo que as versões das dependências fiquem travadas para reproduções futuras.

uv sync
Sincroniza o ambiente de desenvolvimento com o lockfile, instalando ou removendo pacotes conforme necessário.

uv tool run (ou o alias uvx)
Executa ferramentas de linha de comando fornecidas por pacotes Python em um ambiente efêmero, similar ao que o pipx faz.

uv tool install [ferramenta]
Instala uma ferramenta Python de forma global, permitindo o uso contínuo sem precisar do ambiente efêmero.

uv python install [versão1] [versão2] ...
Instala uma ou mais versões do Python, facilitando o gerenciamento de múltiplas versões.

uv venv --python [versão]
Cria um novo ambiente virtual utilizando a versão do Python especificada.

uv python pin [versão]
Define a versão do Python que deverá ser usada por padrão no projeto, salvando essa configuração em um arquivo (como o .python-version).

uv pip compile [arquivo_de_entrada] --universal --output-file [arquivo_de_saida]
Compila as dependências declaradas em um arquivo de entrada em um arquivo de requisitos compatível e universal.

uv pip sync [arquivo_de_requisitos]
Sincroniza o ambiente instalando exatamente as versões especificadas no arquivo de requisitos.

Aqui estão algumas dicas avançadas para tirar o máximo proveito do uv:

Aproveite os Workspaces:
Se você trabalha com projetos complexos ou monorepos, use a funcionalidade de workspaces (estilo Cargo). Isso permite compartilhar dependências entre subprojetos e manter uma configuração centralizada, reduzindo redundâncias e facilitando a manutenção.

Utilize o Cache Global:
O uv possui um cache global para deduplicar dependências. Essa abordagem não só economiza espaço em disco, mas também acelera as instalações, pois as mesmas versões de pacotes não são baixadas repetidamente.

Inline Dependency Metadata para Scripts:
Para scripts únicos, adicione metadados inline diretamente no arquivo. Isso garante que, ao rodar o script com uv run, todas as dependências necessárias sejam instaladas automaticamente, melhorando a portabilidade e a reprodutibilidade.

Gerencie Múltiplas Versões do Python:
Aproveite o comando uv python install para instalar diferentes versões do Python e use o uv python pin para fixar uma versão específica no projeto. Isso ajuda a manter consistência em ambientes de desenvolvimento e produção.

Interface Pip Avançada:
Use os comandos do uv que reproduzem a interface do pip, como uv pip compile e uv pip sync, para gerar lockfiles universais e instalar pacotes de forma reprodutível. Essas ferramentas permitem ajustes finos, como overrides de versões e resolução de dependências de forma mais robusta.

Integração com Ferramentas de Linha de Comando:
Experimente o uv tool run (ou seu alias uvx) para executar ferramentas Python em ambientes efêmeros. Essa prática é especialmente útil para testar utilitários sem poluir seu ambiente global.

Automatização e CI/CD:
Considere integrar o uv em seus pipelines de CI/CD. Os comandos de lock, sync e execução de scripts facilitam a criação de builds reprodutíveis e consistentes, o que é essencial para fluxos de trabalho automatizados.

Configuração Avançada e Overrides:
Explore os arquivos de configuração do uv para customizar o comportamento da resolução de dependências, definir variáveis de ambiente específicas e ajustar a forma como o uv lida com os pacotes. Essa customização pode ser crucial em projetos com requisitos específicos.

Atualizações e Performance:
Fique atento às atualizações do uv, pois a equipe frequentemente adiciona melhorias de performance e novas funcionalidades. Testar novas versões em um ambiente controlado pode trazer benefícios consideráveis no fluxo de trabalho.

atualizar pip install --upgrade uv

🚀 Instalando e Configurando o Ruff com uv
Se você ainda não tem o Ruff no seu ambiente gerenciado pelo uv, instale-o assim:


uv add ruff
Se quiser instalar o Ruff globalmente como uma ferramenta de linha de comando:

uv tool install ruff
🔍 Executando o Ruff
Agora que o Ruff está instalado, você pode começar a usá-lo!

1️⃣ Checando problemas no código (Linting):

uv run ruff check .
Esse comando verifica todo o código na pasta atual (.) e exibe problemas de estilo, importações não utilizadas, erros de sintaxe, etc.

2️⃣ Formatando código com o Ruff (substituindo Black):

uv run ruff format .
O Ruff pode formatar seu código no estilo do Black, mas é muito mais rápido.

3️⃣ Corrigindo automaticamente os erros de linting (fixing):

uv run ruff check . --fix
Isso aplica correções automáticas para problemas simples, como remover imports não usados e corrigir formatações básicas.

📂 Usando o Ruff em um Projeto
Se você quiser configurar o Ruff para um projeto específico, pode criar um arquivo pyproject.toml e adicionar as configurações:

toml

[tool.ruff]
# Escolha regras específicas (exemplo: flake8, isort, pyflakes)
select = ["E", "F", "I"]

# Ignore regras específicas
ignore = ["E501"]  # E501 = Linha muito longa

# Máximo de caracteres por linha
line-length = 88

# Organizar imports automaticamente
[tool.ruff.isort]
known-first-party = ["meuprojeto"]
Depois, execute:

uv run ruff check .
Agora o Ruff seguirá as regras definidas no seu pyproject.toml.

🔄 Integrando o Ruff no seu Workflow
Se quiser rodar o Ruff automaticamente antes de commits, use o pre-commit:

Adicione o Ruff ao pre-commit:
uv add pre-commit
No arquivo .pre-commit-config.yaml, adicione:
yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.14  # Atualize para a versão mais recente
    hooks:
      - id: ruff
      - id: ruff-format
Instale os hooks:
uv run pre-commit install
Agora, sempre que você tentar fazer um commit, o Ruff será executado automaticamente para garantir que o código está formatado e sem erros.

🎯 Dicas Avançadas
Use ruff --explain [código] para entender melhor cada erro:
uv run ruff --explain E501
Rodando o Ruff apenas em arquivos alterados:
uv run ruff check --diff
Rodando o Ruff em múltiplos arquivos ou apenas um específico:
uv run ruff check src/ tests/
🏁 Resumo
✔ Ruff pode substituir Black, isort, Flake8 e PyLint com muito mais velocidade
✔ Pode ser facilmente integrado ao uv
✔ Configurável via pyproject.toml
✔ Funciona com pre-commit para manter seu código limpo automaticamente

Se quiser mais exemplos ou precisar de ajuda com um caso específico, só avisar! 🚀🐍