export function normalizeInventory(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return {};
  const result={};
  for(const [id,value] of Object.entries(input)) {
    const count=Number(value);
    if (/^(part|cmp|comp):[\w.:-]+$/.test(id) && Number.isInteger(count) && count>0 && count<=999) result[id]=count;
  }
  return result;
}
export function matchProject(project, inventory) {
  // Aggregate duplicate requirements before comparing; inventory isn't consumed across alternative projects.
  const required=new Map();
  for(const item of project.bom||[]) {
    const qty=Number(item.quantity);
    if(Number.isFinite(qty)&&qty>0) required.set(item.id,(required.get(item.id)||0)+qty);
  }
  const rows=[...required].map(([id,quantity])=>({id,quantity,have:Math.min(Number(inventory[id])||0,quantity),missing:Math.max(0,quantity-(Number(inventory[id])||0))}));
  const total=rows.reduce((sum,x)=>sum+x.quantity,0);
  const have=rows.reduce((sum,x)=>sum+x.have,0);
  return {rows,total,have,score:total?Math.round(have/total*100):0,complete:total>0&&have===total,missing:rows.filter(x=>x.missing>0)};
}
export function searchText(record, query) {
  const words=query.toLocaleLowerCase('ru').trim().split(/\s+/).filter(Boolean);
  const hay=JSON.stringify(record).toLocaleLowerCase('ru');
  return words.every(w=>hay.includes(w));
}
