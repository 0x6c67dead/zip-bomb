#!/usr/bin/env python3
"""Extrator/inspetor seguro — o padrão de defesa contra zip bombs.

Descomprime em streaming e impõe um TETO de bytes durante a leitura:
nunca confia no tamanho declarado no cabeçalho (quem controla o arquivo
controla esse número). Não escreve nada em disco — conta os bytes que
seriam materializados e aborta se passarem do teto.

Nos zips aninhados, inspeciona um nível por vez: as entradas internas
aparecem como arquivos .zip e não são recursadas automaticamente —
recursão cega é justamente o comportamento que uma bomba explora.

Uso:
    python3 extrator_seguro.py artefatos/bomba_simples.gz --limite-mib 500
    python3 extrator_seguro.py artefatos/bomba_aninhada.zip --limite-mib 2048
"""
from __future__ import annotations

import argparse
import gzip
import sys
import zipfile

TAMANHO_BLOCO = 1 << 20  # 1 MiB por leitura


class EstouroDeTeto(Exception):
    """A leitura passou do limite de bytes descomprimidos."""


def formatar_tamanho(valor: float) -> str:
    """Formata uma quantidade de bytes em unidades legíveis (KiB, MiB, ...)."""
    for unidade in ("B", "KiB", "MiB", "GiB", "TiB"):
        if valor < 1024:
            return f"{valor:.1f} {unidade}"
        valor /= 1024
    return f"{valor:.1f} PiB"


def inspecionar_gzip(caminho: str, limite: int) -> None:
    """Lê o .gz em blocos até o fim ou até estourar o teto."""
    total_lido = 0
    with gzip.open(caminho, "rb") as arquivo_gzip:
        while bloco := arquivo_gzip.read(TAMANHO_BLOCO):
            total_lido += len(bloco)
            if total_lido > limite:
                raise EstouroDeTeto
    print(f"  conteúdo: {formatar_tamanho(total_lido)}")


def inspecionar_zip(caminho: str, limite: int) -> None:
    """Lê cada entrada do .zip em blocos, comparando o contado com o declarado."""
    total_lido = 0
    with zipfile.ZipFile(caminho) as arquivo_zip:
        for entrada in arquivo_zip.infolist():
            bytes_da_entrada = 0
            with arquivo_zip.open(entrada) as conteudo:
                while bloco := conteudo.read(TAMANHO_BLOCO):
                    bytes_da_entrada += len(bloco)
                    total_lido += len(bloco)
                    if total_lido > limite:
                        raise EstouroDeTeto
            # entrada.file_size é o valor DECLARADO no cabeçalho — pode mentir.
            situacao = "ok" if bytes_da_entrada == entrada.file_size else "DIVERGE do cabeçalho!"
            print(
                f"  {entrada.filename}: declarado {formatar_tamanho(entrada.file_size)}, "
                f"contado {formatar_tamanho(bytes_da_entrada)} [{situacao}]"
            )
    print(f"  total (1 nível): {formatar_tamanho(total_lido)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspetor de comprimidos com teto de segurança")
    parser.add_argument("arquivo", help=".gz ou .zip a inspecionar")
    parser.add_argument("--limite-mib", type=int, default=500, help="teto de bytes descomprimidos (default: 500)")
    argumentos = parser.parse_args()
    limite = argumentos.limite_mib << 20

    print(f"[{argumentos.arquivo}] teto: {formatar_tamanho(limite)}")
    try:
        if argumentos.arquivo.endswith(".gz"):
            inspecionar_gzip(argumentos.arquivo, limite)
        elif argumentos.arquivo.endswith(".zip"):
            inspecionar_zip(argumentos.arquivo, limite)
        else:
            sys.exit("formato não suportado (use .gz ou .zip)")
        print("ok: dentro do teto")
    except EstouroDeTeto:
        sys.exit(f"[ABORTADO] passou do teto de {formatar_tamanho(limite)} — resposta correta diante de uma bomba")


if __name__ == "__main__":
    main()
