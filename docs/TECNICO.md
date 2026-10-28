# Documentação técnica

Notas da engenharia reversa do OS v4 do Turbo EverDrive v1 (`tos.pce`, 128 KB, MD5
`38241a96caa1573f9caf20a2b52dd3e8`) e de como o mod foi construído.

## Visão geral do OS original

- ROM de 16 bancos de 8 KB. O vetor de reset fica em `$E100` (banco 0).
- Escrito em C com o compilador **HuC**: pilha C em `$00/$01`, pilha de argumentos em `$3F24+` indexada por `$02`, biblioteca HuC no banco 0.
- Mapeamento durante o menu (MPR0..7): `FF F8 03 00 0C 0A 00 00`.
  - Banco 3 (strings) fica em `$4000`.
  - Banco 12 (trampolins) fica em `$8000`.
  - O código C usa bancos 5–12 em `$A000`.
- Textos: todos ficam numa tabela no banco 3 (`$4000–$4109`). `put_string(str, x, y)` está em `$EFD8`.
- Fonte 1bpp em ROM (banco 1, offset 0, 96 glifos). É carregada por `$E495`/`$A92E`, chamado em `$E1AE` (boot) e `$EE5C` (`load_default_font`).
  - Tile = caractere − `$20` + `$80`.
  - Cor 1 = glifo, cor 2 = fundo da célula.
- Paletas de texto, definidas em `main` (banco 11, `$AB8F`):
  - pal 0: cursor e telas de texto (a cor 2 dela é o fundo da tela);
  - pal 1: arquivos;
  - pal 2: pastas;
  - pal 3: barras de cima e de baixo. A cor `$32` (fundo da barra) é verde se `regs[7]&15 == 0` e cinza nos outros casos.
- Laço de espera do navegador: banco 10, `$A4D1`. Lê `joy(0)` (`$F8E9`) a cada frame.
  - `$222D` = botões recém-apertados (joytrg).
  - `$2228` = botões segurados.
- Botões: II abre a pasta, RUN roda o jogo, I volta para a raiz (na raiz abre a tela Sobre).
  - SELECT sozinho não fazia nada; o OS só o lê como modificador ao lançar um jogo.

### Registradores do cartucho
Ficam nos 16 primeiros bytes do banco 0 (`$E000–$E00F` com MPR7 = 0). O código C usa um ponteiro em `$2983` com valor `$E000`.

| reg | uso |
|---|---|
| 0 (e 1, espelho) | dado SPI: escrita = transfere byte; leitura = último byte. No modo auto-leitura, a leitura também dispara a próxima transferência (o OS lê setores com `TAI $E000`) |
| 4 | status: bit 0 = SPI pronto, bit 1 = flash pronta, bit 3 = dado SD→flash |
| 7 | info do firmware (nibble baixo) |
| 8 | controle: bit 0 = CS (1 = desseleciona), bit 2 = auto-leitura |
| 3, 5, 6, 10 | DMA SD→flash e mapeamento, usados ao carregar jogos e atualizar o OS |

Os bancos `$40+` são a flash do cartucho, com comandos AMD (`$6AAA`/`$6555`). O OS se regrava ao rodar um arquivo chamado `TOS.PCE` (comparado com "TOS     PCE"), e só nesse momento.

### Cartão SD
- SPI puro. Para ler um setor o OS faz:
  1. CMD12 (fecha o stream anterior);
  2. CMD18 do setor;
  3. lê **um** bloco;
  4. deixa o stream aberto.
- Flag do tipo de cartão: `$2985` bit 0 (1 = SDHC, endereçamento por bloco).
- Estrutura FAT do OS (globais estáveis):

| endereço | conteúdo |
|---|---|
| `$30A3` | LBA da partição |
| `$30A7` | setores por FAT |
| `$30B1` | LBA da FAT |
| `$30B5` | LBA do cluster 2 (base de dados) |
| `$30B9` | bytes por cluster |
| `$30BD` | cluster da raiz |
| `$30C1` | cluster da pasta atual |

