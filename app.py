import os
import time
from flask import Flask, render_template, request, redirect, url_for
from supabase import create_client, Client

app = Flask(__name__)

# Configurações do Supabase via Variáveis de Ambiente
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "midias"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Extensões suportadas
VIDEO_EXTENSIONS = ('.mp4', '.webm', '.ogg', '.mov')
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')

@app.route('/', methods=['GET'])
def index():
    itens = []
    try:
        # Lista os arquivos dentro do bucket
        arquivos = supabase.storage.from_(BUCKET_NAME).list()
        
        for arq in arquivos:
            nome = arq['name']
            # Ignora pastas ou arquivos ocultos que o supabase às vezes cria
            if nome == '.emptyFolderPlaceholder':
                continue
                
            # Gera o link direto do arquivo
            url = supabase.storage.from_(BUCKET_NAME).get_public_url(nome)
            
            # Identifica se é vídeo ou imagem pela extensão
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
        # Adiciona um timestamp na frente do nome para evitar arquivos duplicados
        nome_limpo = f"{int(time.time())}_{arquivo.filename}"
        conteudo = arquivo.read()
        content_type = arquivo.content_type

        # Envia para o Supabase Storage
        supabase.storage.from_(BUCKET_NAME).upload(
            path=nome_limpo,
            file=conteudo,
            file_options={"content-type": content_type}
        )

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)