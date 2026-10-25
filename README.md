# No, I'm not a Human — port Android experimental

Reconstrução em andamento da versão 1.3.18 fornecida pelo usuário. O repositório preserva o código novo, extratores, evidências e testes para retomar o trabalho após reinícios do ambiente. A campanha completa ainda não está implementada.

A versão 0.2 acrescentou a casa 3D original, colisões, joystick e câmera por toque. A interface dos diálogos e da pausa usa a geometria, imagens e fontes recuperadas do original. O menu, o vídeo de abertura com áudio e legendas, a primeira visita do vizinho, a conversa dentro da casa e o estado de telefone continuam integrados.

A versão 0.3 inclui o botão **DEBUG: pular intro**, diagnóstico copiável no aparelho e recuperação com iluminação simplificada se a compilação do shader falhar. A causa exata do fechamento relatado no Redmi ainda não foi confirmada.

## Controles no celular

- Durante o vídeo: **DEBUG: pular intro** entra na casa sem esperar 72 segundos.
- Opções → Diagnóstico: copia ou compartilha o registro, por ação do usuário.
- Joystick à esquerda: andar.
- Arrastar à direita: olhar ao redor.
- Mirar perto de uma porta: mostrar a ação de interação.
- Botão de pausa: continuar, opções, menu e salvar a sessão.

O save é apenas em memória: fechar o aplicativo perde o estado. A sequência atual termina após a primeira conversa com o vizinho dentro da casa. Os próximos dias, o telefone em close-up, a iluminação final e outros efeitos permanecem em desenvolvimento.

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