- Nomes longos (LFN): o OS mostra o **byte baixo** de cada unidade UTF-16 (时 U+65F6 → `$F6`). A barra inferior mostra até 60 caracteres (2 linhas de 30, BAT linhas 24–25).

### RAM, VRAM e VCE
- A RAM (`$2000–$3FFF`) é usada quase inteira em pastas grandes, por causa da lista de arquivos.
- `$2020–$203F` só é tocado pelas rotinas de gravação da flash, que terminam em reset. O mod usa essa faixa como estado.
- VRAM:

| faixa | uso |
|---|---|
| `$0000–$07FF` | BAT 64×32 |
| `$0800–$0FFF` | fonte |
| `$7F00` | SATB, com DMA automático a cada frame (DCR = `$10`) |

  O resto da VRAM fica livre.
- Registrador VDC selecionado: o OS guarda uma sombra em `$F7` e o IRQ de vsync a restaura. Qualquer acesso ao VDC fora do OS precisa manter isso coerente.
- Scroll: o IRQ de vsync (`$E27B`) copia `$2210/$2211` (regiões de scroll do HuC) para o BYR a cada frame.

## O que o mod muda

| Mudança | Onde |
|---|---|
| Fonte de 128 glifos (96 originais + 32 acentuados), carregada como 128 caracteres | banco 13 `$0000`; bytes do carregador em `$E1AE` e `$EE5C` |
| Strings traduzidas (realocadas e recentralizadas) | banco 3 `$4110+` |
| Gancho do laço do navegador (`jsr joy` → `joyhook`): ajuda, capas, SELECT | banco 0 `$FF63`; chamada em banco 10 `$A567` |
| Gancho do `cls()` (`$EDA9` → `cls_new`): redesenha o banner e esconde a capa | banco 0 |
| BG rolado 16 px: o IRQ grava BYR = 240 constante (`$E27D`); o banner fica nas linhas 30–31 do BAT | banco 0 |
| Splash: gancho no `set_font_pal(0)` de `main` (`$AD54`) | banco 11 `$B6xx` → banco 13 |
| Tela Sobre: versão em texto (no lugar de `put_number(4)`) + créditos | banco 11 `$B600` |
| Tela do jogo: o início do caminho de carregamento (`$A96A`, RUN num arquivo) vira `jmp $BF63` | banco 10 `$BF63` → banco 0 `act_far` → banco 13 `action` |
| Temas, banner, ajuda, splash, driver SD, capas | banco 13 `$C400+` (`tools/cart_asm.py`), chamado via MPR6 |
| Tiles e mapa da splash | bancos 14 e 15 |

O código do banco 13 roda com interrupções desligadas sempre que mexe no VDC ou no SD. No fim, devolve ao VDC o registrador da sombra `$F7`.

### Temas
- O índice do tema fica na **CRAM `$1FF`** (cor 15 da paleta de sprite 15): bits 0–3 = tema, bit 8 = inicializado.
- A **CRAM `$1FE`** guarda a cor de barra que o OS escolheu no boot, para o tema Original ficar idêntico ao OS de fábrica.
- Cada tema define 9 cores: backdrop, fundo, cursor, arquivo, pasta, texto e fundo da barra.

### Capas
1. No primeiro frame ocioso, o mod lê a raiz (primeiro cluster) usando a estrutura FAT do OS e procura a entrada 8.3 `RGPOA   DAT`.
2. Confere a assinatura do setor 0 e aplica o tema salvo.
3. A cada frame calcula um hash do nome mostrado na barra inferior, lendo os tiles direto do BAT. São considerados só ASCII imprimível, ignorando `.`, espaço e caixa: `A += c; B += A`, ambos de 16 bits.
4. Se o hash ficar estável por 12 frames, lê o bucket `(A ^ B) & máscara` do índice, acha o setor da capa, carrega a paleta na CRAM `$100` e os 12 setores de padrões na VRAM `$4000`.
5. Liga 6 sprites de 32×64 (painel de 96×128 em x=152, y=40) escrevendo na SATB.

