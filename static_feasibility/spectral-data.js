/* Read-only loader for exported genuine spectra; no data are synthesized here. */
window.CronoscopeSpectra={
  index:()=>fetch('demo/spectra/index.json').then(response=>{if(!response.ok)throw new Error('Spectral export index unavailable');return response.json()}),
  spectrum:id=>fetch(`demo/spectra/${encodeURIComponent(id)}.json`).then(response=>{if(!response.ok)throw new Error('Genuine spectral export unavailable');return response.json()})
};
