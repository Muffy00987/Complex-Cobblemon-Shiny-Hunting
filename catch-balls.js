(()=>{
const BALL_IMG='https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/';
const ballImg=slug=>`${BALL_IMG}${slug}-ball.png`;
function catchChance(rate,mult){
  const r=Number(rate);
  if(!Number.isFinite(r)||r<=0)return null;
  const modified=(r*mult)/3; // Cobblemon default calculator: full HP, in battle, no status, level 13+
  if(modified>=255)return 100;
  const shake=Math.min(65536,Math.round(65536/Math.pow(255/modified,0.1875)));
  return Math.max(0,Math.min(100,Math.pow(shake/65537,4)*100));
}
function fmt(p){if(p==null)return 'Unknown';if(p>=99.95)return '≈100%';if(p<0.1)return `${p.toFixed(2)}%`;return `${p.toFixed(1)}%`}
function bestBalls(x){
  const types=(x.types||[]).map(t=>String(t).toLowerCase());
  const biome=(x.biomes||'').toLowerCase();
  const e=x.encounter||{};
  const options=[
    {name:'Quick Ball',slug:'quick',mult:5,why:'5× on the first turn'},
    {name:'Dream Ball',slug:'dream',mult:4,why:'4× while the target is asleep'},
    {name:'Timer Ball',slug:'timer',mult:4,why:'Up to 4× late in battle'}
  ];
  if(types.includes('water')||types.includes('bug'))options.push({name:'Net Ball',slug:'net',mult:3,why:'3× on Water- or Bug-type Pokémon'});
  if(types.includes('water')||/ocean|river|beach|swamp|lake|water/.test(biome))options.push({name:'Dive Ball',slug:'dive',mult:3.5,why:'3.5× when the target is submerged'});
  const light=(e.light_ranges||[]).some(r=>Number(r?.min??99)<=7||Number(r?.max??99)<=7);
  if(light||/cave|nether|deep dark|underground/.test(biome))options.push({name:'Dusk Ball',slug:'dusk',mult:3.5,why:'3.5× at light 0; 3× at light 1–7'});
  if(/forest|plains/.test(biome))options.push({name:'Park Ball',slug:'park',mult:2.5,why:'2.5× in Forest or Plains biomes'});
  options.push({name:'Repeat Ball',slug:'repeat',mult:3.5,why:'3.5× if already registered as caught'});
  const seen=new Set();
  return options.filter(o=>!seen.has(o.name)&&seen.add(o.name)).sort((a,b)=>b.mult-a.mult).slice(0,3).map(o=>({...o,chance:catchChance(x.catch_rate,o.mult)}));
}
function panel(x){
  const balls=bestBalls(x);
  return `<section class="capture-panel"><div class="capture-title"><span>◉</span><div><b>Best Poké Balls</b><small>Best applicable Cobblemon options</small></div></div><div class="capture-balls">${balls.map((b,i)=>`<div class="capture-ball"><div class="capture-rank">#${i+1}</div><img src="${ballImg(b.slug)}" alt="${b.name}" loading="lazy"><b>${b.name}</b><strong>${fmt(b.chance)}</strong><span>${b.mult}× catch modifier</span><small>${b.why}</small></div>`).join('')}</div><p class="capture-note">Estimated chance assumes full HP, no status, in battle, level 13+, and that the listed ball condition is active. Lower HP or Sleep/Freeze can raise the actual chance. Master Ball is excluded because it is always guaranteed.</p></section>`;
}
const css=`
.modalbox{width:min(980px,100%)}
.modalTop{grid-template-columns:180px minmax(180px,1fr) minmax(330px,1.35fr);gap:18px}
.capture-panel{border-left:1px solid var(--line);padding-left:18px;min-width:0}
.capture-title{display:flex;align-items:center;gap:9px;margin-bottom:10px}.capture-title>span{font-size:25px;color:var(--aqua)}.capture-title b{display:block}.capture-title small{display:block;color:var(--muted);font-size:10px;margin-top:2px}
.capture-balls{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.capture-ball{position:relative;text-align:center;border:1px solid var(--line);border-radius:10px;background:linear-gradient(150deg,rgba(20,31,48,.96),rgba(18,15,31,.96));padding:8px 5px;min-width:0}.capture-ball img{display:block;width:54px;height:54px;object-fit:contain;image-rendering:pixelated;margin:0 auto 3px;filter:drop-shadow(0 5px 6px rgba(0,0,0,.45))}.capture-ball b{display:block;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.capture-ball strong{display:block;color:var(--aqua);font-size:17px;margin-top:3px}.capture-ball span{display:block;color:#fff;font-size:9px;margin-top:1px}.capture-ball small{display:block;color:var(--muted);font-size:8px;line-height:1.25;margin-top:4px}.capture-rank{position:absolute;top:5px;left:6px;font-size:9px;font-weight:900;color:var(--gold)}.capture-note{color:var(--muted);font-size:9px;line-height:1.35;margin:8px 0 0}
@media(max-width:850px){.modalTop{grid-template-columns:150px 1fr}.capture-panel{grid-column:1/-1;border-left:0;border-top:1px solid var(--line);padding:14px 0 0}.modalTop>img{width:140px;height:140px}}
@media(max-width:520px){.modalTop{grid-template-columns:1fr}.modalTop>img{margin:auto}.capture-balls{grid-template-columns:1fr 1fr 1fr}.capture-ball img{width:44px;height:44px}.capture-ball strong{font-size:14px}}
`;
const style=document.createElement('style');style.textContent=css;document.head.appendChild(style);
const original=window.openPokemon;
if(typeof original!=='function')return;
window.openPokemon=function(x){
  original(x);
  const top=document.querySelector('#modalBody .modalTop');
  if(top&&!top.querySelector('.capture-panel'))top.insertAdjacentHTML('beforeend',panel(x));
};
})();
