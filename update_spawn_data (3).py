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
            rows.append({'name':unescape(cells[0]),'rarity':unescape(cells[1]),'biomes':unescape(cells[2]),'types':[],'groups':[],'pokemon_id':None,'forms':[],'catch_rate':None,'encounter':{},'evolutions':[]})
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
pokemon_evolution=csv_rows('pokemon_evolution.csv')
evolution_triggers=csv_rows('evolution_triggers.csv')
items=csv_rows('items.csv')
locations=csv_rows('locations.csv')
moves=csv_rows('moves.csv')
capture_rate_by_species={int(r['id']):int(r['capture_rate']) for r in species if r.get('capture_rate') not in (None,'')}

species_name_by_id={int(r['id']):r['identifier'].replace('-',' ').title() for r in species}
trigger_name_by_id={int(r['id']):r['identifier'].replace('-',' ').title() for r in evolution_triggers}
item_name_by_id={int(r['id']):r['identifier'].replace('-',' ').title() for r in items}
location_name_by_id={int(r['id']):r['identifier'].replace('-',' ').title() for r in locations}
move_name_by_id={int(r['id']):r['identifier'].replace('-',' ').title() for r in moves}
type_name_by_id={int(r['id']):r['identifier'].replace('-',' ').title() for r in csv_rows('types.csv')}

def _int_or_none(v):
    try:
        return int(v) if v not in (None,'') else None
    except Exception:
        return None

def build_evolution_map():
    """
    Build outgoing evolutions from pokemon_species.evolves_from_species_id first.
    This guarantees that a known species relationship is never lost just because
    pokemon_evolution.csv is missing/changed. Then enrich each relationship with
    trigger/level/item/condition details when available.
    """
    out={}

    # Index evolution-detail rows by the species they evolve INTO.
    detail_by_evolved={}
    for r in pokemon_evolution:
        eid=_int_or_none(r.get('evolved_species_id'))
        if eid is not None:
            detail_by_evolved.setdefault(eid,[]).append(r)

    # The species table is the authoritative parent -> child relationship.
    for child in species:
        child_id=_int_or_none(child.get('id'))
        parent_id=_int_or_none(child.get('evolves_from_species_id'))
        if child_id is None or parent_id is None:
            continue

        detail_rows=detail_by_evolved.get(child_id) or [None]

        for r in detail_rows:
            conds=[]
            trigger_name="Evolution"
            min_level=None

            if r:
                min_level=_int_or_none(r.get('minimum_level'))
                if min_level is not None:
                    conds.append(f"Level {min_level}")

                trigger_item=_int_or_none(r.get('trigger_item_id'))
                if trigger_item is not None:
                    conds.append(f"Use {item_name_by_id.get(trigger_item,'Item')}")

                held_item=_int_or_none(r.get('held_item_id'))
                if held_item is not None:
                    conds.append(f"Holding {item_name_by_id.get(held_item,'Item')}")

                min_happiness=_int_or_none(r.get('minimum_happiness'))
                if min_happiness is not None:
                    conds.append(f"Friendship ≥ {min_happiness}")

                min_beauty=_int_or_none(r.get('minimum_beauty'))
                if min_beauty is not None:
                    conds.append(f"Beauty ≥ {min_beauty}")

                min_affection=_int_or_none(r.get('minimum_affection'))
                if min_affection is not None:
                    conds.append(f"Affection ≥ {min_affection}")

                tod=(r.get('time_of_day') or '').strip()
                if tod:
                    conds.append(tod.title())

                known_move=_int_or_none(r.get('known_move_id'))
                if known_move is not None:
                    conds.append(f"Knows {move_name_by_id.get(known_move,'required move')}")

                known_move_type=_int_or_none(r.get('known_move_type_id'))
                if known_move_type is not None:
                    conds.append(f"Knows a {type_name_by_id.get(known_move_type,'required')}-type move")

                location_id=_int_or_none(r.get('location_id'))
                if location_id is not None:
                    conds.append(f"At {location_name_by_id.get(location_id,'specific location')}")

                party_species=_int_or_none(r.get('party_species_id'))
                if party_species is not None:
                    conds.append(f"{species_name_by_id.get(party_species,'Required Pokémon')} in party")

                party_type=_int_or_none(r.get('party_type_id'))
                if party_type is not None:
                    conds.append(f"{type_name_by_id.get(party_type,'Required')}-type Pokémon in party")

                trade_species=_int_or_none(r.get('trade_species_id'))
                if trade_species is not None:
                    conds.append(f"Trade for {species_name_by_id.get(trade_species,'specific Pokémon')}")

                if str(r.get('needs_overworld_rain','')).lower() in ('1','true'):
                    conds.append("While raining")

                if str(r.get('turn_upside_down','')).lower() in ('1','true'):
                    conds.append("Hold device upside down")

                rel=_int_or_none(r.get('relative_physical_stats'))
                if rel is not None:
                    conds.append("Attack > Defense" if rel==1 else "Attack < Defense" if rel==-1 else "Attack = Defense")

                trigger=_int_or_none(r.get('evolution_trigger_id'))
                trigger_name=trigger_name_by_id.get(trigger,'Evolution')

            # Never claim "no evolution" just because condition detail was absent.
            if not conds:
                conds.append(trigger_name if trigger_name!="Evolution" else "Evolution requirement unavailable")

            entry={
                'to_species_id':child_id,
                'to_name':species_name_by_id.get(child_id,str(child_id)),
                'trigger':trigger_name,
                'minimum_level':min_level,
                'conditions':conds
            }

            # De-duplicate identical branches.
            bucket=out.setdefault(parent_id,[])
            sig=(entry['to_species_id'],tuple(entry['conditions']))
            if not any((e['to_species_id'],tuple(e.get('conditions',[])))==sig for e in bucket):
                bucket.append(entry)

    return out

evolution_map=build_evolution_map()

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
        r['evolutions']=evolution_map.get(int(sid),[])

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
