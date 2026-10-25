# Atualização: prévia do início para Android

O arquivo original foi recuperado e teve seu hash confirmado. O projeto `android-current/` combina regras C++, diálogos Rust e apresentação Java/libGDX. A integração atual acrescenta menu, vídeo original de abertura com áudio e legendas, cena da casa e a primeira visita do vizinho. O trecho seguinte de conversa dentro da casa também foi recuperado. Consulte `android-current/README.md` e seus relatórios para o resultado efetivamente compilado e verificado. O objetivo continua o jogo completo em Android; a campanha completa ainda não está integrada.

# Reconstrução nativa para Android — No, I'm not a Human

Este é um trabalho de recuperação e reconstrução a partir do ZIP fornecido pelo usuário. O código novo em Rust e a interface Android são separados dos executáveis de Windows. Este conjunto ainda não equivale ao jogo completo.

## Núcleo C++ recuperado

A implementação atual está em `native-game/`, incluindo inventário, ocupantes, visitas, cômodos, telefone, energia, emoções e progressão. Os 73 objetos de personagens e suas 275 emoções voltaram a ser validados; a integração do roteiro com estado C++ também passou. Consulte `native-game/RECUPERACAO.md` e `native-game/VALIDATION.json` para distinguir o que está salvo, os testes atuais e os limites de integração. Ainda não é um APK com a campanha completa.

## APK experimental da etapa anterior

O aplicativo `NINAH — Diálogos` contém conversas e opções do grafo original, texto em português do Brasil e inglês, uma galeria de arte recuperada e um catálogo de textos. A conversa do vizinho do segundo dia permite percorrer as três perguntas e encerrar a ligação. A escolha de outros trechos usa os pontos de entrada originais, sem criar ligações artificiais entre cenas.

O APK inclui bibliotecas novas para ARM64 e x86-64. Foi compilado, assinado para teste e inspecionado, mas não foi executado em um celular ou emulador Android neste ambiente. Ele não usa Wine nem os executáveis ou DLLs do pacote de Windows. O manifesto não solicita permissões de internet, armazenamento, câmera ou microfone.

Esta versão não permite jogar a campanha completa: os comandos específicos do jogo ainda são apresentados como referências, e funções de estado não implementadas interrompem o trecho com uma indicação de limite. O modelo separado de energia e personagens em `game-state/` já contém algumas regras verificadas, mas ainda não está ligado ao aplicativo.

## O que foi recuperado

- Programa Yarn original: 3.255 nós, 56.585 instruções e 276 valores iniciais. A decodificação foi conferida por dois caminhos independentes, incluindo os campos omitidos que usam valores padrão do Protobuf.
- Tabelas de localização em 18 idiomas, incluindo português do Brasil; 610.124 registros no total. A ordem das linhas nas tabelas não determina, por si só, a ordem dos diálogos.
- Imagens e amostras de áudio exportadas dos recursos originais. Alguns sprites precisam de verificação adicional da decodificação de textura.
- Estruturas e métodos recuperados da compilação IL2CPP para análise. A saída do descompilador contém lacunas e substituições; ela não é equivalente ao projeto original pronto para recompilar.
- Inventário com hashes e análise estática dos arquivos fornecidos.
- Configuração original de dias e energia, lista inicial de registros de personagens, poses, tempos de chegada e parâmetros de geração. Os dados de personagens têm campos ainda não interpretados, preservados nos arquivos brutos e identificados no relatório específico.

## O que o código novo faz

A implementação em Rust interpreta instruções de diálogo e expõe eventos para a interface Android. Comandos específicos do jogo são tratados como dados e eventos: eles nunca são enviados a um shell nem usados para carregar DLLs. As funcionalidades efetivamente integradas e verificadas são registradas no relatório de validação do pacote.

O assembly de Windows foi usado como material de análise de métodos. Ele não pode ser executado diretamente como código ARM64 de Android. A reconstrução usa código novo onde o comportamento necessário foi estabelecido.

## O que ainda falta para ser o jogo completo

A interface Android atual permite testar partes integradas do núcleo por toque. O áudio de abertura está ligado ao vídeo; o restante do áudio, fluxo completo da campanha, persistência após fechar o aplicativo e comandos restantes ainda precisam ser concluídos e comparados com o comportamento original. Recuperar o grafo Yarn não recupera automaticamente esses sistemas. Algumas regras e configurações já foram recuperadas para essa próxima etapa, mas não substituem a integração completa.

## Segurança e origem

Nenhum executável, DLL, instalador ou processo do jogo original foi executado durante esta análise. Os relatórios em `security/` descrevem as limitações da auditoria. A DLL modificada do crack não integra o código novo. O pacote original não foi certificado como livre de malware, pois uma varredura completa com definições antivírus atuais não pôde ser realizada.

Fonte analisada: `No.Im.not.a.Human.v1.3.18.zip`, 1.042.955.341 bytes.

SHA-256 do ZIP de origem: `f8e6a46efbd41452266790a1350bbec3cfd6027470282171b912df80b08489f1`.

O ZIP original, os executáveis de Windows e as DLLs geradas pelas ferramentas de análise não acompanham este conjunto. Os scripts de engenharia reversa que trabalham sobre esses binários exigem o arquivo de origem. Os recursos exportados, o programa de diálogos, as referências de assembly em texto e o código novo necessário para recompilar a prévia são preservados aqui.

Este documento distingue recuperação de dados, reconstrução do interpretador e implementação dos sistemas do jogo. Um APK de demonstração dessas partes não deve ser apresentado como um port completo.
