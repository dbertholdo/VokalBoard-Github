// Fast local controller checks; no browser, database or child processes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/listing-form.js', 'utf8');
const template = fs.readFileSync('app/templates/listing_form.html', 'utf8');
const types = ['seeking_singer', 'seeking_conductor', 'singer_available', 'conductor_available'];
let cases = 0;
for (const initial of types) {
    let change;
    const elements = Object.fromEntries(['job-fields', 'fee-input', 'repertoire-input', 'job-required-help']
        .map(id => [id, {value:'preserve me'}]));
    elements['listing-type-select'] = {value:initial, addEventListener(event, fn) {
        assert.equal(event,'change'); change=fn;
    }};
    const generic = {}, job = {};
    const firstDate = {value:'2026-09-01', addEventListener(){}};
    const lastDate = {removeAttribute(){}};
    const eventDate = {};
    const localInput = {disabled:false};
    elements['availability-fields'] = {querySelector: s => s.includes('available_from') ? firstDate : lastDate};
    elements['event-date-field'] = {querySelector:()=>eventDate};
    elements['listing-location'] = {querySelectorAll:()=>[localInput], addEventListener(){}};
    vm.runInNewContext(source, {document:{
        getElementById:id=>elements[id],
        querySelectorAll:selector=>[selector==='.label-generic'?generic:job],
    }});
    for (const type of [initial, ...types, initial]) {
        elements['listing-type-select'].value=type;
        change();
        const isJob=['seeking_singer','seeking_conductor'].includes(type);
        assert.equal(elements['availability-fields'].disabled,type!=='singer_available');
        assert.equal(eventDate.required,isJob);
        assert.equal(localInput.required,type!=='singer_available');
        assert.equal(lastDate.max,'2026-09-30');
        assert.equal(elements['job-fields'].hidden,false);
        assert.equal(elements['job-fields'].disabled,false);
        assert.equal(elements['fee-input'].required,isJob);
        assert.equal(elements['repertoire-input'].required,isJob);
        assert.equal(elements['job-required-help'].hidden,!isJob);
        assert.equal(generic.hidden,isJob);
        assert.equal(job.hidden,!isJob);
        assert.equal(elements['fee-input'].value,'preserve me');
    }
    cases++;
}
assert.equal((template.match(/name="csrf_token"/g)||[]).length,1);
assert.equal((template.match(/name="repertoire"/g)||[]).length,1);
assert.equal((template.match(/name="fee"/g)||[]).length,1);
assert(!template.includes('listing_form_voice_type_required_label'));
assert(template.indexOf('name="fee"') < template.indexOf("t('listing_form_optional_section')"));
assert(template.indexOf('name="voice_type_id"') > template.indexOf("t('listing_form_optional_section')"));
assert(template.includes('is_edit'));
const stack=[];
for (const match of template.matchAll(/{%[-+]?\s*(\w+)/g)) {
    const token=match[1];
    if (['if','for','block'].includes(token)) stack.push(token);
    if (['endif','endfor','endblock'].includes(token)) assert.equal(stack.pop(),token.slice(3));
}
assert.equal(stack.length,0);
console.log(`${cases} initial listing types and all transitions passed; template structural checks passed.`);
