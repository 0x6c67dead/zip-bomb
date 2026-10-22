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

CHUNK = 1 << 20  # 1 MiB


class EstouroDeTeto(Exception):
    """A leitura passou do limite de bytes descomprimidos."""


def fmt(n: float) -> str:
    for unidade in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} PiB"


def inspecionar_gzip(caminho: str, limite: int) -> None:
    total = 0
    with gzip.open(caminho, "rb") as f:
        while chunk := f.read(CHUNK):
            total += len(chunk)
            if total > limite:
                raise EstouroDeTeto
    print(f"  conteúdo: {fmt(total)}")


def inspecionar_zip(caminho: str, limite: int) -> None:
    total = 0
    with zipfile.ZipFile(caminho) as z:
        for info in z.infolist():
            contado = 0
            with z.open(info) as f:
                while chunk := f.read(CHUNK):
                    contado += len(chunk)
                    total += len(chunk)
                    if total > limite:
                        raise EstouroDeTeto
            # file_size é o valor DECLARADO no cabeçalho — pode mentir.
            marca = "ok" if contado == info.file_size else "DIVERGE do cabeçalho!"
            print(f"  {info.filename}: declarado {fmt(info.file_size)}, contado {fmt(contado)} [{marca}]")
    print(f"  total (1 nível): {fmt(total)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspetor de comprimidos com teto de segurança")
    ap.add_argument("arquivo", help=".gz ou .zip a inspecionar")
    ap.add_argument("--limite-mib", type=int, default=500, help="teto de bytes descomprimidos (default: 500)")
    args = ap.parse_args()
    limite = args.limite_mib << 20

    print(f"[{args.arquivo}] teto: {fmt(limite)}")
    try:
        if args.arquivo.endswith(".gz"):
            inspecionar_gzip(args.arquivo, limite)
        elif args.arquivo.endswith(".zip"):
            inspecionar_zip(args.arquivo, limite)
        else:
            sys.exit("formato não suportado (use .gz ou .zip)")
        print("ok: dentro do teto")
    except EstouroDeTeto:
        sys.exit(f"[ABORTADO] passou do teto de {fmt(limite)} — resposta correta diante de uma bomba")


if __name__ == "__main__":
    main()
