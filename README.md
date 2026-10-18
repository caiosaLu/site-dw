# Site DW — Sistema de Gerenciamento de Produtos

Sistema web desenvolvido em Python com Flask para gerenciar produtos, categorias e usuários, utilizando banco de dados SQLite e uma interface administrativa baseada no AdminLTE.

## Funcionalidades

- Cadastro, listagem, edição e exclusão de produtos.
- Gerenciamento de categorias.
- Gerenciamento de usuários.
- Upload de imagens de produtos e categorias.
- Armazenamento de dados em banco SQLite.
- Interface administrativa com HTML, CSS, JavaScript e Bootstrap.

## Tecnologias utilizadas

- **Python** — linguagem de programação.
- **Flask** — framework web.
- **SQLite** — banco de dados.
- **HTML5 e CSS3** — estrutura e estilos das páginas.
- **Bootstrap** — componentes e responsividade.
- **Jinja2** — renderização de templates.
- **AdminLTE** — interface do painel administrativo.

## Como executar o projeto

### 1. Pré-requisitos

- Python instalado.
- Git instalado.
- Visual Studio Code (opcional).

### 2. Clone o repositório

```bash
git clone https://github.com/SEU-USUARIO/site-dw.git
cd site-dw
```

Substitua `SEU-USUARIO` pelo seu nome de usuário do GitHub.

### 3. Crie um ambiente virtual

No Windows:

```powershell
python -m venv .venv
```

Ative o ambiente virtual:

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Instale as dependências

```bash
python -m pip install Flask
```

### 5. Execute a aplicação

```bash
python app.py
```

Acesse no navegador:

http://127.0.0.1:5005

## Estrutura principal

- `app.py` — rotas e lógica da aplicação.
- `banco.sql` — script SQL de criação das tabelas.
- `init_db.py` — inicialização do banco de dados.
- `database.db` — banco de dados SQLite.
- `templates/` — páginas HTML.
- `templates/admin/` — páginas administrativas.
- `static/` — arquivos estáticos, imagens, CSS e JavaScript.
- `static/uploads/` — imagens enviadas pela aplicação.

## Objetivo

Projeto desenvolvido para praticar e demonstrar conhecimentos em desenvolvimento web com Python, operações CRUD, integração com banco de dados e criação de interfaces administrativas.

## Autor

Desenvolvido como projeto de estudo em desenvolvimento web.
