from pathlib import Path
import re
src=Path('reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/DialogSystem/Commands/DialogCommandsInstance.cs').read_text()
rows=[]; pending=None
for line in src.splitlines():
    m=re.search(r'\[(YarnCommand|YarnFunction)\("([^"]+)"\)\]',line)
    if m: pending=(m.group(1).removeprefix('Yarn'),m.group(2)); continue
    if pending:
        x=re.search(r'public static (.+?)\s+(\w+)\((.*?)\) \{ \}',line)
        if x:
            rows.append((pending[0],pending[1],f'{x.group(1)} {x.group(2)}({x.group(3)})'))
        pending=None
out=Path('reconstruction/logic/yarn_api_map.md')
with out.open('w') as f:
    f.write('# Yarn-to-game API map\n\n')
    f.write('Recovered from method attributes in Cpp2IL diffable-C# output for `Assembly-CSharp`; these names bind Yarn instructions to game service callbacks. This is a signature map, not proof that every command body was recovered.\n\n')
    f.write('| Kind | Yarn name | Game method |\n|---|---|---|\n')
    for kind,name,sig in rows: f.write(f'| {kind} | `{name}` | `{sig}` |\n')
print(f'{out} ({len(rows)} bindings)')
