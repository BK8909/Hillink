/* A02: reorder existing rendered cards; customer IDs and handlers stay intact. */
(() => {
  'use strict';
  if (window.A02CatalogAssets) return;
  function displayNumber(card) {
    const label=card.querySelector('.lb-cid b') || card.querySelector('.lb-thid');
    const match=/^\s*(?:No\.?\s*|P-)?(\d+)\b/i.exec(label && label.textContent || '');
    return match ? Number(match[1]) : Number.POSITIVE_INFINITY;
  }
  function sortVisibleCards() {
    const root=document.getElementById('libraryView');
    if (!root) return;
    root.querySelectorAll('.lb-main > .lb-grid').forEach(grid => {
      const cards=[...grid.children].filter(node => node.matches('.lb-card[data-id],.lb-card[data-c]'));
      const ordered=[...cards].sort((a,b) => {
        const x=displayNumber(a), y=displayNumber(b);
        return x===y ? 0 : x<y ? -1 : 1;
      });
      if (ordered.some((card,i) => card!==cards[i])) ordered.forEach(card => grid.appendChild(card));
    });
  }
  const original=typeof libGrid==='function' ? libGrid : null;
  if (original) libGrid=function(...args) {
    const result=original.apply(this,args);
    if (result && typeof result.then==='function') return result.then(value => {sortVisibleCards();return value;});
    sortVisibleCards();
    return result;
  };
  window.A02CatalogAssets=Object.freeze({version:'w44-a02-catalog-order-v1',displayNumber,sortVisibleCards});
  sortVisibleCards();
})();
