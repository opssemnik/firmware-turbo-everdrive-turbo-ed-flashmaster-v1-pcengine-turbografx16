# Turbo EverDrive OS — Retrogamer POA (PT-BR)

Mod do sistema operacional (OS) do **Turbo EverDrive v1** da Krikzz para PC Engine / TurboGrafx-16.
Base: OS v4 original, de https://krikzz.com/pub/support/turbo-everdrive/v1/os/v4/.

**Versão atual: PT-BR v17** · Mod: **Retrogamer POA**, por **Antonio & The Nobre**

![Splash](docs/screenshots/splash.png)

## O que o mod traz

| | |
|---|---|
| ![Menu](docs/screenshots/menu.png) | **Interface em português** com acentos de verdade: a fonte ganhou á à â ã é ê í ó ô õ ú ç, maiúsculas, ü º ª. **Banner Retrogamer POA** no topo e **linha de ajuda** com os botões. |
| ![Capa](docs/screenshots/capa.png) | **Capa do jogo** ao parar o cursor sobre ele. São 2.372 nomes de arquivo com capa, entre PC Engine e SuperGrafx, incluindo hacks, traduções e "Sounds". |
| ![Ações](docs/screenshots/acoes.png) | **Tela do jogo** ao apertar RUN ou II: capa, **Carregar**, **Favoritar / Remover favorito** e **Voltar**. **← / →** passam para o jogo anterior / seguinte da pasta. Os jogos carregados entram na lista de **recentes**. |
| ![Menu](docs/screenshots/menu_principal.png) | **Menu** (botão I na raiz): **Favoritos**, **Recentes**, **Buscar** e **Sobre**. |
| ![Favoritos](docs/screenshots/favoritos.png) | **Listas de favoritos e recentes**: escolher um jogo leva direto até ele (o OS entra na pasta, o cursor vai até o jogo e a tela do jogo abre). Favoritos e recentes ficam salvos no `RGPOA.DAT`. |
| ![Busca](docs/screenshots/busca_teclado.png) | **Busca em todo o cartão**: digite parte do nome no teclado da tela (direcional + II, I apaga, RUN busca). O mod percorre todas as pastas do SD, sem gravar nada. |
| ![Resultados](docs/screenshots/busca_resultados.png) | **Resultados** (até 64, ignorando maiúsculas/minúsculas): escolha um e o console vai até o jogo, como nos favoritos. |
| ![Sobre](docs/screenshots/sobre.png) | **Tela Sobre** com a versão do mod, a data e hora de compilação e os créditos. |
| ![Carregando](docs/screenshots/carregando.png) | **Barra de progresso** ao carregar o jogo, além das mensagens de carregamento e atualização traduzidas. |

**Temas com SELECT** (toque e solte), salvos no cartão SD. Cada tema tem suas cores e pode ter **banner** e **splash** próprios; a barra de progresso também segue as cores do tema. A release traz 10, nesta ordem: Original (Retrogamer POA), **Retrochimp Games** (grupo do Arnaldo), **Maddrugamers** (canal no YouTube) e as variações Retrogamer POA Fósforo Verde, Âmbar, Azul, Brasil, Synthwave, Turbo e Papel.

![Temas](docs/screenshots/temas.png)

![Banners](docs/screenshots/banners.png)

![Splashes](docs/screenshots/splashes.png)

### Criar seus temas e banners
Os temas ficam no `RGPOA.DAT`, então dá para criar, editar ou remover sem regravar o firmware:

1. Edite `themes/themes.json`. Cada tema tem um nome, as cores em `[R, G, B]` (0 a 7) e, opcionalmente, `"banner": "arquivo.png"`. A ordem no arquivo é a ordem no SELECT (máximo 32 temas).
2. Banners: PNG de **256×16 pixels** com até **15 cores**, em `themes/banners/`. Splash: PNG de **256×224** com até **15 cores** (e até 512 blocos 8×8 diferentes), em `themes/splashes/`, campo `"splash"`. As cores são convertidas para a paleta do PC Engine (8 níveis por canal). Os exemplos são gerados por `python tools/theme_art.py` e `python tools/splash_art.py`.
3. Gere o `.dat` (`python tools/artpack.py --keep <RGPOA.DAT do SD>` mantém tema, favoritos e recentes) e copie para a raiz do SD.

Sem `RGPOA.DAT` (ou com um `.dat` sem temas), o firmware usa os 8 temas de fábrica com o banner padrão.

Ao ligar aparece uma **splash screen** por 2 segundos. Qualquer botão pula.

## Botões

| Botão | Função |
|---|---|
| **II** | abre a pasta; num jogo, abre a tela do jogo |
| **RUN** | abre a tela do jogo (Carregar já vem selecionado: RUN de novo carrega) |
| **I** | sobe uma pasta; na raiz, abre o **menu** (Favoritos / Recentes / Sobre) |
| **SELECT** (toque) | troca o tema (fica salvo) |
| ↑ ↓ ← → | navega; ← → trocam de página |

## Instalação