### Tela do jogo, favoritos e recentes
- Em `$A932` o OS testa o RUN; se o item não é pasta, vai para `$A96A`, que abre o arquivo (nome em `$3A64`) e decide entre atualizar o OS (`TOS.PCE`) e carregar o jogo.
- O gancho em `$A96A` chama a tela do jogo, que retorna:
  - **Carregar:** registra nos recentes, refaz as duas instruções substituídas (`lda <$00 / sec`) e segue em `$A96D`.
  - **Voltar:** grava `$FFFF` em `$3B8E-$3B91` (a mesma coisa que o OS faz antes da tela Sobre, para forçar o redesenho completo) e salta para `$B2BF`, o fim do tratamento de teclas. A pilha C fica no mesmo ponto (`$3FE8`, conferido no emulador).
- Estado da tela em `$2040-$2056`. Essa faixa só é gravada pela rotina de carregamento do jogo, que roda depois e termina em reset.
- Cada favorito ou recente guarda o cluster da pasta (`$30C1`), um número de sequência e os 56 primeiros caracteres do nome. Assim a próxima etapa consegue ir até o jogo.
- Recentes: quando a lista está cheia, o mais antigo (menor sequência) é substituído. O `TOS.PCE` não é registrado.

### Menu, listas e "ir ao jogo"
- A chamada da tela Sobre (`$B0E9`, I na raiz) vira `jsr hub10b` (banco 10) → `hub_far` (banco 0) → `hub` (banco 13). "Sobre" no menu chama a tela original (`jsr $8144`).
- Abrir arquivo do OS: `open(índice, $3A64 nome, $3B64, $3B68)` via `$810E` (banco 9 `$A000`; argumentos na pilha C e o último em X:A; a função desempilha). Preenche o nome, o cluster inicial (`$3B64`) e o tamanho (`$3B68`). O índice do cursor é a local `sp+$0E` do navegador.
- A tela do jogo chama `open` para saber o cluster do arquivo selecionado; favoritos e recentes guardam cluster da pasta + cluster do arquivo.
- Ordem de exibição: o OS monta em `$397D` um vetor de bytes "posição na lista → ordinal da entrada". O ordinal conta as entradas da pasta ignorando apagadas (`$E5`), `.`/`..`, partes de nome longo (attr `$0F`) e rótulo de volume. **Máximo de 224 itens por pasta.**
- Ir ao jogo:
  1. `$3B96` = cluster da pasta; `$30C1` = raiz; pilha de caminho (`$3C92`, profundidade `$3D12`) zerada.
  2. A local de tecla (`sp+$0D`) vira II e o byte `sp+$08` vira 4 (o OS passa `$3B92 + esse byte` para `enterdir`, `$80EA`).
  3. Salto para `$AF69`: o próprio OS entra na pasta e redesenha.
  4. No primeiro frame ocioso, o mod acha o ordinal do arquivo varrendo a pasta (seguindo a FAT) e a posição dele em `$397D`, e confirma com `open(i)`.
  5. O gancho do `joy(0)` devolve RIGHT × (i/20), DOWN × (i%20) e RUN, o que abre a tela do jogo.

### II num jogo e pular para letra
- O gancho do `joy(0)` passa a devolver o que o mod decidir: 0 = botões reais, `$FF` = nada (o SELECT nunca chega ao OS), outro valor = tecla injetada.
- II sozinho: o mod chama `open(índice)`. Se o tamanho (`$3B68`) for diferente de 0 é arquivo, e o mod injeta RUN, que abre a tela do jogo. Pastas têm tamanho 0 e seguem o II normal.
- SELECT: o tema troca quando o botão é solto sem nenhuma direção apertada. SELECT + direção pula de letra.
- Pular letra: a ordenação do OS ignora maiúsculas/minúsculas (pastas primeiro, depois arquivos). O total de itens está em `$3A62`.
  1. Uma busca binária com `open()` acha a fronteira pastas/arquivos.
  2. Outra busca acha o início da próxima letra (ou da anterior), dentro do mesmo grupo.
  3. O cursor chega lá pela mesma rotina de busca usada pelos favoritos, que a cada frame compara a página e o índice atuais (local `sp+$10` dentro da chamada do `joy`) com o alvo e injeta ←/→/↑/↓.
