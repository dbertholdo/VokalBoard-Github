const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('app/static/js/search-pagination.js', 'utf8');

// DOM isolado: executa o controlador de produção, sem simular navegador real.
function setup() {
    const events = {}, pending = [], pushed = [];
    const location = {href:'http://localhost/board', origin:'http://localhost'};
    const input = {name:'q', value:'initial', type:'text'};
    const form = {dataset:{searchResults:'board-results'}, action:location.href, elements:[input],
        addEventListener:(n,f)=>events[n]=f, dispatchEvent:()=>{}, contains:()=>false};
    const results = {id:'board-results', content:'old', setAttribute:()=>{}, removeAttribute:()=>{},
        replaceChildren(...nodes){this.content=nodes.join('');}, focus:()=>{}, scrollIntoView:()=>{}, contains:()=>true};
    const retry = {}, error = {hidden:true, querySelector:()=>retry};
    vm.runInNewContext(source, {URL, URLSearchParams, AbortController, setTimeout, clearTimeout, location,
        FormData:class {constructor(){return [['q',input.value]];}},
        CustomEvent:class {},
        DOMParser:class {parseFromString(text){return {getElementById:()=>text==='missing'?null:{childNodes:[text]}};}},
        document:{querySelector:()=>form, getElementById:id=>id==='search-error'?error:results,
            addEventListener:(n,f)=>events[n]=f},
        window:{addEventListener:(n,f)=>events[n]=f},
        history:{pushState(_,__,url){pushed.push(url);location.href=url;},replaceState(_,__,url){location.href=url;}},
        fetch:(url,options)=>new Promise((resolve,reject)=>pending.push({url,options,resolve,reject}))});
    const click = (url, extra={}) => {
        let prevented=false;
        const link={href:url,origin:location.origin,closest:()=>true};
        events.click({target:{closest:()=>link},button:0,preventDefault(){prevented=true;},...extra});
        return prevented;
    };
    const respond = async (i,text,ok=true) => {pending[i].resolve({ok,text:async()=>text}); await new Promise(setImmediate);};
    return {events,pending,pushed,location,input,results,error,retry,click,respond};
}
test('pagination replaces results; modified clicks remain native', async()=>{
    const s=setup(); assert.equal(s.click('http://localhost/board?page=2',{ctrlKey:true}),false);
    assert.equal(s.pending.length,0);
    s.click('http://localhost/board?page=2'); await s.respond(0,'page2');
    assert.equal(s.results.content,'page2'); assert.equal(s.pushed.length,1);
});
test('back restores query without adding history', async()=>{
    const s=setup(); s.location.href='http://localhost/board?q=previous';
    s.events.popstate(); await s.respond(0,'previous');
    assert.equal(s.input.value,'previous'); assert.equal(s.pushed.length,0);
});
test('network failure retains content and offers retry; success clears error', async()=>{
    const s=setup(); s.click('http://localhost/board?page=2');
    s.pending[0].reject(new Error('offline')); await new Promise(setImmediate);
    assert.equal(s.results.content,'old'); assert.equal(s.error.hidden,false);
    assert.equal(s.retry.href,'http://localhost/board?page=2');
    s.click('http://localhost/board?page=2'); await s.respond(1,'new'); assert.equal(s.error.hidden,true);
});
test('late responses cannot overwrite newer results', async()=>{
    const s=setup(); s.click('http://localhost/board?q=old'); s.click('http://localhost/board?q=new');
    assert.equal(s.pending[0].options.signal.aborted,true);
    await s.respond(1,'new'); await s.respond(0,'old');
    assert.equal(s.results.content,'new'); assert.equal(s.pushed.length,1);
});
test('HTTP failures and invalid HTML preserve existing results', async()=>{
    for (const [body,ok] of [['server error',false],['missing',true]]) {
        const s=setup(); s.click('http://localhost/board?page=2'); await s.respond(0,body,ok);
        assert.equal(s.results.content,'old'); assert.equal(s.error.hidden,false);
    }
});
test('failed history keeps URL coherent', async()=>{
    const s=setup(); s.location.href='http://localhost/board?page=2'; s.events.popstate();
    await s.respond(0,'error',false); assert.equal(s.location.href,'http://localhost/board');
});
test('filter submit starts on page one', async()=>{
    const s=setup(); s.input.value='new search'; s.events.submit({preventDefault(){}});
    assert.equal(s.pending[0].url,'http://localhost/board?q=new+search'); await s.respond(0,'filtered');
});
