const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const tick=()=>new Promise(r=>setImmediate(r));
const suggestion={title:'Birthday',guests:40,event_date:'2026-12-12',location:'Oakland',menu_notes:'Chicken requested',dietary_notes:null,next_question:'What time?'};
async function setup(options={}){
 const calls=[],spoken=[],recognitions=[];let resolveDraft;
 const dom=new JSDOM(fs.readFileSync('static/lbk.html','utf8'),{url:'https://caterflow.test/catering',runScripts:'dangerously',beforeParse(w){
  w.scrollTo=()=>{};w.SpeechSynthesisUtterance=class{constructor(text){this.text=text}};
  w.speechSynthesis={cancel(){},getVoices(){return [{lang:'en-US'},{lang:'es-US'}]},speak(u){spoken.push(u)}};
  w.SpeechRecognition=class{constructor(){recognitions.push(this)}start(){}stop(){this.onend?.()}abort(){this.onend?.()}};
  w.fetch=async(url,request)=>{
   if(url==='/api/events')return {ok:true,json:async()=>({user:{role:'customer'},csrf:'token',ai_drafting:true,photo_intake:true})};
   calls.push({url,body:JSON.parse(request.body)});
   if(options.pending)await new Promise(r=>resolveDraft=r);
   return {ok:true,json:async()=>({result:{draft:{...suggestion},requires_customer_review:true}})};
  };
 }});await tick();
 const doc=dom.window.document;
 const find=text=>Array.from(doc.querySelectorAll('button')).find(b=>b.textContent===text);
 const text=()=>doc.querySelector('textarea[aria-label]');
 const type=value=>{text().value=value;text().dispatchEvent(new dom.window.Event('input'))};
 return {dom,doc,calls,spoken,recognitions,find,text,type,resolve:()=>resolveDraft()};
}
test('speech fills editable transcript; it does not send or apply an inquiry',async()=>{
 const x=await setup();x.find('🎙 Speak').click();assert.equal(x.recognitions.length,1);
 x.recognitions[0].onresult({results:[[{transcript:'Chicken for forty people'}]]});
 assert.equal(x.text().value,'Chicken for forty people');assert.equal(x.calls.length,0);assert.equal(x.doc.getElementById('title').value,'');x.dom.window.close();
});
test('AI draft applies only after explicit acceptance; no event write',async()=>{
 const x=await setup();x.type('Birthday for 40');x.find('Prepare my request').click();await tick();
 assert.equal(x.doc.getElementById('title').value,'');assert.ok(x.doc.body.textContent.includes('Did we understand you?'));
 x.find('Use these details and review the form').click();assert.equal(x.doc.getElementById('title').value,'Birthday');assert.equal(x.doc.getElementById('guests').value,'40');
 assert.deepEqual(x.calls.map(c=>c.url),['/api/ai/draft']);x.dom.window.close();
});
test('editing text while drafting discards stale response and stale acceptance',async()=>{
 const x=await setup({pending:true});x.type('40 guests');x.find('Prepare my request').click();await tick();x.type('Actually 60 guests');x.resolve();await tick();
 assert.equal(x.find('Use these details and review the form'),undefined);assert.equal(x.doc.getElementById('guests').value,'');assert.equal(x.text().value,'Actually 60 guests');x.dom.window.close();
});
test('changing language while drafting cannot overwrite new language or form',async()=>{
 const x=await setup({pending:true});x.type('40 guests');x.find('Prepare my request').click();await tick();x.doc.getElementById('language').click();x.resolve();await tick();
 assert.equal(x.doc.documentElement.lang,'es');assert.equal(x.doc.getElementById('guests').value,'');assert.equal(x.find('Use these details and review the form'),undefined);x.dom.window.close();
});
test('camera input is explicit; selected photo requires consent before model call',async()=>{
 const x=await setup();assert.equal(x.doc.getElementById('camera-photo').getAttribute('capture'),'environment');
 x.dom.window.eval("IntakeMedia.preparePhoto=async()=> 'data:image/jpeg;base64,c3ludGhldGlj'");
 const input=x.doc.getElementById('upload-photo');Object.defineProperty(input,'files',{value:[{type:'image/jpeg',size:100}]});input.dispatchEvent(new x.dom.window.Event('change'));await tick();
 x.find('Prepare my request').click();await tick();assert.equal(x.calls.length,0);assert.match(x.doc.getElementById('status').textContent,/permission/);
 const consent=x.doc.getElementById('photo-consent');consent.checked=true;consent.dispatchEvent(new x.dom.window.Event('change'));x.find('Prepare my request').click();await tick();
 assert.equal(x.calls.length,1);assert.equal(x.calls[0].body.photo.consent,true);assert.equal(x.calls[0].body.photo.base64,'c3ludGhldGlj');x.dom.window.close();
});
test('visual service choices update the ordinary reviewed field',async()=>{
 const x=await setup();x.dom.window.eval('step=1;render()');x.find('🚚 Delivery').click();assert.equal(x.doc.getElementById('service').value,'delivery');assert.equal(x.find('🚚 Delivery').getAttribute('aria-pressed'),'true');x.dom.window.close();
});
test('read-aloud voices use selected language and exact displayed summary',async()=>{
 const x=await setup();x.find('🔊 Listen').click();assert.match(x.spoken[0].text,/Speak, type or show/);assert.equal(x.spoken[0].lang,'en-US');
 x.doc.getElementById('language').click();x.find('🔊 Escuchar').click();assert.equal(x.spoken[1].lang,'es-US');x.dom.window.close();
});
