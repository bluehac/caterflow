/* No customer content is sent to Turnstile by this application. */
const BotGuard=(()=>{
 let config=null,pending=false;
 async function headers(path){
  const action={login:'login',intake:'intake','ai/draft':'ai'}[path];if(!action)return {};
  if(!config){const r=await fetch('/api/security');if(!r.ok)throw Error('Secure verification unavailable');config=await r.json();}
  if(!config.enabled)return {};
  if(!config.sitekey)throw Error('Secure verification unavailable');
  if(pending)throw Error('Complete the current secure verification');
  pending=true;
  try{return {'X-Turnstile-Token':await challenge(action)};}finally{pending=false;}
 }
 function challenge(action){return new Promise((resolve,reject)=>{
  const es=document.documentElement.lang==='es',dialog=document.createElement('dialog'),title=document.createElement('h2'),message=document.createElement('p'),target=document.createElement('div'),cancel=document.createElement('button');
  title.textContent=es?'Verificación segura':'Secure verification';message.textContent=es?'Verifica para continuar. Tu solicitud sigue aquí.':'Verify to continue. Your draft stays here.';cancel.textContent=es?'Cancelar':'Cancel';cancel.type='button';dialog.setAttribute('aria-label',title.textContent);dialog.style.cssText='max-width:390px;width:94%;padding:20px;border:2px solid #D7B06A;border-radius:18px;background:#102B56;color:white';dialog.append(title,message,target,cancel);document.body.append(dialog);dialog.showModal();let widget,done=false;
  const finish=(error,token)=>{if(done)return;done=true;clearTimeout(timer);if(widget!==undefined&&window.turnstile)window.turnstile.remove(widget);dialog.close();dialog.remove();error?reject(Error(error)):resolve(token);};
  cancel.onclick=()=>finish(es?'Verificación cancelada':'Verification cancelled');dialog.oncancel=e=>{e.preventDefault();cancel.click();};
  const timer=setTimeout(()=>finish(es?'Intenta verificar de nuevo':'Please try verification again'),120000);
  const render=()=>{try{widget=window.turnstile.render(target,{sitekey:config.sitekey,action,language:es?'es':'en',callback:token=>finish(null,token),'error-callback':()=>finish(es?'No se pudo verificar':'Verification unavailable'),'expired-callback':()=>finish(es?'Verifica de nuevo':'Please verify again')});}catch{finish('Secure verification unavailable');}};
  if(window.turnstile){render();return;}
  const old=document.getElementById('turnstile-script');if(old)old.remove();
  const script=document.createElement('script');script.id='turnstile-script';script.src='https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';script.onload=render;script.onerror=()=>finish('Secure verification unavailable');document.head.append(script);
 });}
 return {headers};
})();
