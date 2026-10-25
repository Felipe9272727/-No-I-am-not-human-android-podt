# Estado atual

O código atual acrescenta a casa 3D original, movimento com joystick, câmera por toque e interação com portas. Os diálogos e a pausa usam imagens/fontes e coordenadas recuperadas da UI. O pacote anterior já possuía a abertura original e a primeira sequência do vizinho; essa sequência continua preservada.

Os extratores recuperaram 153 MeshRenderers, 100 malhas, 57 materiais, 42 texturas, 104 componentes de colisão, duas câmeras e 34 luzes. A extração de UI resolveu 119 sprites e cinco fontes TTF. Geometria, texturas e fontes são preservadas no pacote de dados separado; o APK usa variantes de textura limitadas a 1024 pixels para reduzir memória.

## Verificado nesta etapa

- Teste C++/Rust com ASan/UBSan: menu, introdução, duas rotas de entrada, duas rotas da primeira conversa, telefone, guardas de navegação e restauração de câmera/estado.
- WorldMathTest: direção do joystick, rotação, diagonal, limites de pitch e conversão UV.
- WorldGeometryTest: sete colliders originais de interação; movimento de 2,379 m desde a câmera inicial até parar na porta.
- Renderização real em Mesa EGL/OpenGL 4.5 por software; captura corrigida para a origem das linhas do framebuffer.
- Compilação Java contra Android 35/libGDX e preparação dos recursos.

Os relatórios em `reconstruction/android-current/` distinguem o teste de regras, a renderização no computador e a inspeção do APK. Nenhuma execução em Android é reivindicada.

## Limites

A campanha para após a primeira conversa interna do vizinho; o save é temporário. Close-up/pinos do telefone, novos dias, efeitos e animações restantes ainda não estão integrados. O movimento de 2,5 m/s é uma adaptação móvel, pois a velocidade original serializada não foi confirmada. Shader, iluminação e colisão aproximam a implementação original; a geometria/texturas extraídas são reais.

O Git é o registro do código atual. A cópia privada de versão 8 serve como base anterior e fonte de dados; não deve sobrescrever código novo do repositório.
