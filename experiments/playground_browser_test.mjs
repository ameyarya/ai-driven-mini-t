/** Headless Chrome integration + real-Qwen goal matrix. Standard Node only. */
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,writeFile,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const out=path.join(root,'playground-data','browser-tests',new Date().toISOString().replaceAll(':','-'));
await mkdir(out,{recursive:true});
const profile=await mkdtemp(path.join(tmpdir(),'rook-headless-'));
const chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',[
 '--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
 '--disable-extensions','--disable-component-extensions-with-background-pages','--remote-debugging-port=0',`--user-data-dir=${profile}`,'--window-size=1280,800','about:blank'
],{stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let ws,seq=0;const pending=new Map(),events=[];
async function cdp(method,params={}){const id=++seq;const promise=new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method))},20000);pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value)},reject:error=>{clearTimeout(timer);reject(error)}})});ws.send(JSON.stringify({id,method,params}));return promise}
async function evaluate(expression){const r=await cdp('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function until(expression,timeout=150000){const end=Date.now()+timeout;while(Date.now()<end){if(await evaluate(expression))return;await sleep(200)}throw Error('Timed out: '+expression)}
const results={started:new Date().toISOString(),url:'http://127.0.0.1:8001',ui:[],cases:[],browserErrors:[]};
function check(name,ok,detail){results.ui.push({name,passed:!!ok,detail});if(!ok)throw Error('UI check failed: '+name)}
try{
 let port;
 for(let i=0;i<100;i++){try{port=(await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break}catch{await sleep(100)}}
 if(!port)throw Error('Chrome did not launch');
 const tabs=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();
 const tab=tabs.find(x=>x.type==='page'&&x.url==='about:blank')||tabs.find(x=>x.type==='page');if(!tab)throw Error('No Chrome page target');ws=new WebSocket(tab.webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
 ws.onmessage=event=>{const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}else events.push(m)};
 if(process.env.ROOK_PLAYGROUND_BACKEND==='mlx'){
  const deadline=Date.now()+60000;let ready=false;
  while(Date.now()<deadline){try{ready=(await(await fetch(results.url+'/api/models')).json()).mlx_ready;if(ready)break}catch{}await sleep(200)}
  if(!ready)throw Error('Trained model server did not become ready');
 }
 await cdp('Runtime.enable');await cdp('Page.enable');
 await cdp('Page.navigate',{url:results.url});
 await until("document.querySelector('#frames')?.options.length>0 && document.querySelector('#image')?.naturalWidth>0");
 const initial=await evaluate("({count:document.querySelector('#frames').options.length,reviewDisabled:document.querySelector('#review').disabled,image:document.querySelector('#image').naturalWidth,status:document.querySelector('#status').textContent})");
 check('Catalog and saved JPEG load',initial.count>0&&initial.image>0,initial);
 check('Unreviewed frame cannot be approved',initial.reviewDisabled);
 const backend=process.env.ROOK_PLAYGROUND_BACKEND||'ollama';
 if(await evaluate("Boolean(document.querySelector('#backend'))")){
  await evaluate(`document.querySelector('#backend').value=${JSON.stringify(backend)}`);
 }else if(backend!=='ollama'){throw Error('Model selector missing')}
 results.backend=backend;
 await writeFile(path.join(out,'initial.png'),Buffer.from((await cdp('Page.captureScreenshot',{format:'png'})).data,'base64'));
 check('Missing frame returns 404',(await fetch(results.url+'/image/unknown')).status===404);
 const post=async(body,extra={})=>fetch(results.url+'/api/infer',{method:'POST',headers:{'Content-Type':'application/json',...extra},body:JSON.stringify(body)});
 check('Unknown frame rejected',(await post({frame:'unknown',goal:'Center can'})).status===400);
 check('Blank goal rejected',(await post({frame:await evaluate("document.querySelector('#frames').value"),goal:' '})).status===400);
 check('Cross-origin write rejected',(await post({}, {Origin:'http://elsewhere.invalid'})).status===403);
 check('Non-JSON writes rejected',(await fetch(results.url+'/api/infer',{method:'POST',body:'text'})).status===415);
 const frames=await(await fetch(results.url+'/api/frames')).json();
 const pick=predicate=>frames.slice().reverse().find(x=>predicate(x.measurement));
 const scenes=[['left',pick(m=>m.target_visible&&m.target_x<35&&!m.target_clipped)],['right',pick(m=>m.target_visible&&m.target_x>65&&!m.target_clipped)],['center',pick(m=>m.target_visible&&Math.abs(m.target_x-50)<3&&!m.target_clipped)],['missing',pick(m=>!m.target_visible&&m.candidate_count===0)]];
 const goals=[
 ['center','Center the can in the image, then stop.','center'],
 ['approach','Move closer to the can until it occupies roughly 50% of the image height. Keep it centered, then stop.','approach_size'],
 ['find','Find the can by doing a 360 turn in place. Center it, then stop.','find'],
 ['combined','Find the can by turning in place, then move closer until it occupies roughly 50% of the image height. Keep it centered, then stop.','find_approach_size'],
 ['shoot','Find the can and shoot it.','unsupported'],
 ['away','Move farther away from the can.','unsupported'],
 ['physical_distance','Move within 20 centimeters of the can.','unsupported']
 ];
 for(const [scene,item] of scenes){if(!item){results.cases.push({scene,skipped:'No matching recorded scene'});continue}
  for(const [name,goal,visibleExpectedMode] of goals){
   // Non-search goals on an absent target should be refused, not guessed.
   const expectedMode=scene==='missing'&&['center','approach'].includes(name)?'unsupported':visibleExpectedMode;
   await evaluate(`document.querySelector('#frames').value=${JSON.stringify(item.id)};document.querySelector('#frames').dispatchEvent(new Event('change'));document.querySelector('#goal').value=${JSON.stringify(goal)};document.querySelector('#infer').click();`);
   await until("document.querySelector('#infer').disabled");
   check('Frame selection locked during '+scene+'/'+name,await evaluate("document.querySelector('#frames').disabled"));
   await until("!document.querySelector('#infer').disabled");
   const r=await evaluate("({status:document.querySelector('#status').textContent,plan:document.querySelector('#expected').value,reviewEnabled:!document.querySelector('#review').disabled,image:document.querySelector('#image').getAttribute('src')})");
   let plan;try{plan=JSON.parse(r.plan)}catch{}
   const accepted=r.status.startsWith('Plan returned');
   const modeCorrect=plan?.mode===expectedMode;
   const heightCorrect=expectedMode==='unsupported'||!['approach','combined'].includes(name)||plan?.height_percent===50;
   const passed=modeCorrect&&heightCorrect&&(expectedMode==='unsupported'?!accepted:accepted);
   results.cases.push({scene,case:name,frame:item.id,goal,expectedMode,passed,accepted,...r,plan});
   console.log(`${results.cases.length}/28 ${scene}/${name}: ${passed?'PASS':'FAIL'} · ${r.status}`);
   await writeFile(path.join(out,'report.json'),JSON.stringify(results,null,2));
  }
 }
 await evaluate("document.querySelector('#frames').dispatchEvent(new Event('change'))");
 check('Changing frames clears stale plan and approval',await evaluate("document.querySelector('#expected').value===''&&document.querySelector('#review').disabled"));
 results.browserErrors=events.filter(x=>x.method==='Runtime.exceptionThrown');
 check('No uncaught browser exceptions',results.browserErrors.length===0);
 await writeFile(path.join(out,'final.png'),Buffer.from((await cdp('Page.captureScreenshot',{format:'png'})).data,'base64'));
}catch(error){results.fatal=String(error);console.error(error)}finally{
 results.finished=new Date().toISOString();results.summary={uiPassed:results.ui.filter(x=>x.passed).length,uiTotal:results.ui.length,modelPassed:results.cases.filter(x=>x.passed).length,modelTotal:results.cases.filter(x=>!x.skipped).length};
 await writeFile(path.join(out,'report.json'),JSON.stringify(results,null,2));
 console.log('REPORT',out,JSON.stringify(results.summary));
 ws?.close();chrome.kill();
}
if(results.fatal)process.exitCode=1;
