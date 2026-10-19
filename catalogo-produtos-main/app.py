from pathlib import Path
import sqlite3
import uuid

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import session, redirect, url_for
from flask import request, session, redirect, url_for
from flask import render_template, request, redirect, url_for, session


app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['UPLOAD_FOLDER'] = Path(app.root_path) / 'static' / 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'].mkdir(parents=True, exist_ok=True)


def conexao():
    conn = sqlite3.connect(Path(app.root_path) / 'database.db')
    conn.row_factory = sqlite3.Row
    return conn


def atualizar_tabela_produto():
    with conexao() as conn:
        colunas = conn.execute(
            "PRAGMA table_info(produto)"
        ).fetchall()

        nomes = [coluna["name"] for coluna in colunas]

        if "quantidade" not in nomes:
            conn.execute("""
                ALTER TABLE produto
                ADD COLUMN quantidade INTEGER NOT NULL DEFAULT 0
            """)

atualizar_tabela_produto()

@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    session.pop('usuario_nome', None)
    session.pop('tipo', None)

    flash('Você saiu da sua conta.', 'success')
    return redirect(url_for('login'))

def atualizar_tabela_usuario():
    with conexao() as conn:
        colunas = conn.execute(
            "PRAGMA table_info(usuario)"
        ).fetchall()

        nomes = [coluna["name"] for coluna in colunas]

        if "tipo" not in nomes:
            conn.execute("""
                ALTER TABLE usuario
                ADD COLUMN tipo TEXT NOT NULL DEFAULT 'cliente'
            """)


ROTAS_ADMIN = {
    'painel_admin',
    'index',
    'listarCategoria',
    'cadastrarCategoria',
    'editarCategoria',
    'excluirCategoria',
    'listarProduto',
    'editarProduto',
    'excluirProduto',
    'listarUsuario',
    'cadastrarUsuario',
    'editarUsuario',
    'excluirUsuario',
    'cadastrarProduto',
}


@app.before_request
def proteger_rotas_administrativas():
    if request.endpoint not in ROTAS_ADMIN:
        return

    if 'usuario_id' not in session:
        flash('Faça login para acessar o painel.', 'warning')
        return redirect(url_for('login'))

    if session.get('tipo') != 'admin':
        flash('Acesso permitido somente ao administrador.', 'danger')
        return redirect(url_for('loja'))

def extensao_permitida(nome_arquivo):
    return '.' in nome_arquivo and nome_arquivo.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def salvar_imagem(arquivo, prefixo='imagem'):
    """Salva a imagem em static/uploads e retorna o caminho relativo usado pelo url_for('static')."""
    if not arquivo or not arquivo.filename:
        return None

    nome_original = secure_filename(arquivo.filename)
    if not extensao_permitida(nome_original):
        raise ValueError('Formato de imagem não permitido. Use PNG, JPG, JPEG, GIF ou WEBP.')

    extensao = nome_original.rsplit('.', 1)[1].lower()
    nome = f'{prefixo}_{uuid.uuid4().hex}.{extensao}'
    arquivo.save(app.config['UPLOAD_FOLDER'] / nome)
    return f'uploads/{nome}'


def excluir_imagem(caminho):
    """Remove apenas arquivos armazenados em static/uploads."""
    if not caminho or not caminho.startswith('uploads/'):
        return
    arquivo = Path(app.root_path) / 'static' / caminho
    if arquivo.exists() and arquivo.is_file():
        arquivo.unlink()


@app.route('/')
def inicio():
    return redirect(url_for('login'))


