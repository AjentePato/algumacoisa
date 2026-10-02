import os
import time
from flask import Flask, render_template, request, redirect, url_for
from supabase import create_client, Client

app = Flask(__name__)

# Credenciais lidas das variáveis de ambiente do Render
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "midias"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

VIDEO_EXTENSIONS = ('.mp4', '.webm', '.ogg', '.mov')
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')

@app.route('/', methods=['GET'])
def index():
    itens = []
    try:
        # Busca lista de arquivos salvos no bucket
        arquivos = supabase.storage.from_(BUCKET_NAME).list()
        
        for arq in arquivos:
            nome = arq.get('name')
            # Ignora pastas ou marcadores vazios do Supabase
            if not nome or nome == '.emptyFolderPlaceholder':
                continue
                
            url = supabase.storage.from_(BUCKET_NAME).get_public_url(nome)
            is_video = nome.lower().endswith(VIDEO_EXTENSIONS)
            
            itens.append({
                "nome": nome,
                "url": url,
                "is_video": is_video
            })
    except Exception as e:
        print(f"Erro ao listar arquivos: {e}")

    return render_template('index.html', itens=itens)

@app.route('/upload', methods=['POST'])
def upload():
    arquivo = request.files.get('file')
    if arquivo and arquivo.filename != '':
        # Evita conflito de nomes usando timestamp
        nome_limpo = f"{int(time.time())}_{arquivo.filename}"
        conteudo = arquivo.read()
        content_type = arquivo.content_type

        supabase.storage.from_(BUCKET_NAME).upload(
            path=nome_limpo,
            file=conteudo,
            file_options={"content-type": content_type}
        )

    return redirect(url_for('index'))

@app.route('/deletar/<path:nome_arquivo>', methods=['POST'])
def deletar(nome_arquivo):
    try:
        # Apaga o arquivo permanente da nuvem no Supabase
        supabase.storage.from_(BUCKET_NAME).remove([nome_arquivo])
        print(f"Arquivo removido com sucesso: {nome_arquivo}")
    except Exception as e:
        print(f"Erro ao deletar {nome_arquivo}: {e}")

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