- Dados do banner, ícones, linha de ajuda e paletas ficam no banco 15 (`$1000+`), lidos via MPR3 (`$7000+`).

### Temas e banners do `RGPOA.DAT`
- Cabeçalho: byte 19 = número de temas, bytes 20–23 = setor da tabela (relativo ao início do arquivo). O firmware anterior ignora esses bytes.
- Tabela: 32 bytes por tema = 9 cores (u16, ordem de `SLOTS`), setor do banner (u32, 0 = banner padrão) e nome (10 bytes).
- Banner: 5 setores, com a paleta (16 cores, vai para a paleta 6, CRAM `$60`) e 64 tiles em sequência, enviados para a VRAM `$1400` (tiles `$140-$17F`). O mapa não precisa ser guardado: a linha 30 do BAT recebe `$6140+i` e a linha 31 `$6160+i`.
- Os ícones da linha de ajuda continuam na paleta 4 e nos tiles `$100+`, que o banner customizado não toca.
- `theme_set`: se o `.dat` tem temas, lê as cores e o banner do cartão (até 6 setores) e redesenha as linhas do banner. A cada `cls()`, `banner_rows` escreve o banner ativo.

### Salvamento do tema
- Toda gravação passa por `write_scr` (CMD24). Ela só aceita os setores 0–10 do `RGPOA.DAT` e recusa o arquivo se ele estiver antes de `$30B5`.
- Antes de gravar, quem chama relê o setor e confere a assinatura dele.
- O tema altera só o byte 16 do setor 0.
- Depois relê o setor, para deixar um stream de leitura aberto como o OS espera.

## Formato do `RGPOA.DAT`

Setores de 512 bytes, contados a partir do início do arquivo.

| setor | conteúdo |
|---|---|
| 0 | `RGPOA-DAT-v3` + 4 zeros (16 bytes), tema (byte 16), nº de buckets (byte 17, potência de 2), versão (byte 18) |
| 1 .. 8 | favoritos; 9 .. 10 recentes: `RGPOA-SLOT`, tipo (`F`/`R`), nº do setor, 4 zeros; depois 7 entradas de 64 bytes: `cluster da pasta u32` (0 = vazia), `seq u16`, `cluster do arquivo u32`, `nome[54]` |
| 11 .. 10+nb | buckets: 64 entradas de 8 bytes `hashA u16, hashB u16, setor u32` (setor 0 = fim) |
| resto | capas, 13 setores cada: `"RGA1"`, 4 bytes reservados, 16 cores (u16 no formato do VCE: `GGGRRRBBB`), depois 6.144 bytes de padrões de sprite (6 sprites 32×64, células 16×16 com 4 planos) |

## Ferramentas

| arquivo | função |
|---|---|
| `tools/build.py` | gera `out/TOS.PCE` a partir do original (baixa e confere o MD5); cada patch confere os bytes originais |
| `tools/asm.py`, `tools/huc6280.py` | assembler e disassembler HuC6280 próprios |
| `tools/cart_asm.py` | código do banco 13 |
| `tools/art.py` | banner, ícones dos botões, linha de ajuda, splash (arte original) |
| `tools/scrape.py`, `tools/artconv.py`, `tools/artpack.py` | scraper, conversão para 96×128/15 cores, gerador do `RGPOA.DAT` |
| `tools/machine.py`, `tools/cpu.py` | emulador headless (HuC6280, VDC/VCE, sprites, joypad, SD em SPI sobre uma imagem de cartão; gravações vão para um overlay em memória) |
| `tools/fatinject.py` | coloca um arquivo na raiz do cartão emulado (só em memória) |
| `tools/test_mod.py`, `tools/test_v3.py`, `tools/screenshots.py` | testes e capturas |