@app.route('/loja')
def loja():
    busca = request.args.get('busca', '').strip()
    categoria_id = request.args.get('categoria', '').strip()

    sql = '''
        SELECT produto.*, categoria.nome AS categoria_nome
        FROM produto
        LEFT JOIN categoria ON categoria.id = produto.id_categoria
        WHERE produto.ativo = 1
    '''
    parametros = []

    if busca:
        sql += ' AND produto.nome LIKE ?'
        parametros.append(f'%{busca}%')

    if categoria_id.isdigit():
        sql += ' AND produto.id_categoria = ?'
        parametros.append(int(categoria_id))

    sql += ' ORDER BY produto.id DESC'

    with conexao() as conn:
        produtos = conn.execute(sql, parametros).fetchall()
        categorias = conn.execute(
            'SELECT id, nome FROM categoria WHERE ativo = 1 ORDER BY nome'
        ).fetchall()

    return render_template(
        'loja/index.html',
        produtos=produtos,
        categorias=categorias,
        busca=busca,
        categoria_selecionada=categoria_id
    )

@app.route('/loja/produto/<int:id>')
def detalhes_produto(id):
    with conexao() as conn:
        produto = conn.execute('''
            SELECT produto.*, categoria.nome AS categoria_nome
            FROM produto
            LEFT JOIN categoria ON categoria.id = produto.id_categoria
            WHERE produto.id = ? AND produto.ativo = 1
        ''', (id,)).fetchone()

    if produto is None:
        return 'Produto não encontrado', 404

    return render_template('loja/detalhes.html', produto=produto)

@app.route('/carrinho/adicionar/<int:id>', methods=['POST'])
def adicionar_carrinho(id):
    with conexao() as conn:
        produto = conn.execute(
            '''
            SELECT id, nome, preco
            FROM produto
            WHERE id = ? AND ativo = 1
            ''',
            (id,)
        ).fetchone()

    if produto is None:
        return 'Produto não encontrado', 404

    carrinho = session.get('carrinho', {})
    produto_id = str(produto['id'])

    if produto_id in carrinho:
        carrinho[produto_id]['quantidade'] += 1
    else:
        carrinho[produto_id] = {
            'nome': produto['nome'],
            'preco': float(produto['preco']),
            'quantidade': 1
        }

    session['carrinho'] = carrinho
    session.modified = True

    return redirect(url_for('ver_carrinho'))


@app.route('/carrinho')
def ver_carrinho():
    carrinho = session.get('carrinho', {})

    total = sum(
        item['preco'] * item['quantidade']
        for item in carrinho.values()
    )

    return render_template(
        'loja/carrinho.html',
        carrinho=carrinho,
        total=total
    )

@app.route('/carrinho/atualizar/<int:id>', methods=['POST'])
def atualizar_carrinho(id):
    carrinho = session.get('carrinho', {})
    produto_id = str(id)

    if produto_id in carrinho:
        try:
            quantidade = int(request.form.get('quantidade', 1))
        except (ValueError, TypeError):
            quantidade = 1

        if quantidade <= 0:
            carrinho.pop(produto_id, None)
        else:
            carrinho[produto_id]['quantidade'] = min(quantidade, 99)

        session['carrinho'] = carrinho
        session.modified = True

    return redirect(url_for('ver_carrinho'))


@app.route('/carrinho/remover/<int:id>', methods=['POST'])
def remover_carrinho(id):
    carrinho = session.get('carrinho', {})
    carrinho.pop(str(id), None)

    session['carrinho'] = carrinho
    session.modified = True

    return redirect(url_for('ver_carrinho'))


@app.route('/carrinho/finalizar', methods=['POST'])
def finalizar_compra():
    if 'usuario_id' not in session:
        flash('Faça login para finalizar sua compra.', 'warning')
        return redirect(url_for('login'))

    carrinho = session.get('carrinho', {})

    if not carrinho:
        flash('Seu carrinho está vazio.', 'warning')
        return redirect(url_for('ver_carrinho'))

    with conexao() as conn:
        for produto_id, item in carrinho.items():
            produto = conn.execute(
                'SELECT quantidade, nome FROM produto WHERE id = ? AND ativo = 1',
                (int(produto_id),)
            ).fetchone()

            if produto is None:
                flash('Um produto do carrinho não está mais disponível.', 'danger')
                return redirect(url_for('ver_carrinho'))

            quantidade_comprada = int(item['quantidade'])

            if produto['quantidade'] < quantidade_comprada:
                flash(
                    f'Estoque insuficiente para {produto["nome"]}. '
                    f'Disponível: {produto["quantidade"]}.',
                    'danger'
                )
                return redirect(url_for('ver_carrinho'))

        for produto_id, item in carrinho.items():
            conn.execute(
                '''
                UPDATE produto
                SET quantidade = quantidade - ?
                WHERE id = ?
                ''',
                (int(item['quantidade']), int(produto_id))
            )

        conn.commit()

    session.pop('carrinho', None)
    flash('Compra finalizada e estoque atualizado!', 'success')
    return redirect(url_for('loja'))



