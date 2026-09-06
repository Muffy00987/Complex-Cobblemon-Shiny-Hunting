import csv, io, json, re, urllib.request, zipfile
from html import unescape
from pathlib import Path

SPAWN_URL='https://raw.githubusercontent.com/hspahic-cs/cobblemon-server/main/docs/spawn-lookup.md'
POKE_BASE='https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'
COBBLEMON_ARCHIVE='https://codeload.github.com/codemonkey85/Cobblemon-Mirror/zip/refs/heads/main'

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Cobblemon-Shiny-Hunting-Updater'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read().decode('utf-8')


def get_bytes(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Cobblemon-Shiny-Hunting-Updater'})
    with urllib.request.urlopen(req,timeout=120) as r:
        return r.read()

def _add_unique(d,key,value):
    if value is None or value == '' or value == []:
        return
    if isinstance(value,list):
        for v in value:
            _add_unique(d,key,v)
        return
    d.setdefault(key,[])
    if value not in d[key]:
        d[key].append(value)

def load_spawn_conditions():
    """Load base Cobblemon spawn_pool_world JSON and summarize encounter conditions by Pokémon."""
    out={}
    try:
        blob=get_bytes(COBBLEMON_ARCHIVE)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for name in z.namelist():
                if '/data/cobblemon/spawn_pool_world/' not in name or not name.endswith('.json'):
                    continue
                try:
                    obj=json.loads(z.read(name).decode('utf-8'))
                except Exception:
                    continue
                if str(obj.get('enabled',True)).lower() == 'false':
                    continue
                for spawn in obj.get('spawns',[]) or []:
                    if spawn.get('type') not in (None,'pokemon'):
                        continue
                    pname=spawn.get('pokemon')
                    if not pname:
                        continue
                    key=norm(pname)
                    e=out.setdefault(key,{
                        'time_ranges':[],'boosted_times':[],'weather':[],'y_ranges':[],
                        'light_ranges':[],'sky_light_ranges':[],'moon_phases':[],
                        'sky_access':[],'contexts':[]
                    })
                    _add_unique(e,'contexts',spawn.get('context'))
                    cond=spawn.get('condition') or {}
                    _add_unique(e,'time_ranges',cond.get('timeRange'))
                    if 'isRaining' in cond:
                        _add_unique(e,'weather','Rain required' if cond.get('isRaining') else 'No rain')
                    if 'isThundering' in cond:
                        _add_unique(e,'weather','Thunder required' if cond.get('isThundering') else 'No thunder')
                    if 'minY' in cond or 'maxY' in cond:
                        e['y_ranges'].append({'min':cond.get('minY'),'max':cond.get('maxY')})
                    if 'minLight' in cond or 'maxLight' in cond:
                        e['light_ranges'].append({'min':cond.get('minLight'),'max':cond.get('maxLight')})
                    if 'minSkyLight' in cond or 'maxSkyLight' in cond:
                        e['sky_light_ranges'].append({'min':cond.get('minSkyLight'),'max':cond.get('maxSkyLight')})
                    _add_unique(e,'moon_phases',cond.get('moonPhase'))
                    if 'canSeeSky' in cond:
                        _add_unique(e,'sky_access','Must see sky' if cond.get('canSeeSky') else 'Must not see sky')

                    anti=spawn.get('anticondition') or {}
                    if 'isRaining' in anti and anti.get('isRaining'):
                        _add_unique(e,'weather','Cannot be raining')
                    if 'isThundering' in anti and anti.get('isThundering'):
                        _add_unique(e,'weather','Cannot be thundering')

                    multipliers=[]
                    wm=spawn.get('weightMultiplier')
                    if wm:
                        multipliers.append(wm)
                    multipliers.extend(spawn.get('weightMultipliers') or [])
                    for mult in multipliers:
                        mc=(mult or {}).get('condition') or {}
                        _add_unique(e,'boosted_times',mc.get('timeRange'))
        return out
    except Exception as exc:
        print('Warning: could not load detailed Cobblemon spawn conditions:',exc)
        return {}

def norm(s):
    s=unescape(s).strip().lower()
    s=s.replace('♀','-f').replace('♂','-m')
    s=re.sub(r"[^a-z0-9]+",'-',s).strip('-')
    return s

def parse_spawn(text):
    rows=[]
    for m in re.finditer(r'<tr>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>',text,re.S|re.I):
        cells=[re.sub(r'<[^>]+>','',x).strip() for x in m.groups()]
        if len(cells)==3 and cells[0] != 'Species':
            rows.append({'name':unescape(cells[0]),'rarity':unescape(cells[1]),'biomes':unescape(cells[2]),'types':[],'groups':[],'pokemon_id':None,'forms':[],'catch_rate':None,'encounter':{}})
    return rows

def csv_rows(name):
    return list(csv.DictReader(io.StringIO(get(POKE_BASE+name))))

spawn_text=get(SPAWN_URL)
rows=parse_spawn(spawn_text)
if not rows:
    raise RuntimeError('No spawn rows parsed')

pokemon=csv_rows('pokemon.csv')
pokemon_types=csv_rows('pokemon_types.csv')
species=csv_rows('pokemon_species.csv')
egg=csv_rows('pokemon_egg_groups.csv')
spawn_conditions=load_spawn_conditions()
capture_rate_by_species={int(r['id']):int(r['capture_rate']) for r in species if r.get('capture_rate') not in (None,'')}

# PokeAPI language id 9 is English in current data.
name_by_species_id={r['id']:r['identifier'] for r in species}
# Species egg-group ids.
egg_ids={}
for r in egg:
    egg_ids.setdefault(r['species_id'],[]).append(r['egg_group_id'])
egg_names={r['id']:r['identifier'].replace('-',' ') for r in csv_rows('egg_groups.csv')}
# Type ids/names.
type_names={r['id']:r['identifier'].replace('-',' ').title() for r in csv_rows('types.csv')}

types_by_pokemon={}
type_species_by_id={}
for r in pokemon:
    type_species_by_id[r['id']]=r['species_id']
for r in pokemon_types:
    pid=r['pokemon_id']
    types_by_pokemon.setdefault(pid,[]).append((int(r['slot']),type_names.get(r['type_id'],r['type_id'])))
for k in types_by_pokemon:
    types_by_pokemon[k]=[x[1] for x in sorted(types_by_pokemon[k])]

# Build lookup from normalized identifiers and a few display-name variants.
sp_by_key={norm(v):int(k) for k,v in name_by_species_id.items()}
pokemon_by_key={norm(p['identifier']):p for p in pokemon}

# All known PokeAPI visual forms/variants for each species.
forms_by_species={}
for p in pokemon:
    forms_by_species.setdefault(p['species_id'],[]).append({
        'id':int(p['id']),
        'identifier':p['identifier'],
        'form_identifier':p.get('form_identifier') or ('default' if p.get('is_default')=='1' else p['identifier'].split('-',1)[-1]),
        'is_default':p.get('is_default')=='1'
    })
for sid in forms_by_species:
    forms_by_species[sid].sort(key=lambda f:(not f['is_default'], f['id']))
for p in pokemon:
    spid=int(p['species_id'])
    sp_by_key.setdefault(norm(p['identifier']),spid)

# Common Cobblemon display variants -> PokeAPI species identifiers.
ALIASES={
    'mr-mime':'mr-mime','mime-jr':'mime-jr','nidoran-f':'nidoran-f','nidoran-m':'nidoran-m',
    'farfetchd':'farfetchd','sirfetchd':'sirfetchd','type-null':'type-null','jangmo-o':'jangmo-o',
}
for r in rows:
    key=norm(r['name'])
    sid=sp_by_key.get(ALIASES.get(key,key))
    if sid is None:
        # Try dropping common regional/form suffixes only when a base species exists.
        for suffix in ('-alolan','-galarian','-hisuian','-paldean'):
            if key.endswith(suffix) and key[:-len(suffix)] in sp_by_key:
                sid=sp_by_key[key[:-len(suffix)]]; break
    if sid is not None:
        form=pokemon_by_key.get(key)
        if form is None:
            # Try a direct identifier lookup after removing a few display-only separators.
            form=pokemon_by_key.get(norm(r['name']))
        if form is not None:
            r['types']=types_by_pokemon.get(form['id'],[])
            r['pokemon_id']=int(form['id'])
            sid=int(form['species_id'])
        else:
            r['types']=[]
            # Fall back to the base species Pokémon id when a spawn row has no exact form match.
            base_p=next((p for p in pokemon if int(p['species_id'])==int(sid) and p.get('is_default')=='1'),None)
            if base_p is not None:
                r['pokemon_id']=int(base_p['id'])
        r['groups']=[egg_names.get(t,str(t)).replace('-',' ').title() for t in egg_ids.get(str(sid),[])]
        r['forms']=forms_by_species.get(str(sid),forms_by_species.get(int(sid),[]))
        r['catch_rate']=capture_rate_by_species.get(int(sid))
        # Prefer exact form/display key, then species identifier.
        encounter=spawn_conditions.get(key) or spawn_conditions.get(norm(name_by_species_id.get(str(sid),''))) or {}
        r['encounter']=encounter

out=Path('data/spawn-data.js')
out.parent.mkdir(parents=True,exist_ok=True)
meta={
    'source':SPAWN_URL,
    'encounter_source':COBBLEMON_ARCHIVE,
    'updated_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
    'spawn_rows':len(rows),
    'species':len({r['name'] for r in rows}),
}
out.write_text('window.COBBLEMON_SPAWN_META='+json.dumps(meta,separators=(',',':'))+';\nwindow.COBBLEMON_SPAWN_DATA='+json.dumps(rows,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print(json.dumps(meta,indent=2))
