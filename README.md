# zip-bomb

Estudo sobre **bombas de descompressão** (zip bombs): por que funcionam, como são construídas, onde aparecem como superfície de ataque e — principalmente — como se defender. Faz parte dos meus estudos em segurança ofensiva.

> ⚠️ **Aviso**: material estramente educacional. Usar isso contra sistemas de terceiros sem autorização é um ataque de negação de serviço (ilegal na maioria das jurisdições). O uso legítimo é testar a resiliência dos **seus próprios** sistemas. Os defaults do gerador são deliberadamente modestos (GB, não PB).

## Por que funciona

Compressão sem perda remove **redundância**. O DEFLATE (usado em `.zip` e `.gz`) substitui repetições por referências, então 1 GiB de zeros comprime para ~1 MiB. O teto prático de uma única passada é **~1032:1** — imposto pela janela deslizante de 32 KiB do LZ77.

A vulnerabilidade nasce de uma **assimetria de custo**: enviar/armazenar o arquivo comprimido é barato, mas processá-lo custa proporcional ao tamanho *descomprimido*. Quem controla o input comprimido escolhe quanto o alvo vai materializar:

```
custo do atacante  ≈ tamanho comprimido      (42 KB)
custo do alvo      ≈ tamanho descomprimido   (4,5 PB)
```

## As construções

| Construção | Mecanismo | Razão típica |
|---|---|---|
| **Simples** | Dado altamente redundante comprimido uma vez | até ~1032:1 (teto do DEFLATE) |
| **Aninhada** | Zip contendo *k* cópias de um zip, *n* níveis; o total multiplica: `fundo × kⁿ` | exponencial em *n* |
| **Cabeçalhos sobrepostos** (estado da arte, Fifield 2019) | Um único fluxo DEFLATE cujos cabeçalhos de arquivo locais se sobrepõem, fazendo o mesmo dado comprimido contar como vários arquivos — sem recursão | 281.000:1 (10 MB → 281 TB) |
| **Quine** | Um zip que contém a si mesmo; a extração gera o zip de novo, indefinidamente | potencialmente infinita |

O clássico `42.zip` são 42.374 bytes que, extraídos recursivamente (16 cópias por nível, 5 níveis), expandem para **4,5 PB**.

## Superfícies de ataque

O vetor nunca é o arquivo em si — é um **serviço que descomprime input não confiável sem limite**:

- **Upload em web apps** — avatares, anexos, importadores que aceitam `.zip`/`.gz`
- **Formatos que são zip por baixo** — `.docx`, `.xlsx`, `.pptx`, `.odt`, `.jar`, `.apk`
- **Gateways de e-mail/antivírus** que escaneiam anexos (a bomba como distração pra travar o scanner)
- **HTTP** — servidor que aceita `Content-Encoding: gzip` num POST pequeno e infla pra GB antes de validar
- **Imagens** — PNG/JPEG têm compressão própria ("decompression bomb" de imagem); XML tem o análogo *billion laughs*
- **Pipelines de CI/CD e parsers de backup** processando artefatos de fontes externas

## Efeito no alvo

É um **DoS de recurso**, não invasão — três modos conforme como a vítima extrai:

- **Disco**: extração em filesystem → enche `/tmp`, partição ou quota, derruba vizinhos
- **Memória**: extração em RAM (`zipfile.read()`, `ZipInputStream`) → OOM killer / limite de cgroup
- **CPU**: bombas quine/recursivas gastam ciclos infinitos inflando e recomprimindo

## Defesa

1. **Nunca confie no tamanho declarado no cabeçalho** (`ZipEntry.getSize()`, `info.file_size`) — ele é controlado por quem fez o arquivo
2. Extraia com **limite de bytes imposto durante a leitura** (streaming + teto), abortando ao passar do limite — é o que o `extrator_seguro.py` demonstra
3. Rode descompressão de input não confiável em **sandbox com quota de disco, limite de memória e timeout de CPU** — o blast radius vira um container, não o host

## Como usar

```bash
# gerar os três artefatos didáticos (saem em artefatos/, gitignored)
python3 gerador.py simples                       # 1 GiB de zeros -> ~1 MiB
python3 gerador.py aninhada                      # ~6 MiB -> ~6,4 GiB se extraído
python3 gerador.py controle                      # aleatório: razão ~1:1

# inspecionar sem materializar (os cabeçalhos dos próprios arquivos são honestos;
# os de um atacante, não)
unzip -l artefatos/bomba_aninhada.zip
gzip -l artefatos/bomba_simples.gz

# o padrão de defesa: streaming com teto
python3 extrator_seguro.py artefatos/bomba_simples.gz --limite-mib 500   # aborta: 1 GiB > 500 MiB
python3 extrator_seguro.py artefatos/bomba_aninhada.zip --limite-mib 64
```

O roteiro completo de experimentos está em [`experimentos.md`](experimentos.md).

## Estrutura

```
gerador.py           gerador didático (simples / aninhada / controle)
extrator_seguro.py   inspetor com teto de bytes — a defesa em código
experimentos.md      roteiro de experimentos e observações esperadas
artefatos/           artefatos gerados (não versionados)
```

## Referências

- [Zip bomb — Wikipedia](https://en.wikipedia.org/wiki/Zip_bomb) — visão geral e o caso 42.zip
- [David Fifield — *A better zip bomb* (USENIX WOOT 2019)](https://www.bamsoftware.com/hacks/zipbomb/) — bomba não-recursiva com cabeçalhos sobrepostos: 10 MB → 281 TB
- [Russ Cox — *Zip Files All The Way Down*](https://research.swtch.com/zip) — construção de zips quine (que contêm a si mesmos)
