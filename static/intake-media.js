/* Shared browser-only accessibility controls. No recording persistence or analytics. */
const IntakeMedia=(()=>{
  let recognition=null,revision=0;
  const t=(es,en)=>document.documentElement?.lang==='es'?es:en;
  const button=(text,action)=>{const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=action;return b;};
  function stop(){revision++;if(recognition){recognition.abort();recognition=null;}if('speechSynthesis' in window)window.speechSynthesis.cancel();}
  function speak(text,status){
    if(!('speechSynthesis' in window)){if(status)status.textContent=t('La lectura en voz alta no está disponible. Puedes leer o editar el texto.','Read-aloud is unavailable. You can read or edit the text.');return;}
    window.speechSynthesis.cancel();
    const utterance=new SpeechSynthesisUtterance(String(text).slice(0,7000));
    utterance.lang=document.documentElement?.lang==='es'?'es-US':'en-US';utterance.rate=.9;
    const voices=window.speechSynthesis.getVoices();const voice=voices.find(v=>v.lang.toLowerCase().startsWith(utterance.lang.slice(0,2)));
    if(voice)utterance.voice=voice;
    utterance.onerror=()=>{if(status)status.textContent=t('No se pudo leer. El texto sigue disponible.','Read-aloud failed. The text is still available.');};
    window.speechSynthesis.speak(utterance);
  }
  function listenButton(parent,text,status){const b=button(t('🔊 Escuchar','🔊 Listen'),()=>speak(typeof text==='function'?text():text,status));parent.append(b);return b;}
  function voice(parent,text,status,changed){
    const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
    const consent=document.createElement('p');consent.textContent=t('Al tocar Hablar, autorizas el micrófono. Tu navegador puede enviar audio a su servicio de voz. Revisa la transcripción antes de enviarla a la IA. No grabamos ni guardamos audio aquí.','Tapping Speak permits microphone use. Your browser may send audio to its speech service. Review the transcript before sending it to AI. We do not record or save audio here.');parent.append(consent);listenButton(parent,()=>consent.textContent,status);
    const talk=button(t('🎙 Hablar','🎙 Speak'),()=>{
      if(recognition){recognition.stop();return;}
      if(!Recognition){status.textContent=t('Usa el micrófono del teclado o escribe. Este navegador no ofrece reconocimiento de voz.','Use keyboard dictation or type. This browser does not offer speech recognition.');return;}
      if('speechSynthesis' in window)window.speechSynthesis.cancel();
      const token=revision,base=text.value;let current='';recognition=new Recognition();const active=recognition;
      active.lang=document.documentElement?.lang==='es'?'es-US':'en-US';active.continuous=false;active.interimResults=true;
      active.onresult=e=>{
        if(token!==revision)return;
        current=Array.from(e.results).map(r=>r[0].transcript).join(' ');
        text.value=(base+(base?'\n':'')+current).slice(0,4000);changed();
        status.textContent=t('Revisa y corrige lo que escuchamos.','Review and correct what we heard.');
      };
      active.onerror=()=>{if(token===revision)status.textContent=t('No se pudo escuchar. Puedes escribir o usar el dictado del teclado.','Could not listen. You can type or use keyboard dictation.');};
      active.onend=()=>{if(recognition===active)recognition=null;talk.textContent=t('🎙 Hablar','🎙 Speak');};
      try{active.start();talk.textContent=t('■ Terminar de hablar','■ Stop speaking');status.textContent=t('Escuchando…','Listening…');}
      catch{recognition=null;status.textContent=t('No se pudo activar el micrófono. Puedes escribir.','Microphone unavailable. You can type.');}
    });parent.append(talk);
    const note=document.createElement('p');note.textContent=t('Habla en el idioma seleccionado; si mezclas idiomas, revisa nombres, fechas y cantidades.','Speak in the selected language; if you mix languages, check names, dates and quantities.');parent.append(note);
  }
  async function preparePhoto(file){
    if(!file||!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>8_000_000)throw Error(t('Elige una foto JPEG, PNG o WebP de hasta 8 MB.','Choose a JPEG, PNG or WebP photo up to 8 MB.'));
    const url=URL.createObjectURL(file);
    try{
      const image=new Image();image.src=url;await image.decode();
      if(!image.naturalWidth||image.naturalWidth*image.naturalHeight>24_000_000)throw Error(t('Elige una foto más pequeña.','Choose a smaller photo.'));
      const scale=Math.min(1,1280/Math.max(image.naturalWidth,image.naturalHeight));
      const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
      const context=canvas.getContext('2d');context.fillStyle='#fff';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(image,0,0,canvas.width,canvas.height);
      let result=canvas.toDataURL('image/jpeg',.8);
      if(result.length>533000)result=canvas.toDataURL('image/jpeg',.5);
      if(result.length>533000)throw Error(t('Elige una foto más pequeña.','Choose a smaller photo.'));
      return result;
    }finally{URL.revokeObjectURL(url);}
  }
  if(typeof window!=='undefined' && window.addEventListener)window.addEventListener('pagehide',stop);
  return {stop,speak,voice,listenButton,preparePhoto,button};
})();
