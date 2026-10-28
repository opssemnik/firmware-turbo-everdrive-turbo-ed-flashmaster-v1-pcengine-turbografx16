# Turbo EverDrive OS — Retrogamer POA (PT-BR)

Mod do sistema operacional (OS) do **Turbo EverDrive v1** da Krikzz para PC Engine / TurboGrafx-16.
Base: OS v4 original, de https://krikzz.com/pub/support/turbo-everdrive/v1/os/v4/.

**Versão atual: PT-BR v4** · Mod: **Retrogamer POA**, por **Antonio & The Nobre**

![Splash](docs/screenshots/splash.png)

## O que o mod traz

| | |
|---|---|
| ![Menu](docs/screenshots/menu.png) | **Interface em português** com acentos de verdade: a fonte ganhou á à â ã é ê í ó ô õ ú ç, maiúsculas, ü º ª. **Banner Retrogamer POA** no topo e **linha de ajuda** com os botões. |
| ![Capa](docs/screenshots/capa.png) | **Capa do jogo** ao parar o cursor sobre ele. São 2.372 nomes de arquivo com capa, entre PC Engine e SuperGrafx, incluindo hacks, traduções e "Sounds". |
| ![Sobre](docs/screenshots/sobre.png) | **Tela Sobre** com a versão do mod e os créditos. |
| ![Carregando](docs/screenshots/carregando.png) | Mensagens de carregamento e atualização traduzidas. |

**8 temas de cor com SELECT**, salvos no cartão SD: Original, Fósforo Verde, Âmbar, Azul, Brasil, Synthwave, Turbo e Papel.

![Temas](docs/screenshots/temas.png)

Ao ligar aparece uma **splash screen** por 3 segundos. Qualquer botão pula.

## Botões

| Botão | Função |
|---|---|
| **II** | abre a pasta |
| **RUN** | inicia o jogo |
| **I** | volta para a raiz; na raiz, abre/fecha a tela Sobre |
| **SELECT** | troca o tema (fica salvo) |
| ↑ ↓ ← → | navega; ← → trocam de página |

## Instalação

1. Baixe o `.zip` da [última release](../../releases/latest).
2. **Faça backup do seu cartão SD** (veja [Segurança](#segurança)).
3. Copie `TOS.PCE` e `RGPOA.DAT` para a **raiz** do SD.
4. Ligue o console, selecione `TOS.PCE` na lista e aperte **RUN**. Aparece "Atualizando o SO...": não desligue até terminar.

O `RGPOA.DAT` aparece na lista da raiz. Deixe ele lá: é dele que saem as capas e o tema salvo. Sem ele o mod funciona, só que sem capas e sem salvar o tema.

### Voltar ao OS original
Baixe o `tos.pce` original da Krikzz (link acima), copie para a raiz do SD como `TOS.PCE`, selecione e aperte **RUN**.

## Segurança

O OS da Krikzz grava o firmware na flash do cartucho quando você roda o `TOS.PCE`. O mod não muda esse processo.

Sobre o cartão SD, o mod **só grava um setor**: o setor 0 do `RGPOA.DAT`, e só o byte do tema. Antes de cada gravação ele:
- relê esse setor e confere a assinatura de 16 bytes `RGPOA-DAT-v1`;
- recusa qualquer setor fora da área de dados do FAT32.

FAT e diretórios nunca são gravados. Mesmo assim, faça backup do SD antes de instalar uma versão nova.

## Capas: como gerar o `RGPOA.DAT` para os seus jogos

A release traz um `RGPOA.DAT` pronto para o acervo `GAMES_PCENGINE` e para a coleção do autor. Para gerar um com os seus jogos:

```
pip install pillow
python tools/scrape.py  <pasta_dos_roms> [outra_pasta ...]   # casa ROMs com capas e baixa as que faltam
python tools/artpack.py                                      # gera out/RGPOA.DAT
```

O scraper casa primeiro pelo CRC32 da ROM (base No-Intro do libretro-database) e, se não achar, pelo título aproximado. Isso cobre hacks, traduções, bad dumps e "Sounds". As capas vêm do [libretro-thumbnails](https://github.com/libretro-thumbnails) (PC Engine e SuperGrafx), e as já baixadas estão em `art_cache/img/`.

O cartucho identifica o jogo pelo **nome do arquivo**, então o mesmo jogo em pastas diferentes mostra a mesma capa. Se renomear ou adicionar jogos, gere o `.dat` de novo. Trocar o `RGPOA.DAT` volta o tema para o Original.

## Compilar o firmware

Requer Python 3 e Pillow. O OS original é baixado automaticamente do site da Krikzz e conferido pelo MD5.

```
python tools/build.py        # -> out/TOS.PCE
python tools/test_mod.py     # emulador headless: splash, menu, sobre, temas, carregamento
python tools/test_v3.py      # capas + salvamento do tema (precisa de uma imagem de SD em sdcard_dump)
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
