# Dashboard de Intermodalidade Bicicleta-Metro — imagem de producao (Hugging Face Spaces)
# A app Dash corre via Docker e e servida por gunicorn na porta 7860 (a porta do HF).

FROM python:3.11-slim

# Utilizador nao-root, conforme recomendado pelo Hugging Face Spaces (UID 1000).
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /home/user/app

# Instalar dependencias primeiro (aproveita a cache de build do Docker).
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copiar o codigo e a base de dados ja construida (data/processed/mobilidade.db).
COPY --chown=user . .

# Porta exposta pela aplicacao (esperada pelo Hugging Face Spaces).
EXPOSE 7860

# Servidor de producao: serve o objeto Flask `server` definido em app/app.py.
# 1 worker + threads chega de sobra para a baixa concorrencia de um estudo;
# timeout folgado para a primeira operacao espacial (mudanca de raio).
CMD ["gunicorn", "--bind", "0.0.0.0:7860", \
     "--workers", "1", "--threads", "8", "--timeout", "120", \
     "app.app:server"]