@app.route('/listar_categorias')
def listarCategoria():
    with conexao() as conn:
        categorias = conn.execute('SELECT * FROM categoria ORDER BY id DESC').fetchall()
    return render_template('admin/listar_categoria.html', categorias=categorias)


@app.route('/cadastrar_categorias', methods=['GET', 'POST'])
def cadastrarCategoria():
    if request.method == 'POST':
        nome_categoria = request.form.get('nome_categoria', '').strip()
        descricao = request.form.get('descricao', '').strip()
        ativo = request.form.get('ativo', 'False')
        imagem = request.files.get('imagem')

        if not nome_categoria:
            flash('Informe o nome da categoria.', 'danger')
            return render_template('admin/cadastrar_categoria.html')

        try:
            caminho_imagem = salvar_imagem(imagem, 'categoria')
        except ValueError as erro:
            flash(str(erro), 'danger')
            return render_template('admin/cadastrar_categoria.html')

        with conexao() as conn:
            conn.execute(
                '''INSERT INTO categoria (nome, descricao, ativo, img)
                   VALUES (?, ?, ?, ?)''',
                (nome_categoria, descricao, ativo, caminho_imagem),
            )
            conn.commit()

        flash('Categoria cadastrada com sucesso.', 'success')
        return redirect(url_for('listarCategoria'))

    return render_template('admin/cadastrar_categoria.html')


@app.route('/editarcategoria/<int:id>', methods=['GET', 'POST'])
def editarCategoria(id):
    with conexao() as conn:
        categoria = conn.execute('SELECT * FROM categoria WHERE id = ?', (id,)).fetchone()

    if categoria is None:
        flash('Categoria não encontrada.', 'danger')
        return redirect(url_for('listarCategoria'))

    if request.method == 'POST':
        nome_categoria = request.form.get('nome_categoria', '').strip()
        descricao = request.form.get('descricao', '').strip()
        ativo = request.form.get('ativo', 'False')
        imagem = request.files.get('imagem')
        caminho_imagem = categoria['img']

        if not nome_categoria:
            flash('Informe o nome da categoria.', 'danger')
            return render_template('admin/editar_categoria.html', categoria=categoria)

        if imagem and imagem.filename:
            try:
                novo_caminho = salvar_imagem(imagem, f'categoria_{id}')
            except ValueError as erro:
                flash(str(erro), 'danger')
                return render_template('admin/editar_categoria.html', categoria=categoria)

            excluir_imagem(caminho_imagem)
            caminho_imagem = novo_caminho

        with conexao() as conn:
            conn.execute(
                '''UPDATE categoria
                   SET nome = ?, descricao = ?, ativo = ?, img = ?
                   WHERE id = ?''',
                (nome_categoria, descricao, ativo, caminho_imagem, id),
            )
            conn.commit()

        flash('Categoria atualizada com sucesso.', 'success')
        return redirect(url_for('listarCategoria'))

    return render_template('admin/editar_categoria.html', categoria=categoria)


