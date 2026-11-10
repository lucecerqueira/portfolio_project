#!/usr/bin/env bash
# Interrompe o script caso ocorra algum erro
set -o errexit

# Atualiza instalador de pacotes
pip install --upgrade pip

# Instala as dependências científicas e do Django
pip install -r requirements.txt

# Coleta os arquivos estáticos (CSS, JS, Three.js) com compressão WhiteNoise
python manage.py collectstatic --no-input --clear

# Aplica as migrações do banco de dados (SQLite/PostgreSQL)
python manage.py migrate
