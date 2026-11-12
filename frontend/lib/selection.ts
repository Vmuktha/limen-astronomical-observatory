import type { Candidate } from './types';
export function selectCandidates(items:Candidate[], query:string, category:string, sort:keyof Pick<Candidate,'spectral_rank'|'image_rank'|'multimodal_rank'>){const needle=query.trim();return items.filter(item=>(category==='All'||item.triage_category===category)&&(!needle||`${item.specid} ${item.targetid}`.includes(needle))).sort((a,b)=>a[sort]-b[sort]);}