1. Baixe o `.zip` da [última release](../../releases/latest).
2. **Faça backup do seu cartão SD** (veja [Segurança](#segurança)).
3. Copie `TOS.PCE` e `RGPOA.DAT` para a **raiz** do SD.
4. Ligue o console, selecione `TOS.PCE` na lista e aperte **RUN**. Aparece "Atualizando o SO...": não desligue até terminar.

O `RGPOA.DAT` aparece na lista da raiz. Deixe ele lá: dele saem as capas, o tema salvo, os favoritos e os recentes. Sem ele o mod funciona, só que sem esses recursos.

A v8 usa o `RGPOA.DAT` no formato v3. Um `.dat` de versão anterior **precisa ser trocado** pelo da release: o antigo é ignorado (sem capas). Os favoritos e recentes de testes da v7 não são aproveitados.

### Limites
- O OS original da Krikzz mostra **no máximo 224 itens por pasta**. Pastas com mais arquivos têm jogos que nunca aparecem no console; vale dividi-las em subpastas. A busca encontra esses jogos, mas não consegue levar o cursor até eles.
- A busca lê todas as pastas do cartão a cada pesquisa: ~1,5 s para 1.000 arquivos, uns 8–10 s para 6.000.
- Depois de ir a um jogo pelos favoritos/recentes, o botão I volta para a raiz (e não para a pasta-mãe).
- Até 56 favoritos e 14 recentes.

### Voltar ao OS original
Baixe o `tos.pce` original da Krikzz (link acima), copie para a raiz do SD como `TOS.PCE`, selecione e aperte **RUN**.

## Segurança

O OS da Krikzz grava o firmware na flash do cartucho quando você roda o `TOS.PCE`. O mod não muda esse processo.

Sobre o cartão SD, o mod **só grava dentro do `RGPOA.DAT`**, e só nos 11 primeiros setores dele: o setor 0 (tema), 1–8 (favoritos) e 9–10 (recentes). Antes de cada gravação ele:
- relê o setor e confere a assinatura dele (`RGPOA-DAT-v2` no setor 0, `RGPOA-SLOT` + tipo + número nos outros). Se o arquivo estiver fragmentado no cartão, a assinatura não bate e nada é gravado;
- recusa qualquer setor fora desses 11 e fora da área de dados do FAT32.

FAT e diretórios nunca são gravados. Mesmo assim, faça backup do SD antes de instalar uma versão nova.

## Capas: como gerar o `RGPOA.DAT` para os seus jogos

A release traz um `RGPOA.DAT` pronto para o acervo `GAMES_PCENGINE` e para a coleção do autor. Para gerar um com os seus jogos:

```
pip install pillow
python tools/scrape.py  <pasta_dos_roms> [outra_pasta ...]   # casa ROMs com capas e baixa as que faltam
python tools/artpack.py                                      # gera out/RGPOA.DAT
python tools/artpack.py --keep E:\RGPOA.DAT                   # idem, mantendo tema, favoritos e recentes do .dat atual
```

O scraper casa primeiro pelo CRC32 da ROM (base No-Intro do libretro-database) e, se não achar, pelo título aproximado. Isso cobre hacks, traduções, bad dumps e "Sounds". As capas vêm do [libretro-thumbnails](https://github.com/libretro-thumbnails) (PC Engine e SuperGrafx), e as já baixadas estão em `art_cache/img/`.

O cartucho identifica o jogo pelo **nome do arquivo**, então o mesmo jogo em pastas diferentes mostra a mesma capa. Se renomear ou adicionar jogos, gere o `.dat` de novo. Use `--keep` com o `.dat` que está no SD para não perder tema, favoritos e recentes.

## Compilar o firmware

Requer Python 3 e Pillow. O OS original é baixado automaticamente do site da Krikzz e conferido pelo MD5.

```
python tools/build.py        # -> out/TOS.PCE
python tools/run_tests.py    # todos os testes em paralelo (~2 min); ou: run_tests.py v11 v14
python tools/test_mod.py     # emulador headless: splash, menu, sobre, temas, carregamento
python tools/test_v3.py      # capas + salvamento do tema (precisa de uma imagem de SD em sdcard_dump)
python tools/test_v7.py      # tela do jogo, favoritos e recentes
python tools/test_v8.py      # menu, listas e "ir ao jogo"
python tools/test_v9.py      # II num jogo, SELECT (tema), splash
python tools/test_v10.py     # temas e banners do RGPOA.DAT
python tools/test_v11.py     # busca global
python tools/test_v12.py     # barra de progresso (gravações na flash idênticas às da versão anterior)
python tools/test_v14.py     # splash por tema e barra nas cores do tema
python tools/test_v15.py     # ← / → na tela do jogo
python tools/screenshots.py  # gera docs/screenshots/
```

Para lançar uma versão nova, aumente `MOD_VERSION` em `tools/build.py`.

Detalhes técnicos (engenharia reversa, mapa de memória, protocolo do SD, formato do `RGPOA.DAT`) estão em [docs/TECNICO.md](docs/TECNICO.md). O histórico está em [CHANGELOG.md](CHANGELOG.md).

## Créditos e avisos

- Mod: **Retrogamer POA**, por Antonio & The Nobre.
- OS original, hardware e firmware do Turbo EverDrive: **Krikzz** (krikzz.com). Este projeto não é oficial.
- Capas: projeto [libretro-thumbnails](https://github.com/libretro-thumbnails). As artes pertencem aos seus respectivos donos e estão aqui sem fins lucrativos.
- Nenhuma ROM é distribuída aqui.
- O código das ferramentas (`tools/`) está sob licença MIT ([LICENSE](LICENSE)).
