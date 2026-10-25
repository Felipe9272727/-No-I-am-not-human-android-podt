//! A deliberately small, safe interpreter for the game's recovered Yarn VM graph.
//! The program format is the lossless JSON projection produced by the decoder.
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};

const MAX_SNAPSHOT_BYTES: usize = 32 * 1024 * 1024;
const MAX_SNAPSHOT_ENTRIES: usize = 100_000;
const MAX_SNAPSHOT_STRING_BYTES: usize = 1024 * 1024;

#[derive(Clone, Debug, PartialEq)]
pub struct Line { pub string_id: String, pub substitutions: Vec<String> }
#[derive(Clone, Debug, PartialEq)]
pub struct OptionItem { pub line: Line, pub destination: String, pub enabled: bool }
#[derive(Clone, Debug, PartialEq)]
pub enum Event { Line(Line), Options(Vec<OptionItem>), Command(String), Stopped, Error(String) }

pub type FunctionHandler = Box<dyn FnMut(&str, &[Value]) -> Result<Value,String> + Send>;

fn hex(bytes: &[u8]) -> String { bytes.iter().map(|b| format!("{b:02x}")).collect() }
fn primitive(value: &Value) -> bool { value.is_null() || value.is_string() || value.is_boolean() || value.is_number() }
fn require_exact_keys(map: &Map<String, Value>, keys: &[&str], what: &str) -> Result<(), String> {
    if map.len() != keys.len() || keys.iter().any(|key| !map.contains_key(*key)) {
        return Err(format!("{what} has missing or unknown fields"));
    }
    Ok(())
}

pub struct Runtime {
    program: Value, vars: Map<String, Value>, node: String, pc: usize, stack: Vec<Value>,
    options: Vec<OptionItem>, halted: bool, budget: usize,
    function_handler: Option<FunctionHandler>,
    program_sha256: String,
}

impl Runtime {
    pub fn from_json_str(s: &str) -> Result<Self, String> {
        let p: Value = serde_json::from_str(s).map_err(|e| e.to_string())?;
        Self::new(p)
    }
    pub fn new(program: Value) -> Result<Self, String> {
        if !program.get("nodes").and_then(Value::as_object).is_some() { return Err("program.nodes missing".into()); }
        let vars = program.get("initial_values").and_then(Value::as_object).cloned().unwrap_or_default();
        let program_sha256 = hex(&Sha256::digest(program.to_string().as_bytes()));
        Ok(Self { program, vars, node:String::new(), pc:0, stack:vec![], options:vec![], halted:true, budget:100_000, function_handler:None, program_sha256 })
    }
    pub fn set_function_handler(&mut self, handler: FunctionHandler) { self.function_handler=Some(handler); }
    pub fn set_step_budget(&mut self, n: usize) { self.budget=n; }
    pub fn variables(&self) -> &Map<String, Value> { &self.vars }
    pub fn set_variable(&mut self, key: impl Into<String>, value: Value) { self.vars.insert(key.into(), value); }
    pub fn current_node(&self) -> &str { &self.node }
    /// Return a versioned, JSON-compatible snapshot of VM state. External function callbacks
    /// and line metadata are host-owned and intentionally excluded.
    pub fn dump_snapshot(&self) -> Result<Value, String> {
        if self.vars.len() > MAX_SNAPSHOT_ENTRIES || self.stack.len() > MAX_SNAPSHOT_ENTRIES || self.options.len() > MAX_SNAPSHOT_ENTRIES {
            return Err("runtime state exceeds snapshot collection limits".into());
        }
        if self.node.len() > MAX_SNAPSHOT_STRING_BYTES
            || self.vars.iter().any(|(k, v)| k.len() > MAX_SNAPSHOT_STRING_BYTES || !primitive(v) || v.as_str().is_some_and(|s| s.len() > MAX_SNAPSHOT_STRING_BYTES))
            || self.stack.iter().any(|v| !primitive(v) || v.as_str().is_some_and(|s| s.len() > MAX_SNAPSHOT_STRING_BYTES))
            || self.options.iter().any(|o| o.line.string_id.len() > MAX_SNAPSHOT_STRING_BYTES || o.destination.len() > MAX_SNAPSHOT_STRING_BYTES
                || o.line.substitutions.len() > MAX_SNAPSHOT_ENTRIES || o.line.substitutions.iter().any(|s| s.len() > MAX_SNAPSHOT_STRING_BYTES)) {
            return Err("runtime state exceeds snapshot type or string limits".into());
        }
        let snapshot = Value::Object(Map::from_iter([
            ("format".into(), Value::String("ninah-yarn-vm-snapshot".into())),
            ("version".into(), Value::from(1)),
            ("program_sha256".into(), Value::String(self.program_sha256.clone())),
            ("state".into(), serde_json::json!({
                "variables": self.vars,
                "node": self.node,
                "pc": self.pc,
                "stack": self.stack,
                "options": self.options.iter().map(|o| serde_json::json!({
                    "line": {"string_id": o.line.string_id, "substitutions": o.line.substitutions},
                    "destination": o.destination,
                    "enabled": o.enabled,
                })).collect::<Vec<_>>(),
                "halted": self.halted,
            })),
        ]));
        if snapshot.to_string().len() > MAX_SNAPSHOT_BYTES { return Err("snapshot exceeds 32 MiB limit".into()); }
        Ok(snapshot)
    }

