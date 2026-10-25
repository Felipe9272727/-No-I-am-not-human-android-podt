# Verificação atual

Nesta etapa, o host da abertura passou com AddressSanitizer e UndefinedBehaviorSanitizer: menu, cinco intervalos de legendas, passagem para a casa, duas rotas de entrada/conversa do vizinho, admissão e visibilidade, estado da geladeira, geração de 15 telefones, consulta e desbloqueio do número do vizinho e restauração conjunta em memória. As três rotas anteriores de ferramentas também passaram. `android-current/host_validation.json` registra o comando, o resultado e os hashes dos arquivos testados. LeakSanitizer ficou desativado por uma falha de acesso a tarefas/ptrace do ambiente.

A implementação atual possui 19 executáveis de regressão C++ com AddressSanitizer e UndefinedBehaviorSanitizer. Passaram os testes de comandos, inventário, ocupantes, energia, cômodos, telefone, progressão, apresentação, sinais, opções e snapshots da sessão. A verificação de vazamentos está desativada neste ambiente.

Após reconstrução limpa dos caches de teste, passaram 14 casos Rust da VM Yarn e quatro da ponte C ABI. As duas rotas de integração C++/Rust com o roteiro original conferem energia, entrega de item e metadados exatos.

O novo host do aplicativo também passou por teste nativo com sanitizadores: recompensa do Fatman, recusa do Firefighter, energia da Alkonost, inspeção, pose futura da Mother e restauração conjunta em memória sem duplicar a recompensa.

Comandos, a partir da raiz:

```sh
bash reconstruction/native-game/build.sh
python3 tools/reverse-scenes/validate_scene_render_manifest.py
python3 tools/validate_reconstruction.py
python3 tools/android-current/build_apk.py
```

`native-game/HOST_VALIDATION.json` preserva o resultado anterior dos 19 executáveis realmente executados. `android-current/host_validation.json` descreve os testes do host; `android-current/port_validation_report.json` registra a compilação, conteúdo e assinatura da prévia do início. `android-current/validation_report.json` preserva o APK anterior. As configurações e os recursos de cena foram conferidos estruturalmente: 61 personagens e 1.223 referências visuais resolvidas; todas as 15.693 referências de falas/opções possuem texto em português e inglês.

O teste nativo do host não executa Android. A prévia nova ainda não foi instalada ou executada em aparelho/emulador neste ambiente. A campanha completa, áudio além do vídeo de abertura, aparência final e desempenho continuam pendentes de integração e validação. O APK antigo do visualizador de diálogos tem seu relatório histórico preservado em `mobile-runtime/LEGACY_VALIDATION.json`; ele não comprova o comportamento do aplicativo atual.
