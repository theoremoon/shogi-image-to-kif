// Verify using Piyo's actual public parser, provided as a local downloaded script.
// Usage: node scripts/verify_piyo.mjs /tmp/piyo-shogi.js docs/compatibility-fixtures.json
import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';
const [scriptPath, fixturePath] = process.argv.slice(2);
if (!scriptPath || !fixturePath) throw new Error('Pass the downloaded Piyo script and fixture JSON');
const source=fs.readFileSync(scriptPath,'utf8');
const context={DEBUG:false,console,Worker:function(){this.addEventListener=()=>{};},URL,
  document:{getElementById:()=>({options:[]})},window:{},navigator:{userAgent:''},location:{},setTimeout:()=>{},setInterval:()=>{}};
vm.createContext(context);vm.runInContext(source,context,{timeout:10000});
const results=[];
for(const fixture of JSON.parse(fs.readFileSync(fixturePath,'utf8'))){
  const actual=context.BOD2SFEN(fixture.kif);
  if(actual!==fixture.sfen)throw new Error(`${fixture.name}: ${actual} != ${fixture.sfen}`);
  if(!context.isSFEN('sfen '+fixture.sfen))throw new Error('SFEN prefix not recognized');
  results.push({name:fixture.name,expected_sfen:fixture.sfen,actual_sfen:actual,match:true});
}
console.log(JSON.stringify({source_url:'https://www.studiok-i.net/ps/ps_2_shogi.min.js',
  source_sha256:crypto.createHash('sha256').update(source).digest('hex'),checked_at:'2026-10-03',
  method:'Unmodified public BOD2SFEN parser, executed in a Node VM with browser globals stubbed',results},null,2));
