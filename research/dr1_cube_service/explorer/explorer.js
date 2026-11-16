(()=>{"use strict";
  const $=id=>document.getElementById(id);let sample=null;let selected="IMAGE";
  const safe=value=>String(value??"Unavailable").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
  const format=value=>value===null?"Missing":Number.isInteger(value)?String(value):Number(value).toPrecision(7);
  const flatten=values=>values.reduce((items,row)=>items.concat(row),[]);
  function setStatus(message,state=""){const node=$("status");node.textContent=message;node.className=`status ${state}`;node.dataset.state=state}
  function renderGrid(){
    const grid=$("grid");if(!sample){grid.className="pixel-grid empty";grid.innerHTML="<p>Load a sample to display genuine values.</p>";return}
    const record=sample.arrays[selected],values=flatten(record.values),finite=values.filter(value=>value!==null&&Number.isFinite(value));
    const minimum=finite.length?Math.min(...finite):0,maximum=finite.length?Math.max(...finite):1,span=Math.max(maximum-minimum,Number.EPSILON);
    grid.className="pixel-grid";grid.innerHTML=values.map((value,index)=>{
      if(value===null||!Number.isFinite(value))return `<div class="pixel missing" data-index="${index}" data-value="missing">Missing</div>`;
      const bucket=selected==="FLAGS"?1:Math.max(1,Math.min(10,Math.round(1+9*((value-minimum)/span))));
      return `<div class="pixel intensity-${bucket}" data-index="${index}" data-value="${safe(value)}">${safe(format(value))}</div>`;
    }).join("");
    const missing=sample.missing_data.missing_count[selected];
    const label=selected==="IMAGE"?sample.science.image_unit:selected==="NHITS"?"contribution count":"raw integer bitmap · uninterpreted";
    $("unit").textContent=label;$("array-note").textContent=`${selected} · dtype ${record.dtype} · finite ${record.finite_count}/16 · missing values: ${missing}`;
  }
  function renderMetadata(){
    const wavelength=sample.wavelength_metadata,product=sample.product,selection=sample.selection;
    $("wavelength").innerHTML=`<dt>Channel</dt><dd>${selection.channel_zero_based}</dd><dt>Detector</dt><dd>D${wavelength.DETECTOR} / subchannel ${wavelength.SUBCHAN}</dd><dt>Central λ</dt><dd>${Number(wavelength.WAVELENGTH).toFixed(9)} µm</dd><dt>Bounds</dt><dd>${Number(wavelength.WL_MIN).toFixed(9)}–${Number(wavelength.WL_MAX).toFixed(9)} µm</dd><dt>Bandwidth</dt><dd>${Number(wavelength.BANDWIDTH).toFixed(9)} µm</dd>`;
    $("provenance").innerHTML=`<dt>Product</dt><dd>${safe(product.filename)}</dd><dt>Collection</dt><dd>${safe(product.collection)}</dd><dt>Release</dt><dd>${safe(product.release)}</dd><dt>Region</dt><dd>x ${selection.pixel_origin_zero_based[0]}, y ${selection.pixel_origin_zero_based[1]} · ${selection.width}×${selection.height}</dd><dt>Size</dt><dd>${Number(product.content_length).toLocaleString()} bytes</dd><dt>Archive</dt><dd><a href="${safe(product.official_url)}" rel="noreferrer">Official allowlisted IRSA identity</a></dd>`;
    const validation=sample.validation.public_result_replay===true?"Verified result replay; raw FITS ranges are not packaged.":sample.validation.genuine_evidence_match===true?"Genuine saved evidence matched exactly.":"Structural decoding only; genuine replay match unavailable.";
    $("validation").textContent=`${validation} External requests this call: ${sample.resources.external_requests_this_call}. Independent photometric calibration: no.`;$("validation").className=`validation ${sample.validation.genuine_evidence_match===true?"success":""}`;
  }
  async function loadSample(){
    const button=$("load-sample"),[x,y]=$("region").value.split(",").map(Number),channel=Number($("channel").value);button.disabled=true;setStatus("Loading verified cube sample…","loading");
    try{
      const response=await fetch("/api/experimental/dr1/cube/sample",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:"Npix7945_cube",channel,x,y,width:4,height:4})});
      const payload=await response.json();if(!response.ok||payload.status!=="SUCCESS")throw new Error(payload.error?.message||`Request failed with HTTP ${response.status}`);
      sample=payload;renderGrid();renderMetadata();setStatus(`Loaded channel ${channel}, region x ${x}, y ${y}. Verified values are displayed.`,"success");
    }catch(error){setStatus(`Unable to load sample: ${error.message}`,"error")}
    finally{button.disabled=false}
  }
  document.querySelectorAll("[data-array]").forEach(button=>button.addEventListener("click",()=>{selected=button.dataset.array;document.querySelectorAll("[data-array]").forEach(item=>{const active=item===button;item.classList.toggle("active",active);item.setAttribute("aria-pressed",String(active))});renderGrid()}));
  $("load-sample").addEventListener("click",loadSample);
})();
