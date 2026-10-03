import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..'),out=path.join(root,'playground-data/simulation');
await mkdir(out,{recursive:true});
const profile=await mkdtemp(path.join(tmpdir(),'rook-sim-chrome-'));
const chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--disable-gpu','--no-first-run','--disable-extensions','--remote-debugging-port=0',`--user-data-dir=${profile}`,'--window-size=1280,800','about:blank'],{stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let ws,id=0;const pending=new Map(),errors=[];
async function cdp(method,params={}){const seq=++id;const result=new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(seq);reject(Error(method+' timed out'))},20000);pending.set(seq,{resolve:v=>{clearTimeout(timer);resolve(v)},reject})});ws.send(JSON.stringify({id:seq,method,params}));return result}
async function evaluate(expression){const r=await cdp('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function until(expression){for(let n=0;n<300;n++){if(await evaluate(expression))return;await sleep(100)}throw Error('UI wait timed out: '+expression)}
const checks=[];function check(name,passed){checks.push({name,passed});if(!passed)throw Error(name)}
const backend=process.env.ROOK_SIM_BACKEND||'scripted';
try{
let port;for(let n=0;n<100;n++){try{port=(await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break}catch{await sleep(100)}}
const tabs=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}else if(m.method==='Runtime.exceptionThrown')errors.push(m)};
await cdp('Page.enable');await cdp('Runtime.enable');await cdp('Page.navigate',{url:'http://127.0.0.1:8002'});
await until("document.querySelector('#camera')?.naturalWidth===640 && document.querySelector('#labels')?.naturalWidth===640");
check('Both camera views load',true);
check('Page fits laptop height',await evaluate('document.documentElement.scrollHeight<=innerHeight'));
await writeFile(path.join(out,'page.png'),Buffer.from((await cdp('Page.captureScreenshot',{format:'png'})).data,'base64'));
await evaluate("document.querySelector('#reset').click()");await sleep(200);
if(backend==='ollama')await evaluate("document.querySelector('#backend').value='ollama'");
await evaluate("document.querySelector('#goal').value='Center the red can, then shoot once.';document.querySelector('#start').click()");
await until("document.querySelector('#shots').textContent.includes('contact HIT')");check('UI mission fires and reports simulated contact',true);
await evaluate("document.querySelector('#stop').click()");await until("document.querySelector('#status').textContent.includes('Stopped by user')");check('Stop button works',true);
await evaluate("document.querySelector('#reset').click()");await until("document.querySelector('#shots').textContent==='No shots'");check('Reset reloads simulated launcher',true);
check('No uncaught browser exceptions',errors.length===0);
}finally{
await writeFile(path.join(out,backend==='ollama'?'qwen-browser-checks.json':'browser-checks.json'),JSON.stringify({backend,checks,errors},null,2));ws?.close();chrome.kill();
}
console.log(JSON.stringify(checks));