@app.route('/excluir_categoria/<int:id>', methods=['GET', 'POST'])
def excluirCategoria(id):
    with conexao() as conn:
        categoria = conn.execute('SELECT * FROM categoria WHERE id = ?', (id,)).fetchone()

    if categoria is None:
        flash('Categoria não encontrada.', 'danger')
        return redirect(url_for('listarCategoria'))

    if request.method == 'POST':
        with conexao() as conn:
            conn.execute('DELETE FROM categoria WHERE id = ?', (id,))
            conn.commit()
        excluir_imagem(categoria['img'])
        flash('Categoria excluída com sucesso.', 'success')
        return redirect(url_for('listarCategoria'))

    return render_template('admin/excluir_categoria.html', categoria=categoria)


@app.route('/listar_produtos')
def listarProduto():
    with conexao() as conn:
        produtos = conn.execute(
            '''SELECT produto.*, categoria.nome AS categoria_nome
               FROM produto
               LEFT JOIN categoria ON categoria.id = produto.id_categoria
               ORDER BY produto.id DESC'''
        ).fetchall()
    return render_template('admin/listar_produto.html', produtos=produtos)



@app.route('/editar_produto/<int:id>', methods=['GET', 'POST'])
def editarProduto(id):
    with conexao() as conn:
        produto = conn.execute(
            'SELECT * FROM produto WHERE id = ?',
            (id,)
        ).fetchone()

        categorias = conn.execute(
            'SELECT * FROM categoria ORDER BY nome'
        ).fetchall()

    if produto is None:
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('listarProduto'))

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        preco_texto = request.form.get('preco', '').strip()
        ativo = request.form.get('ativo', 'True')
        categoria_texto = request.form.get('id_categoria', '')

        if not nome:
            flash('Informe o nome do produto.', 'danger')
            return redirect(url_for('editarProduto', id=id))

        try:
            preco = float(preco_texto.replace(',', '.'))

            if preco < 0:
                raise ValueError

            id_categoria = (
                int(categoria_texto)
                if categoria_texto
                else None
            )

        except ValueError:
            flash('Informe um preço ou uma categoria válida.', 'danger')
            return redirect(url_for('editarProduto', id=id))

        with conexao() as conn:
            conn.execute(
                '''
                UPDATE produto
                SET nome = ?,
                    preco = ?,
                    ativo = ?,
                    id_categoria = ?
                WHERE id = ?
                ''',
                (nome, preco, ativo, id_categoria, id)
            )
            conn.commit()

        flash('Produto atualizado com sucesso!', 'success')
        return redirect(url_for('listarProduto'))

    return render_template(
        'admin/editar_produto.html',
        produto=produto,
        categorias=categorias
    )

@app.route('/repor_estoque/<int:id>', methods=['POST'])
def reporEstoque(id):
    try:
        quantidade = int(request.form.get('quantidade', 0))

        if quantidade <= 0:
            flash('Informe uma quantidade maior que zero.', 'danger')
            return redirect(url_for('listarProduto'))

        with conexao() as conn:
            produto = conn.execute(
                'SELECT id FROM produto WHERE id = ?',
                (id,)
            ).fetchone()

            if produto is None:
                flash('Produto não encontrado.', 'danger')
                return redirect(url_for('listarProduto'))

            conn.execute(
                '''
                UPDATE produto
                SET quantidade = COALESCE(quantidade, 0) + ?
                WHERE id = ?
                ''',
                (quantidade, id)
            )
            conn.commit()

        flash('Estoque atualizado com sucesso!', 'success')

    except ValueError:
        flash('Informe uma quantidade válida.', 'danger')

    return redirect(url_for('listarProduto'))

@app.route('/excluir_produto/<int:id>', methods=['GET', 'POST'])
def excluirProduto(id):
    with conexao() as conn:
        produto = conn.execute(
            'SELECT * FROM produto WHERE id = ?', (id,)
        ).fetchone()

    if produto is None:
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('listarProduto'))

    if request.method == 'POST':
        with conexao() as conn:
            conn.execute(
                'DELETE FROM produto WHERE id = ?', (id,)
            )
            conn.commit()

        excluir_imagem(produto['img'])
        flash('Produto excluído com sucesso.', 'success')
        return redirect(url_for('listarProduto'))

    return render_template(
        'admin/excluir_produto.html',
        produto=produto
    )




