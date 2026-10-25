# Estado do port Android — 24 de outubro de 2026

Este checkpoint contém a reconstrução em C++ e a VM de diálogos em Rust. Ainda não é o APK completo solicitado. O projeto `../android-current/` integra este núcleo por JNI a uma interface Android com renderização libGDX, menu e abertura original. O antigo APK “NINAH — Diálogos” é um protótipo separado; ele não contém o núcleo C++ atual nem uma campanha completa.

## Integração realizada nesta etapa

`DialogueSession` liga a VM aos serviços C++ de inventário e ocupantes. O decodificador tipado cobre 12 tipos de comando, presentes em 396 das 4.043 instruções de comando do roteiro; as outras 3.647 seguem para a camada de cena ou para uma solicitação explícita ao host. Essa contagem mede decodificação, não cobertura completa da campanha. Entregador, atualização de déficit, expulsão pela FEMA e morte do cômodo têm adaptadores distintos; callbacks necessários precisam estar ligados ao estado real.

A nova `SceneCommandRouter` conecta os comandos disponíveis à apresentação e aos flags de história. Ela conserva como solicitações pendentes operações sem provedor ou dados suficientes. `SetupGun(true)` exige a operação do gerenciador de personagens; `SetupGun(false)` muda a apresentação sem essa operação. `DontSetupGun` chama o gerenciador com false e não é um evento de esconder a arma.

A apresentação contém dados de 61 personagens da cena: poses atuais e para o dia seguinte, retratos animados, sinais humanos/impostores e identidades dos recursos. Alterar uma pose atual modifica o pacote do cômodo; alterações para amanhã aguardam `apply_tomorrow_poses()`. Os pacotes carregam sprites, transformações e o campo que impede interação. A escala do retrato usa `Vector3.one * DialogScale + override.Scale`, corrigindo a inferência anterior. O novo host Android de teste consome esses pacotes para desenhar a cena; a apresentação final e o fluxo completo continuam em construção.

A rota original `Fatman_Asking_1_1_1` percorre as falas, atualiza os dados do retrato e entrega a Kombucha através da mesma sessão. Há testes separados de recusa do Firefighter e escolhas de energia da Alkonost. Isso não comprova uma campanha inteira.

## Retomada do diálogo

A VM e a sessão C++ agora possuem snapshots versionados. Eles preservam variáveis Yarn, pilha, nó, próxima instrução, opções pendentes, fala visível e comando aguardando o host. A restauração valida o programa, os metadados e a consistência dos eventos antes de trocar o estado. Restaurar a última fala da recompensa do Fatman não entrega o item novamente.

O host precisa salvar inventário, personagens, flags e apresentação na mesma transação. O aplicativo de teste faz essa cópia conjunta apenas em memória. O snapshot de diálogo sozinho não é um save completo da partida. Chamadas de confirmação de comandos também precisam ser serializadas pelo host; a comparação atual do texto rejeita textos divergentes, mas não identifica duas solicitações assíncronas distintas com o mesmo texto.

## Início confirmado e lacunas

A inicialização de `DayNightController` começa no dia 0 à noite, com energia 1 depois de `Init`; o contador bruto do construtor é 0 antes dessa etapa. O único visitante predefinido para dia 0 é Neighbour, convidado 1. A abertura original de aproximadamente 72 segundos foi extraída com suas cinco janelas de legendas. O callback de fim abre a cena de jogo 1. A seleção de diálogo da porta foi comprovada como `entrance_neighbour_0`; após a admissão, a primeira interação do vizinho sem conversas anteriores seleciona `talk_neighbour_1`. O gerador de visitas aguarda a preparação do randomizador; o atraso configurado para esse caso é um segundo. A prévia conta esse intervalo após entrar na casa, uma adaptação explícita do host. A lista inicial completa de ocupantes, outro eventual nó disparado automaticamente na cena e o instante exato dos callbacks originais ainda não foram estabelecidos. A evidência e os limites estão em `../reverse-bootstrap/`.

O host Android/JNI permite testar o início até a primeira conversa dentro da casa, além dos cômodos, retratos, sinais e três rotas de ferramentas com toque. Ainda faltam o fluxo completo da campanha, áudio além da abertura, efeitos restantes, persistência após fechar o aplicativo e validação em aparelho. O save é apenas um checkpoint em memória do contexto; ele não sobrevive ao encerramento. `ShowPlayerSign` não possui origem visual comprovada no recorte atual; a forma original de um argumento `ChangePose Dude_Chilling` permanece uma inconsistência a investigar. Comandos assíncronos como `wait` não são consumidos como efeitos instantâneos.

## Recursos e origem preservados

O programa original contém 3.255 nós, 56.585 instruções e 276 variáveis iniciais. Todas as 15.693 referências de falas/opções resolvem em português do Brasil e inglês. Foram preservadas 1.200 imagens de personagens, 56 áudios WAV com seus FSB5 e dez imagens adicionais da cena. Isso não equivale a todos os recursos audiovisuais de todas as cenas.

Os 73 objetos brutos de personagens e 275 entradas de emoção, 867 arquivos de análise nativa do assembly do jogo e os scripts de extração acompanham o código. O ZIP original possui cópias persistidas em partes, descritas em `../security/ORIGINAL_ARCHIVE_RECOVERY.json`; não é necessário pedir novo envio se o ambiente temporário reiniciar.

Nenhum EXE, DLL ou instalador original foi executado. Os executáveis e DLLs de Windows, incluindo a DLL modificada Steam, não entram na reconstrução. Os relatórios não certificam o pacote original como livre de malware.

Os resultados realmente executados estão em `HOST_VALIDATION.json`, `ANDROID_BUILD_VALIDATION.json` e `VALIDATION.json`. Compilar bibliotecas Android e passar testes no computador não demonstra execução em celular nem substitui o APK completo.
