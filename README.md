# No, I'm not a Human — port Android experimental

Reconstrução em andamento da versão 1.3.18 fornecida pelo usuário. O repositório preserva o código novo, extratores, evidências e testes para retomar o trabalho após reinícios do ambiente. A campanha completa ainda não está implementada.

A versão 0.2 acrescentou a casa 3D original, colisões, joystick e câmera por toque. A interface dos diálogos e da pausa usa a geometria, imagens e fontes recuperadas do original. O menu, o vídeo de abertura com áudio e legendas, a primeira visita do vizinho, a conversa dentro da casa e o estado de telefone continuam integrados.

A versão 0.4 corrige a ausência dos shaders do libGDX dentro do APK, identificada pelo diagnóstico do aparelho. Menu, diálogos e interação usam artes/fontes recuperadas, substituindo os principais controles genéricos. O botão **DEBUG: pular intro** e o diagnóstico copiável permanecem. Há adaptações para celular e escolhas de fonte ainda inferidas; a interface não é apresentada como uma cópia idêntica do original.

A versão 0.5 acrescenta músicas originais ao menu e à abertura na casa, com ambiência e opção de silenciar. Repara duas texturas danificadas, ajusta transparência/profundidade e a renderização de objetos espelhados. O histórico de falhas antigas deixa de gerar avisos automáticos após uma atualização. Os próximos dias continuam fora do port; a UI e os efeitos ainda têm diferenças em relação ao original.

A versão 0.6 corrige paredes/teto descartados ao virar a câmera e acrescenta otimização dos modelos em C++ sem alterar triângulos, texturas ou normais. Reutiliza objetos do renderizador, inclui contador de FPS e oferece renderização equilibrada, leve ou nativa. O usuário relatou cerca de 10 FPS na 0.5; o ganho da 0.6 no aparelho ainda precisa ser medido.

A versão 0.7 remove a camada de software que forçava a interface a ser rasterizada pela CPU. Movimentos apenas de câmera deixam de redesenhar o HUD, as interações reaproveitam resultados e o GL descansa sob menu/intro. O diagnóstico mostra a aceleração real do Canvas e o custo de desenho do HUD. O usuário ainda precisa testar o desempenho dessa versão no Xiaomi.

A versão 0.8 recupera o tratamento de cor da cena noturna, anima seis portas internas a partir dos valores originais e permite voltar à exploração após a primeira conversa. A versão 0.9 corrige barreiras exageradas de caixas com escalas diferentes entre eixos e o apoio no alçapão. Recupera 18 camadas de cenário nas sete vistas internas originais, com posição, transparência e ordem de desenho da cena. Personagens e objetos condicionais continuam dependendo do estado do jogo; essa mudança não acrescenta novos dias ou libera áreas ainda sem progressão. Os testes de geometria e de desenho GLES2 passaram no host; o APK ainda precisa de teste no aparelho.

A versão 0.10 acrescenta a primeira manhã: após concluir a visita inicial, entre no quarto e toque em **Dormir**. A virada aplica as regras recuperadas do dia 1, com duas ações disponíveis; **Assistir à TV** abre as sete falas originais de `tv_1_necessary`, em português. A cama usa sua imagem, posição e escala recuperadas. O fade de 500 ms e os botões são adaptações para toque. Pausa e segundo plano congelam a transição, e a música muda para a faixa original diurna. A próxima noite, as visitas seguintes e a iluminação diurna final continuam em desenvolvimento.

A versão 0.11 acrescenta save manual no aparelho, com validação do estado completo e uma cópia anterior. Ao reabrir, use **Continuar**. Em **Opções → DEBUG: gato 3D**, pode-se conferir o modelo e a textura originais na cadeira da entrada. É uma prévia estática: animações, carinho, alimentação e a liberação pela Ballerina ainda não estão integrados. O teste fica desligado por padrão e não altera a campanha, que continua limitada à primeira manhã.

A versão 0.12 prioriza a fidelidade da cena: a ordem de sobreposição agora segue os filhos serializados de cada Transform do Unity. Isso corrige, por exemplo, a mesinha aparecendo por cima da cama. As seis inspeções usam as 13 camadas de imagem, molduras, máscara e coordenadas originais; mãos e foto seguem seus movimentos e tempos recuperados. O painel genérico de inspeção foi removido. Uma auditoria direta dos dados originais conferiu os 1.348 transforms e os 153 MeshRenderers da casa sem encontrar diferenças nas matrizes exportadas. Isso valida a geometria estática, mas não demonstra equivalência completa de iluminação, efeitos, estados de objetos ou comportamento. A execução continua reimplementada em C++/Rust/Java, e o movimento aleatório da íris permanece pendente.

