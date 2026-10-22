# Roteiro de experimentos

Cada experimento tem uma pergunta, o comando e a observação esperada.

## 1. Redundância é tudo (o grupo de controle)

**Pergunta:** o que faz um arquivo virar bomba — o tamanho ou o conteúdo?

```bash
python3 gerador.py simples --tamanho-mib 64
python3 gerador.py controle --tamanho-mib 64
```

**Esperado:** mesmo pipeline, mesmo tamanho de entrada. Os zeros comprimem ~1000:1; o aleatório fica em ~1:1. Compressão só "paga" quando há redundância a remover.

## 2. O teto de uma passada

**Pergunta:** até onde vai a razão com uma única compressão?

```bash
python3 gerador.py simples --tamanho-mib 64
python3 gerador.py simples --tamanho-mib 1024
```

**Esperado:** a razão cresce devagar (logaritmicamente) e converge para o teto do DEFLATE (~1032:1), imposto pela janela de 32 KiB do LZ77. Comprimir mais forte não passa disso — por isso bombas maiores precisam de *estrutura*, não de compressão.

## 3. Multiplicação estrutural (aninhamento)

**Pergunta:** como a aninhada passa do teto sem comprimir "melhor"?

```bash
python3 gerador.py aninhada --fundo-mib 16 --niveis 2 --copias 4   # 16 MiB × 16
python3 gerador.py aninhada --fundo-mib 16 --niveis 3 --copias 4   # 16 MiB × 64
python3 gerador.py aninhada --fundo-mib 16 --niveis 3 --copias 8   # 16 MiB × 512
```

**Esperado:** o arquivo final quase não cresce entre as variações, mas o total se extraído multiplica por `kⁿ`. É o mecanismo do 42.zip: razão exponencial com arquivo externo minúsculo.

## 4. Cabeçalho declarado vs. contado

**Pergunta:** dá pra confiar no que o cabeçalho diz?

```bash
unzip -l artefatos/bomba_aninhada.zip
python3 extrator_seguro.py artefatos/bomba_aninhada.zip --limite-mib 512
```

**Esperado:** nos nossos artefatos, declarado == contado (somos honestos). O ponto do experimento é a lição defensiva: o cabeçalho é um campo do arquivo, controlado por quem o criou — a checagem tem que acontecer **durante** a descompressão, contando bytes, nunca antes confiando no valor declarado.

## 5. O teto salvando você

**Pergunta:** o que o extrator seguro muda na prática?

```bash
python3 extrator_seguro.py artefatos/bomba_simples.gz --limite-mib 500
python3 extrator_seguro.py artefatos/bomba_simples.gz --limite-mib 2048
```

**Esperado:** com teto de 500 MiB ele aborta no meio (o conteúdo é 1 GiB); com 2048 MiB termina e reporta o total. Compare com um `zcat bomba.gz > /dev/null` ingênuo: o zcat materializa tudo — a diferença é que ele impõe um limite *antes* de saber o tamanho real.

## 6. Leitura extra (estado da arte)

- Fifield, [*A better zip bomb*](https://www.bamsoftware.com/hacks/zipbomb/) — como sobrepor cabeçalhos locais faz o mesmo fluxo comprimido contar como vários arquivos (281.000:1 **sem** recursão)
- Russ Cox, [*Zip Files All The Way Down*](https://research.swtch.com/zip) — zips quine: a extração produz o próprio zip, para sempre

**Pergunta pra fechar:** por que o artigo do Fifield é "melhor" que o aninhado? Dica: scanners defendem contra recursão (limitam profundidade), mas um fluxo único com cabeçalhos sobrepostos passa por qualquer limite de profundidade.
