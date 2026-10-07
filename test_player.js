// Exercise the player controller without network, media playback, or GPT.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const nodes={},requests=[];
function node(id){return nodes[id]??=( {id,style:{},classList:{toggle(){}},paused:true,currentTime:0,duration:4000,readyState:1,playbackRate:1,volume:1,checked:false,value:'65',plays:0,attrs:{},setPointerCapture(){},play(){this.plays++;this.paused=false;return Promise.resolve()},pause(){this.paused=true},removeAttribute(n){delete this.attrs[n];if(n==='src')this.src=''},getAttribute(n){return n==='src'?this.src:this.attrs[n]}} )}
const context={document:{querySelector:s=>node(s.slice(1)),fullscreenElement:null,addEventListener(){}},localStorage:{getItem(){return null},setItem(){}},performance:{now:()=>0},requestAnimationFrame:()=>1,cancelAnimationFrame(){},setInterval(){},fetch:async path=>{requests.push(path);return {ok:true,json:async()=>({stop_id:0,media_ready:false,entries:[{id:1,at:15,end:35,text:'A scene',audio:'voice-001.mp3',thumbnail:''}],progress:{status:'ready',done:1,total:1},preparing:false})}},console,Date,innerWidth:1440,innerHeight:900};
for(const id of ['background','pictures','speak','handle','full','stage','gptSetup','prepare','videoURL','progress','startCompanion','stopAll'])context[id]=node(id);
context.speak.checked=true;context.videoURL.value='';
vm.createContext(context);vm.runInContext(fs.readFileSync('player.html','utf8').split('<script>')[1].split('</script>')[0],context);
(async()=>{
 await new Promise(r=>setImmediate(r));
 const video=node('video'),voice=node('voice');video.currentTime=15;video.paused=false;
 vm.runInContext('sync()',context);assert.equal(voice.plays,0,'video playback alone must not narrate');
 context.startCompanion.onclick();assert.equal(voice.plays,1,'explicit Start enables cached narration');
 await context.stopAll.onclick();assert(video.paused);assert(voice.paused);
 video.paused=false;vm.runInContext('sync()',context);assert.equal(voice.plays,1,'Stop must stay disabled when video resumes');
 assert(requests.includes('/action/stop'));assert(!requests.includes('/prepare'));assert(!requests.includes('/action/browser'));
 console.log('Player consent and Stop checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
