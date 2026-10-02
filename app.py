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

# Extensões suportadas
VIDEO_EXTENSIONS = ('.mp4', '.webm', '.mov', '.mkv')
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.ogg', '.aac', '.flac')
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg')

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
            nome_lower = nome.lower()
            
            is_video = nome_lower.endswith(VIDEO_EXTENSIONS)
            is_audio = nome_lower.endswith(AUDIO_EXTENSIONS)
            
            itens.append({
                "nome": nome,
                "url": url,
                "is_video": is_video,
                "is_audio": is_audio
            })
    except Exception as e:
        print(f"Erro ao listar arquivos: {e}")

    return render_template('index.html', itens=itens)

@app.route('/upload', methods=['POST'])
def upload():
    arquivo = request.files.get('file')
    if arquivo and arquivo.filename != '':
        try:
            # Timestamp para evitar nomes duplicados
            nome_limpo = f"{int(time.time())}_{arquivo.filename}"
            conteudo = arquivo.read()
            content_type = arquivo.content_type

            supabase.storage.from_(BUCKET_NAME).upload(
                path=nome_limpo,
                file=conteudo,
                file_options={"content-type": content_type}
            )
        except Exception as e:
            print(f"Erro ao fazer upload: {e}")

    return redirect(url_for('index'))

@app.route('/deletar/<path:nome_arquivo>', methods=['POST'])
def deletar(nome_arquivo):
    try:
        supabase.storage.from_(BUCKET_NAME).remove([nome_arquivo])
        print(f"Arquivo removido com sucesso: {nome_arquivo}")
    except Exception as e:
        print(f"Erro ao deletar {nome_arquivo}: {e}")

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
