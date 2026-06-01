"""
Preparacao dos dados: extrai os historicos GIRA (.7z) para data/raw/.

Garante a reprodutibilidade do pipeline a partir dos ficheiros originais,
sem necessidade de versionar os CSV (grandes) no repositorio.
"""

import os
import sys
from pathlib import Path

import py7zr

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

# Mapeamento: arquivo .7z -> nome final do CSV em data/raw/
ARQUIVOS = {
    "historico-1semestre-2022.7z": "gira_1semestre_2022.csv",
    "historico-2--semestre-2022.7z": "gira_2semestre_2022.csv",
}


def preparar():
    for arquivo, destino in ARQUIVOS.items():
        caminho_7z = config.DIR_RAW / arquivo
        caminho_destino = config.DIR_RAW / destino

        if not caminho_7z.exists():
            print(f"[aviso] nao encontrado: {caminho_7z}")
            continue

        with py7zr.SevenZipFile(caminho_7z, "r") as z:
            nomes = z.getnames()
            z.extractall(config.DIR_RAW)
        # Renomeia o CSV extraido para o nome esperado pelo config.
        # os.replace substitui sempre o destino (em qualquer SO), garantindo que
        # data/raw/ reflete a versao mais recente da fonte. Este comportamento e
        # propositado: o projeto e um prototipo extensivel a dados atualizados.
        for nome in nomes:
            origem = config.DIR_RAW / nome
            if origem.suffix.lower() == ".csv":
                if origem.resolve() != caminho_destino.resolve():
                    os.replace(origem, caminho_destino)
                print(f"[ok] {arquivo} -> {destino}")


if __name__ == "__main__":
    preparar()
