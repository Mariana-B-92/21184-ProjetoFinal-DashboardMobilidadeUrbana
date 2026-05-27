"""
Módulo de carregamento da configuração do projeto.

A configuração é definida no ficheiro config.yaml na raiz do projeto.
Este módulo fornece uma forma centralizada de aceder a esses parâmetros
em qualquer parte do código.
"""

from pathlib import Path
import yaml


# Caminho para a raiz do projeto (dois níveis acima deste ficheiro)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_config() -> dict:
    """Carrega e retorna a configuração do projeto a partir de config.yaml."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Resolver caminhos relativos para absolutos a partir da raiz do projeto
    for key, value in config["paths"].items():
        config["paths"][key] = str(PROJECT_ROOT / value)

    return config


# Configuração carregada uma vez no momento da importação
CONFIG = load_config()