@app.route('/listar_usuarios')
def listarUsuario():
    with conexao() as conn:
        usuarios = conn.execute('SELECT id, nome, ativo FROM usuario ORDER BY id DESC').fetchall()
    return render_template('admin/listar_usuario.html', usuarios=usuarios)


@app.route('/cadastrar_usuarios', methods=['GET', 'POST'])
def cadastrarUsuario():
    if request.method == 'POST':
        nome = request.form.get('nome').strip()
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        ativo = request.form.get('ativo', 'False')

        if not nome or not senha:
            flash('Informe o nome e a senha do usuário.', 'danger')
            return render_template('admin/cadastrar_usuario.html')

        if senha != confirmar_senha:
            flash('As senhas não conferem.', 'danger')
            return render_template('admin/cadastrar_usuario.html')

        with conexao() as conn:
            if conn.execute('SELECT 1 FROM usuario WHERE nome = ?', (nome,)).fetchone():
                flash('Já existe um usuário com esse nome.', 'danger')
                return render_template('admin/cadastrar_usuario.html')

            conn.execute(
    '''INSERT INTO usuario (nome, senha, ativo, tipo)
       VALUES (?, ?, ?, ?)''',
    (nome, generate_password_hash(senha), ativo, 'cliente'),
)
            conn.commit()

        flash('Usuário cadastrado com sucesso.', 'success')
        return redirect(url_for('listarUsuario'))

    return render_template('admin/cadastrar_usuario.html')


@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
def editarUsuario(id):
    with conexao() as conn:
        usuario = conn.execute('SELECT * FROM usuario WHERE id = ?', (id,)).fetchone()

    if usuario is None:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('listarUsuario'))

    if request.method == 'POST':
        nome = request.form.get('nome').strip()
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        ativo = request.form.get('ativo', 'False')

        if not nome:
            flash('Informe o nome do usuário.', 'danger')
            return render_template('admin/editar_usuario.html', usuario=usuario)

        if senha != confirmar_senha:
            flash('As senhas não conferem.', 'danger')
            return render_template('admin/editar_usuario.html', usuario=usuario)

        with conexao() as conn:
            if conn.execute('SELECT 1 FROM usuario WHERE nome = ? AND id <> ?', (nome, id)).fetchone():
                flash('Já existe um usuário com esse nome.', 'danger')
                return render_template('admin/editar_usuario.html', usuario=usuario)

            if senha:
                conn.execute(
                    'UPDATE usuario SET nome = ?, senha = ?, ativo = ? WHERE id = ?',
                    (nome, generate_password_hash(senha), ativo, id),
                )
            else:
                conn.execute(
                    'UPDATE usuario SET nome = ?, ativo = ? WHERE id = ?',
                    (nome, ativo, id),
                )
            conn.commit()

        flash('Usuário atualizado com sucesso.', 'success')
        return redirect(url_for('listarUsuario'))

    return render_template('admin/editar_usuario.html', usuario=usuario)


@app.route('/excluir_usuario/<int:id>', methods=['GET', 'POST'])
def excluirUsuario(id):
    with conexao() as conn:
        usuario = conn.execute('SELECT id, nome FROM usuario WHERE id = ?', (id,)).fetchone()

    if usuario is None:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('listarUsuario'))

    if request.method == 'POST':
        with conexao() as conn:
            conn.execute('DELETE FROM usuario WHERE id = ?', (id,))
            conn.commit()
        flash('Usuário excluído com sucesso.', 'success')
        return redirect(url_for('listarUsuario'))

    return render_template('admin/excluir_usuario.html', usuario=usuario)


