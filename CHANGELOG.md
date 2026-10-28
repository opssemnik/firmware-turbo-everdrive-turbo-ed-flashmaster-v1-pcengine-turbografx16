# Histórico

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