A versão 0.13 foca na casa antes de ampliar a campanha. Recupera o estado inicial da geladeira da cozinha e a TV fixa do quarto, que eram omitidos por filtros de estados/personagens. Corrige o retrato da TV cobrindo as falas: segue a ordem original de desenho e os deslocamentos do painel recuperados de DialogViewData, incluindo o toque no mesmo lugar que o texto. A cama e a TV aceitam toque direto; os cômodos passam a oferecer pausa e save. A exportação também inclui o mineiro originalmente ativo no porão, com a pose do esqueleto serializada; suas animações ainda não são reproduzidas. Os sete cômodos foram comparados com composições independentes dos dados de origem em GLES2. Isso não equivale a teste no Xiaomi nem a paridade completa com o PC. Janelas/close-ups, interações narrativas dos móveis, iluminação e animações restantes continuam na lista da casa.

## Controles no celular

- Durante o vídeo: **DEBUG: pular intro** entra na casa sem esperar 72 segundos.
- Opções → Músicas ligadas/desligadas: controla a trilha e a ambiência; a escolha fica salva.
- Opções → Diagnóstico: copia ou compartilha o registro, por ação do usuário.
- Opções → Renderização: alterna entre equilibrada (padrão), leve e nativa; Mostrar/Ocultar FPS controla o contador.
- Joystick à esquerda: andar.
- Arrastar à direita: olhar ao redor.
- Mirar perto de uma porta: mostrar a ação de interação.
- Botão de pausa: continuar, opções, menu e **Salvar jogo**.
- **Salvar jogo** grava no aparelho; ao reabrir, use **Continuar** no menu.

A partir da 0.11, o save manual persiste ao fechar o aplicativo e mantém uma cópia anterior para recuperar gravações incompletas. A sequência atual chega à primeira manhã e ao primeiro noticiário. A noite do dia 1, o telefone em close-up, a iluminação final e outros efeitos permanecem em desenvolvimento.

## Código e dados

As regras e o JNI usam C++; a VM Yarn usa Rust; a apresentação Android usa Java e libGDX 1.14.2. Python extrai os dados e prepara o APK. Os executáveis e DLLs originais de Windows nunca são carregados pelo port.

- [Estado e testes](PROGRESS.md)
- [Recuperação e dependências de compilação](RECOVERY.md)
- [Aplicativo Android](reconstruction/android-current/)
- [Extração do mundo 3D](tools/reverse-world/)
- [Extração da UI original](tools/reverse-ui/)

Recursos originais grandes, arquivos de origem, SDK/NDK, caches, APKs e chaves de assinatura ficam fora do Git. O pacote de dados recuperados `NINAH-Recursos-3D-UI.zip` acompanha o backup privado e inclui os manifestos, modelos, texturas e fontes necessários. Restaure os dados sem substituir o código mais novo deste repositório.

## Verificações

Passaram os testes de regras C++/Rust com AddressSanitizer e UndefinedBehaviorSanitizer, incluindo as duas rotas iniciais do vizinho, estado de telefone, navegação e save/restore. Os testes Java verificam eixos do joystick, limites da câmera, sete alvos de interação e colisão com a geometria original. A casa foi renderizada de verdade em Mesa/EGL sem janela, incluindo a câmera inicial e outro ângulo.

Esses resultados não equivalem a execução em um aparelho Android. O desempenho, todos os efeitos originais e a campanha completa ainda precisam de validação e desenvolvimento.

A verificação atual remove os recursos do JAR de desenvolvimento: os shaders
são carregados exclusivamente do APK entregue. A versão 0.3 reproduz a falha,
enquanto a versão 0.4 carrega todos os arquivos e renderiza 120 frames em GLES2.
O usuário confirmou que a versão 0.4 entra na casa no Xiaomi, mas relatou falhas visuais. As mudanças da versão 0.5 passaram por compilação e testes de gráficos no host; seu funcionamento no aparelho ainda precisa de teste.
