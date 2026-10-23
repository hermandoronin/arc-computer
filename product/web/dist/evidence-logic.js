export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function safeURL(value) {
  try { const url = new URL(value); return url.protocol === 'https:' ? url.href : '#'; } catch { return '#'; }
}
export function matches(record, query = '') {
  const normalize = s => String(s).normalize('NFKC').toLocaleLowerCase('ru').replace(/ё/g, 'е');
  const haystack = normalize(JSON.stringify(record));
  return normalize(query).trim().split(/\s+/).every(term => haystack.includes(term));
}
export function readiness(route, inventory = {}) {
  const rows = route.requirements.map(req => {
    const raw = Number(inventory[req.id]);
    const have = Number.isFinite(raw) ? Math.max(0, Math.min(req.qty, Math.floor(raw))) : 0;
    return {...req, have, missing: req.qty - have};
  });
  return {rows, have: rows.filter(r => !r.missing).length, total: rows.length,
    complete: rows.length > 0 && rows.every(r => !r.missing)};
}
export function normalizeCases(input) {
  if (!Array.isArray(input)) return [];
  return input.slice(0, 100).filter(c => c && typeof c === 'object' && typeof c.model === 'string' && c.model.trim())
    .map(c => ({model:c.model.slice(0,160), board:String(c.board||'').slice(0,160),
      url:safeURL(c.url)==='#'?'':safeURL(c.url), note:String(c.note||'').slice(0,2500)}));
}
export function planText(route, inventory = {}, sources = []) {
  const {rows} = readiness(route, inventory);
  const links = sources.filter(s => route.source_ids.includes(s.id));
  return `ARC — ${route.title}\n${route.result}\n\nСтатус: маршрут по документации; на стенде ARC не испытан.\n\nКОМПЛЕКТ\n${rows.map(r=>`${r.name} × ${r.qty}; есть ${r.have}; осталось ${r.missing}\n  Найти: ${r.where}\n  Проверить: ${r.check}`).join('\n')}\n\nПОДКЛЮЧЕНИЕ\n${route.wiring.map(r=>r.join(' → ')).join('\n')}\n\nШАГИ\n${route.steps.map((s,i)=>`${i+1}. ${s[0]}\n${s[1]}\nУспех: ${s[2]}`).join('\n\n')}${route.commands?'\n\nКОМАНДЫ\n'+route.commands:''}${route.firmware?'\n\nПРОШИВКА\n'+route.firmware.title+'\n'+route.firmware.config:''}\n\nПРОВЕРКА\n${route.tests.join('\n')}\n\nОГРАНИЧЕНИЯ\n${route.limits.join('\n')}\n\nИСТОЧНИКИ\n${links.map(s=>s.title+'\n'+s.url).join('\n\n')}\n`;
}
