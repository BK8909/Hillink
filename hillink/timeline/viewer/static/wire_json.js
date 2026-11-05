(function(root){
'use strict';
function unpack(value){
 if(!value||value.hillink_transport!=='HILLINK_JSON_DAG_V1')return value;
 if(!Array.isArray(value.nodes)||value.nodes.length>2000000)throw Error('잘못된 실행 전송 자료입니다.');
 const built=[];
 function item(v){
  if(v===null||typeof v!=='object')return v;
  if(Array.isArray(v)||Object.keys(v).length!==1||!Number.isInteger(v.r)||v.r<0||v.r>=built.length)throw Error('잘못된 실행 참조입니다.');
  return built[v.r];
 }
 for(const node of value.nodes){
  if(!Array.isArray(node)||node.length!==2||!['d','a'].includes(node[0])||!Array.isArray(node[1]))throw Error('잘못된 실행 노드입니다.');
  let out;
  if(node[0]==='a')out=node[1].map(item);
  else{out={};for(const pair of node[1]){
   if(!Array.isArray(pair)||pair.length!==2||typeof pair[0]!=='string'||Object.hasOwn(out,pair[0]))throw Error('잘못된 실행 키입니다.');
   Object.defineProperty(out,pair[0],{value:item(pair[1]),enumerable:true,writable:true,configurable:true});
  }}
  built.push(out);
 }
 return item(value.root);
}
root.HLWireJSON={unpack};if(typeof module!=='undefined')module.exports={unpack};
})(typeof window!=='undefined'?window:globalThis);