@app.route('/cadastrar_produto', methods=['GET', 'POST'])
def cadastrarProduto():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        preco_texto = request.form.get('preco', '').strip()
        id_categoria = request.form.get('id_categoria', '').strip()
        ativo = 1 if request.form.get('ativo') == '1' else 0
        arquivo = request.files.get('imagem')

        if not nome or not preco_texto:
            flash('Preencha o nome e o preço do produto.', 'danger')
            return redirect(url_for('cadastrarProduto'))

        try:
            preco = float(preco_texto.replace(',', '.'))
            if preco < 0:
                raise ValueError
            categoria_id = int(id_categoria) if id_categoria else None
        except ValueError:
            flash('Informe um preço e uma categoria válidos.', 'danger')
            return redirect(url_for('cadastrarProduto'))

        caminho_imagem = None

        if arquivo and arquivo.filename:
            nome_seguro = secure_filename(arquivo.filename)

            if not nome_seguro:
                flash('Nome de imagem inválido.', 'danger')
                return redirect(url_for('cadastrarProduto'))

            nome_arquivo = f'{uuid.uuid4().hex}_{nome_seguro}'
            arquivo.save(app.config['UPLOAD_FOLDER'] / nome_arquivo)
            caminho_imagem = f'uploads/{nome_arquivo}'

        try:
            with conexao() as conn:
                conn.execute(
                    '''INSERT INTO produto
                       (nome, preco, ativo, id_categoria, img)
                       VALUES (?, ?, ?, ?, ?)''',
                    (nome, preco, ativo, categoria_id, caminho_imagem)
                )
                conn.commit()
        except Exception:
            if caminho_imagem:
                caminho_salvo = app.config['UPLOAD_FOLDER'] / nome_arquivo
                if caminho_salvo.exists():
                    caminho_salvo.unlink()
            raise

        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('listarProduto'))

    with conexao() as conn:
        categorias = conn.execute(
            'SELECT id, nome FROM categoria ORDER BY nome'
        ).fetchall()

    return render_template(
        'admin/cadastrar_produto.html',
        categorias=categorias
    )

@app.route('/admin')
def painel_admin():
    return render_template('admin/index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        senha = request.form.get('senha', '')

        with conexao() as conn:
            usuario = conn.execute(
                "SELECT * FROM usuario WHERE nome = ?",
                (nome,)
            ).fetchone()

        if not usuario:
            flash('Usuário não encontrado.', 'danger')
            return redirect(url_for('login'))

        if not check_password_hash(usuario['senha'], senha):
            flash('A senha não confere.', 'danger')
            return redirect(url_for('login'))

        if str(usuario['ativo']).lower() not in ('1', 'true', 'ativo'):
            flash('Usuário inativo. Entre em contato com o administrador.', 'warning')
            return redirect(url_for('login'))

        session['usuario_id'] = usuario['id']
        session['usuario_nome'] = usuario['nome']
        session['tipo'] = usuario['tipo']

        if usuario['tipo'] == 'admin':
            return redirect(url_for('painel_admin'))

        return redirect(url_for('loja'))

    return render_template('login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
    
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        senha = request.form.get('senha', '')
        confirmar_senha = request.form.get('confirmar_senha', '')

        if not nome or not senha:
            flash('Preencha o nome e a senha.', 'danger')
            return render_template('cadastro.html')

        if senha != confirmar_senha:
            flash('As senhas não conferem.', 'danger')
            return render_template('cadastro.html')

        with conexao() as conn:
            existente = conn.execute(
                'SELECT 1 FROM usuario WHERE nome = ?',
                (nome,)
            ).fetchone()

            if existente:
                flash('Esse nome de usuário já está cadastrado.', 'danger')
                return render_template('cadastro.html')

            conn.execute(
                '''INSERT INTO usuario (nome, senha, ativo, tipo)
                   VALUES (?, ?, ?, ?)''',
                (nome, generate_password_hash(senha), '1', 'cliente')
            )
            conn.commit()

        flash('Cadastro realizado! Faça login para continuar.', 'success')
        return redirect(url_for('login'))

    return render_template('cadastro.html')


atualizar_tabela_usuario()

if __name__ == '__main__':
    app.run(debug=True, port=5005)
