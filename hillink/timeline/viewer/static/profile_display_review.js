// Separate render copies: LIBV, private intake and engine evidence stay intact.
(function(root){
'use strict';
const accepted = r => ['SOURCE_RECONCILED_DISPLAY_ONLY','EVIDENCE_LIMITED_DISPLAY_ONLY'].includes(r?.status);
function profile(original, review){
 if(!original || !accepted(review))return original;
 const p=JSON.parse(JSON.stringify(original)), c=review.changes;
 if(c.list_line)p.display_list_line=c.list_line;
 if(c.signature)p.display_signature=c.signature;
 p.display_review=review;
 for(const [id,text] of Object.entries(c.fact_summaries||{})){
  if(p.engine?.facts?.[id])p.engine.facts[id].gist=text;
 }
 return p;
}
function catalog(original,review){
 if(!accepted(review))return original;
 return {...original,summary:review.changes.list_line||original.summary,display_signature:review.changes.signature||'',display_review:review};
}
root.HLProfileDisplayReview={profile,catalog};
if(typeof module!=='undefined')module.exports={profile,catalog};
})(typeof window!=='undefined'?window:globalThis);