    /// Validate a complete snapshot against this exact program, then replace state in one
    /// assignment. A failed restore leaves every current VM field untouched.
    pub fn restore_snapshot(&mut self, snapshot: &Value) -> Result<(), String> {
        if snapshot.to_string().len() > MAX_SNAPSHOT_BYTES {
            return Err("snapshot exceeds 32 MiB limit".into());
        }
        let root = snapshot.as_object().ok_or("snapshot must be an object")?;
        require_exact_keys(root, &["format", "version", "program_sha256", "state"], "snapshot")?;
        if root.get("format").and_then(Value::as_str) != Some("ninah-yarn-vm-snapshot") {
            return Err("unsupported snapshot format".into());
        }
        if root.get("version").and_then(Value::as_u64) != Some(1) {
            return Err("unsupported snapshot version".into());
        }
        if root.get("program_sha256").and_then(Value::as_str) != Some(self.program_sha256.as_str()) {
            return Err("snapshot program identity mismatch".into());
        }
        let state = root.get("state").and_then(Value::as_object).ok_or("snapshot state must be an object")?;
        require_exact_keys(state, &["variables", "node", "pc", "stack", "options", "halted"], "snapshot state")?;
        let vars = state.get("variables").and_then(Value::as_object).cloned().ok_or("snapshot variables must be an object")?;
        if vars.len() > MAX_SNAPSHOT_ENTRIES { return Err("snapshot has too many variables".into()); }
        for (name, value) in &vars {
            if name.len() > MAX_SNAPSHOT_STRING_BYTES { return Err("snapshot variable name is too long".into()); }
            if !primitive(value) { return Err(format!("snapshot variable `{name}` must be primitive")); }
            if value.as_str().is_some_and(|s| s.len() > MAX_SNAPSHOT_STRING_BYTES) { return Err(format!("snapshot variable `{name}` is too long")); }
        }
        let node = state.get("node").and_then(Value::as_str).ok_or("snapshot node must be a string")?.to_owned();
        if node.len() > MAX_SNAPSHOT_STRING_BYTES { return Err("snapshot node name is too long".into()); }
        let pc = state.get("pc").and_then(Value::as_u64).and_then(|n| usize::try_from(n).ok()).ok_or("snapshot pc must be a nonnegative integer")?;
        let halted = state.get("halted").and_then(Value::as_bool).ok_or("snapshot halted must be a boolean")?;
        let stack = state.get("stack").and_then(Value::as_array).ok_or("snapshot stack must be an array")?.clone();
        if stack.len() > MAX_SNAPSHOT_ENTRIES { return Err("snapshot stack is too large".into()); }
        if stack.iter().any(|v| !primitive(v) || v.as_str().is_some_and(|s| s.len() > MAX_SNAPSHOT_STRING_BYTES)) {
            return Err("snapshot stack values must be primitive".into());
        }
        let option_values = state.get("options").and_then(Value::as_array).ok_or("snapshot options must be an array")?;
        if option_values.len() > MAX_SNAPSHOT_ENTRIES { return Err("snapshot has too many pending options".into()); }
        let mut options = Vec::with_capacity(option_values.len());
        for (i, value) in option_values.iter().enumerate() {
            let o = value.as_object().ok_or_else(|| format!("snapshot option {i} must be an object"))?;
            require_exact_keys(o, &["line", "destination", "enabled"], "snapshot option")?;
            let line_obj = o.get("line").and_then(Value::as_object).ok_or("snapshot option line must be an object")?;
            require_exact_keys(line_obj, &["string_id", "substitutions"], "snapshot option line")?;
            let string_id = line_obj.get("string_id").and_then(Value::as_str).ok_or("snapshot option string_id must be a string")?.to_owned();
            let substitutions = line_obj.get("substitutions").and_then(Value::as_array).ok_or("snapshot option substitutions must be an array")?
                .iter().map(|v| v.as_str().map(str::to_owned).ok_or_else(|| "snapshot substitutions must be strings".to_string()))
                .collect::<Result<Vec<_>, _>>()?;
            if substitutions.len() > MAX_SNAPSHOT_ENTRIES || substitutions.iter().any(|s| s.len() > MAX_SNAPSHOT_STRING_BYTES) {
                return Err("snapshot option substitutions exceed limits".into());
            }
            if string_id.len() > MAX_SNAPSHOT_STRING_BYTES { return Err("snapshot option line id is too long".into()); }
            let destination = o.get("destination").and_then(Value::as_str).ok_or("snapshot option destination must be a string")?.to_owned();
            if destination.len() > MAX_SNAPSHOT_STRING_BYTES { return Err("snapshot option destination is too long".into()); }
            let enabled = o.get("enabled").and_then(Value::as_bool).ok_or("snapshot option enabled must be a boolean")?;
            options.push(OptionItem { line: Line { string_id, substitutions }, destination, enabled });
        }
        if node.is_empty() {
            if !halted || pc != 0 || !stack.is_empty() || !options.is_empty() {
                return Err("snapshot has state without an active node".into());
            }
        } else {
            let n = self.program.get("nodes").and_then(|nodes| nodes.get(&node)).ok_or_else(|| format!("snapshot node missing from program: {node}"))?;
            let instructions = n.get("instructions").and_then(Value::as_array).ok_or_else(|| format!("program node {node} has no instruction array"))?;
            if pc > instructions.len() { return Err(format!("snapshot pc {pc} is outside node {node}")); }
            for option in &options {
                let target = n.get("labels").and_then(|labels| labels.get(&option.destination)).and_then(Value::as_u64)
                    .ok_or_else(|| format!("snapshot option destination is not a label in {node}: {}", option.destination))?;
                if target > instructions.len() as u64 { return Err(format!("snapshot option destination is outside node {node}: {}", option.destination)); }
            }
        }
        self.vars = vars;
        self.node = node;
        self.pc = pc;
        self.stack = stack;
        self.options = options;
        self.halted = halted;
        Ok(())
    }
    pub fn start(&mut self, name: &str) -> Event {
        self.stack.clear(); self.options.clear();
        if self.node_exists(name) { self.node=name.into(); self.pc=0; self.halted=false; self.run() }
        else { Event::Error(format!("unknown node: {name}")) }
    }
    pub fn advance(&mut self) -> Event { if self.halted { Event::Stopped } else { self.run() } }
    pub fn select_option(&mut self, index: usize) -> Event {
        let Some(o)=self.options.get(index).cloned() else { return Event::Error(format!("invalid option index {index}")); };
        if !o.enabled { return Event::Error("selected option is disabled".into()); }
        self.stack.push(Value::String(o.destination)); self.options.clear(); self.advance()
    }
    fn node_exists(&self,n:&str)->bool { self.program["nodes"].get(n).is_some() }
    fn pop(&mut self)->Result<Value,String> { self.stack.pop().ok_or_else(||format!("stack underflow at {}:{}",self.node,self.pc)) }
    fn truth(v:&Value)->Result<bool,String>{ match v {Value::Bool(b)=>Ok(*b),Value::Null=>Ok(false),Value::Number(n)=>Ok(n.as_f64().unwrap_or(0.)!=0.),_=>Err(format!("expected boolean, got {v}"))} }
    fn num(v:&Value)->Result<f64,String>{v.as_f64().ok_or_else(||format!("expected number, got {v}"))}
    fn string(v:Value)->String { match v {Value::String(s)=>s,Value::Null=>String::new(),Value::Bool(b)=>b.to_string(),Value::Number(n)=>n.as_f64().map(|x|if x.fract()==0.0{format!("{x:.0}")}else{x.to_string()}).unwrap_or_else(||n.to_string()),x=>x.to_string()} }
    fn target(&self, v:&Value)->Result<usize,String>{
        if let Some(n)=v.as_u64(){return Ok(n as usize)}
        let l=v.as_str().ok_or_else(||format!("invalid jump target {v}"))?;
        self.program["nodes"][&self.node]["labels"][l].as_u64().map(|n|n as usize).ok_or_else(||format!("unknown label {l} in {}",self.node))
    }
    fn run(&mut self)->Event {
        for _ in 0..self.budget {
            let Some(ins)=self.program["nodes"].get(&self.node).and_then(|n|n["instructions"].as_array()).and_then(|a|a.get(self.pc)).cloned() else {self.halted=true; return Event::Stopped;};
            let op=ins["opcode"].as_u64().unwrap_or(u64::MAX); let a=ins["operands"].as_array().cloned().unwrap_or_default(); let oldpc=self.pc; self.pc+=1;
            let result:Result<Option<Event>,String>=(|| { Ok(match op {
                0 => { self.pc=self.target(a.first().ok_or("JumpTo missing target")?)?; None },
                1 => { let dest=self.stack.last().ok_or("Jump stack underflow")?.clone(); self.pc=self.target(&dest)?; None },
                2|3 => { let id=a.first().and_then(Value::as_str).ok_or("content instruction missing string operand")?.to_string(); let count=a.get(1).and_then(Value::as_f64).unwrap_or(0.) as usize; let mut s=Vec::with_capacity(count); for _ in 0..count {s.push(Self::string(self.pop()?));} s.reverse(); if op==2 {Some(Event::Line(Line{string_id:id,substitutions:s}))} else { let mut text=id; let mut repl=Vec::new(); for i in (0..s.len()).rev(){let marker=format!("{{{i}}}");if let Some(at)=text.rfind(&marker){repl.push((at,marker.len(),s[i].clone()));}} for (at,len,value) in repl {text.replace_range(at..at+len,&value);} Some(Event::Command(text))} },
                4 => { let id=a.first().and_then(Value::as_str).ok_or("AddOption missing line id")?.to_string(); let dest=a.get(1).and_then(Value::as_str).ok_or("AddOption missing destination")?.to_string(); let count=a.get(2).and_then(Value::as_f64).unwrap_or(0.) as usize; let cond=a.get(3).and_then(Value::as_bool).unwrap_or(false); let mut s=Vec::with_capacity(count); for _ in 0..count{s.push(Self::string(self.pop()?));} s.reverse(); let enabled=if cond{Self::truth(&self.pop()?)?}else{true}; self.options.push(OptionItem{line:Line{string_id:id,substitutions:s},destination:dest,enabled}); None },
                5 => if self.options.is_empty(){self.halted=true;Some(Event::Stopped)}else{Some(Event::Options(self.options.clone()))},
                6 => {self.stack.push(a.first().cloned().ok_or("PushString missing operand")?);None},
                7 => {self.stack.push(a.first().cloned().ok_or("PushFloat missing operand")?);None},
                8 => {self.stack.push(a.first().cloned().ok_or("PushBool missing operand")?);None},
                9 => {self.stack.push(Value::Null);None},
                10 => {let v=self.stack.last().ok_or("JumpIfFalse stack underflow")?; if !Self::truth(v)?{self.pc=self.target(a.first().ok_or("JumpIfFalse missing target")?)?;} None},
                11 => {self.pop()?;None},
                12 => {let f=a.first().and_then(Value::as_str).ok_or("CallFunc missing name")?; let arity=Self::num(&self.pop()?)? as usize; let mut args=Vec::new();for _ in 0..arity{args.push(self.pop()?)} args.reverse(); let value=if f=="visited" || f=="visited_count" { if arity!=1{return Err(format!("function {f} expects 1 arg, bytecode passes {arity}"))}; let node=Self::string(args[0].clone()); let key=format!("$Yarn.Internal.Visiting.{node}"); let count=self.vars.get(&key).or_else(||self.program["initial_values"].get(&key)).and_then(Value::as_f64).unwrap_or(0.0); if f=="visited" {Value::Bool(count>0.0)} else {Value::from(count)} } else {if let Some(supported)=Self::function_arity(f) { if supported!=arity{return Err(format!("function {f} expects {supported} args, bytecode passes {arity}"))} Self::call(f,&args)? } else if let Some(handler)=self.function_handler.as_mut() { handler(f,&args)? } else { return Err(format!("unknown Yarn function `{f}` (no game hook registered)")); }}; self.stack.push(value);None},
                13 => {let k=a.first().and_then(Value::as_str).ok_or("PushVariable missing name")?;let v=self.vars.get(k).cloned().or_else(||self.program["initial_values"].get(k).cloned()).ok_or_else(||format!("undefined variable {k}"))?;self.stack.push(v);None},
                14 => {let k=a.first().and_then(Value::as_str).ok_or("StoreVariable missing name")?;let v=self.stack.last().cloned().ok_or("StoreVariable stack underflow")?;self.vars.insert(k.to_string(),v);None},
                15 => {self.halted=true;Some(Event::Stopped)},
                16 => {let dest=Self::string(self.pop()?); if !self.node_exists(&dest){return Err(format!("RunNode target missing: {dest}"))}; self.node=dest; self.pc=0; self.stack.clear(); self.options.clear(); None},
                _=>return Err(format!("unsupported Yarn opcode {op}")),
            }) })();
            match result {Ok(Some(e))=>return e,Ok(None)=>(),Err(e)=>{self.halted=true;return Event::Error(format!("{e} ({}:{oldpc})",self.node));}}
        }
        self.halted=true; Event::Error(format!("step budget ({}) exceeded; possible bytecode loop at {}:{}",self.budget,self.node,self.pc))
    }
    fn function_arity(f:&str)->Option<usize>{ Some(match f.to_ascii_lowercase().as_str(){
        "bool.not"=>1,
        "bool.and"|"bool.or"|"number.add"|"number.equalto"|"number.greaterthan"|"number.greaterthanorequalto"|"number.lessthan"=>2,
        _=>return None,
    }) }
    fn call(f:&str,a:&[Value])->Result<Value,String>{
        let arity=|n|if a.len()==n{Ok(())}else{Err(format!("{f} expects {n} args, got {}",a.len()))};
        Ok(match f.to_ascii_lowercase().as_str(){
            "bool.not"=>{arity(1)?;Value::Bool(!Self::truth(&a[0])?)},
            "bool.and"=>{arity(2)?;Value::Bool(Self::truth(&a[0])? && Self::truth(&a[1])?)},
            "bool.or"=>{arity(2)?;Value::Bool(Self::truth(&a[0])? || Self::truth(&a[1])?)},
            "number.equalto"=>{arity(2)?;Value::Bool(Self::num(&a[0])?==Self::num(&a[1])?)},
            "number.greaterthan"=>{arity(2)?;Value::Bool(Self::num(&a[0])?>Self::num(&a[1])?)},
            "number.greaterthanorequalto"=>{arity(2)?;Value::Bool(Self::num(&a[0])?>=Self::num(&a[1])?)},
            "number.lessthan"=>{arity(2)?;Value::Bool(Self::num(&a[0])?<Self::num(&a[1])?)},
            "number.add"=>{arity(2)?;Value::from(Self::num(&a[0])?+Self::num(&a[1])?)},
            _=>return Err(format!("unknown Yarn function `{f}` (no game hook registered)")),
        })
    }
}
