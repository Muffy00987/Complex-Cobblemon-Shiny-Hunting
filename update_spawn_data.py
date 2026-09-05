import csv, io, json, re, urllib.request
from html import unescape
from pathlib import Path

SPAWN_URL='https://raw.githubusercontent.com/hspahic-cs/cobblemon-server/main/docs/spawn-lookup.md'
POKE_BASE='https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Cobblemon-Shiny-Hunting-Updater'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read().decode('utf-8')

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
            rows.append({'name':unescape(cells[0]),'rarity':unescape(cells[1]),'biomes':unescape(cells[2]),'types':[],'groups':[],'pokemon_id':None,'forms':[]})
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

# PokeAPI language id 9 is English in current data.
name_by_species_id={r['id']:r['identifier'] for r in species}
# Species egg-group ids.
egg_ids={}
for r in egg:
    egg_ids.setdefault(r['species_id'],[]).append(r['type_id'])
egg_names={r['id']:r['identifier'].replace('-',' ') for r in csv_rows('egg_groups.csv')}
# Type ids/names.
type_names={r['id']:r['identifier'].replace('-',' ').title() for r in csv_rows('types.csv')}

types_by_pokemon={}
type_species_by_id={}
for r in pokemon:
    type_species_by_id[r['id']]=r['species_id']
for r in pokemon_types:
    pid=r['pokemon_id']
    types_by_pokemon.setdefault(pid,[]).append((int(r['slot']),type_names.get(r['type_id'],r['egg_group_id'])))
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

out=Path('data/spawn-data.js')
out.parent.mkdir(parents=True,exist_ok=True)
meta={
    'source':SPAWN_URL,
    'updated_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
    'spawn_rows':len(rows),
    'species':len({r['name'] for r in rows}),
}
out.write_text('window.COBBLEMON_SPAWN_META='+json.dumps(meta,separators=(',',':'))+';\nwindow.COBBLEMON_SPAWN_DATA='+json.dumps(rows,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print(json.dumps(meta,indent=2))
