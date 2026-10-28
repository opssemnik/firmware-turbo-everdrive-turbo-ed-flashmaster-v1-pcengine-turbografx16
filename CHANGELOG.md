# Histórico

## PT-BR v13
- Tela Sobre: **Data/Hora Compil.** mostram quando o firmware foi gerado (antes aparecia "31.15.2235", porque o OS original não preenche esses bytes).
- Removida a linha "SELECT no menu: muda o tema" da tela Sobre.

## PT-BR v12
- **Barra de progresso** no "Carregando...": enche conforme cada bloco de 8 KB do jogo é gravado na flash.
- `RGPOA.DAT` igual ao da v10/v11.

## PT-BR v11
- **Busca global** (menu > Buscar): teclado na tela, varredura de todas as pastas do cartão (só leitura), até 64 resultados; escolher um leva ao jogo.
- Removido o "pular para letra" (SELECT + direção). SELECT volta a ser só o tema.
- `RGPOA.DAT` igual ao da v10.

## PT-BR v10
- **Temas e banners no `RGPOA.DAT`**: cada tema tem cores e, opcionalmente, um banner próprio (PNG 256×16, até 15 cores). Dá para criar e editar temas sem regravar o firmware (`themes/themes.json`).
- 10 temas na release, todos com banner próprio exceto o Original. Inclui **Retrochimp Games** (grupo do Arnaldo) e **Maddrugamers**.
- Compatível com o `RGPOA.DAT` da v8/v9 (sem temas, valem os 8 de fábrica) e vice-versa.

## PT-BR v9
- **II num jogo** abre a tela do jogo (antes só o RUN abria).
- **Pular para uma letra:** SELECT + →/↓ (próxima) e SELECT + ←/↑ (anterior).
- O tema agora troca ao **soltar** o SELECT (para não conflitar com o pulo de letra).
- Splash de 1,5 segundo.
- Banner, ícones e paletas movidos do banco 13 para o banco 15 (espaço para novas funções).
- `RGPOA.DAT` continua no formato v3: favoritos, recentes e tema são mantidos.

## PT-BR v8
- **Menu** no botão I da raiz: Favoritos, Recentes e Sobre.
- **Listas de favoritos e recentes** (recentes do mais novo para o mais antigo). Escolher um jogo faz o OS entrar na pasta dele, leva o cursor até o jogo e abre a tela do jogo.
- Favoritos e recentes guardam também o cluster do arquivo; `RGPOA.DAT` passa para o formato v3 (é preciso trocar o arquivo).

## PT-BR v7
- **Tela do jogo** ao apertar RUN num arquivo: nome, capa e as opções Carregar, Favoritar / Remover favorito e Voltar.
- Favoritos (até 56) e recentes (últimos 14 jogos carregados) salvos no `RGPOA.DAT`.
- `RGPOA.DAT` passa para o formato v2 (setores de favoritos e recentes); é preciso trocar o arquivo.
- `artpack.py --keep` gera um `.dat` novo mantendo tema, favoritos e recentes do atual.

## PT-BR v6
- Splash de 2 segundos (antes 3).

## PT-BR v5
- Ícones dos botões na linha de ajuda com contorno escuro: agora aparecem também no tema Papel (fundo claro).

## PT-BR v4
- Splash de 3 segundos (antes 4).
- `RGPOA.DAT` agora cobre o acervo `GAMES_PCENGINE` e jogos de SuperGrafx (`.sgx`): 2.372 nomes com capa.
- O build baixa o OS original da Krikzz automaticamente.

## PT-BR v3
- Capa do jogo selecionado: painel de 96×128 feito com sprites. Os dados vêm do `RGPOA.DAT` na raiz do SD.
- O tema escolhido com SELECT fica salvo no `RGPOA.DAT` e volta ao ligar.
- Ajuda: "I Voltar" no lugar de "I Info".

## PT-BR v2
- Splash screen no boot.
- Banner Retrogamer POA no topo de todas as telas.
- Linha de ajuda com ícones dos botões.

## PT-BR v1
- Tradução para português, com fonte acentuada.
- 8 temas de cor com SELECT.
- Créditos e versão do mod na tela Sobre.
