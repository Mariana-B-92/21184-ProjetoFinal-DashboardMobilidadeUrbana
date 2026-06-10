"""
Lancador do dashboard para utilizacao simples.

Destina-se a quem nao quer usar a linha de comandos: arranca o servidor e abre
o navegador automaticamente na pagina do dashboard. E o ficheiro chamado pelo
"Iniciar Dashboard.bat" (duplo-clique). Para desenvolvimento continua a poder
correr-se "python -m app.app", que usa o modo debug.
"""

import threading
import webbrowser

from app.app import app

URL = "http://127.0.0.1:8050"


def _abrir_navegador():
    webbrowser.open(URL)


if __name__ == "__main__":
    # Abre o navegador pouco depois de o servidor arrancar (o carregamento dos
    # dados ja terminou neste ponto, pelo que o servidor liga quase de imediato).
    threading.Timer(1.5, _abrir_navegador).start()
    # debug=False: sem recarregador automatico nem avisos de programador,
    # adequado para utilizacao normal.
    app.run(debug=False, host="127.0.0.1", port=8050)