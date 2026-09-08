import React,{useState} from "react";
import {MapContainer,TileLayer,CircleMarker,Popup,Polyline} from "react-leaflet";
const API="http://127.0.0.1:8000";
const vessels=[
["VESSEL_A",.7395,"Medium","Strong spatial, temporal and drift consistency."],
["VESSEL_D",.7264,"Medium","Good trajectory and drift agreement."],
["VESSEL_E",.6082,"Medium","Moderate multi-source evidence."],
["VESSEL_B",.5909,"Low","Weaker spatial/temporal agreement."],
["VESSEL_C",.4628,"Low","Limited evidence consistency."]
];
export default function App(){
 const [analysis,setAnalysis]=useState(null),[loading,setLoading]=useState(false),[status,setStatus]=useState("Ready"),[online,setOnline]=useState(null);
 const spill={latitude:13.10,longitude:80.30,confidence:.77,area:49.3,timestamp:"2026-09-07 10:30",severity:"Medium"};
 async function analyze(){
  setLoading(true);setStatus("Running analysis...");
  try{
   const r=await fetch(API+"/analyze-spill",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({latitude:spill.latitude,longitude:spill.longitude,timestamp:"2026-09-07T10:30:00"})});
   if(!r.ok)throw Error();
   setAnalysis(await r.json());setOnline(true);setStatus("Analysis complete");
  }catch{
   setOnline(false);setAnalysis({estimated_volume_tonnes:42,wind_speed_knots:5,current_speed_knots:1.08,drift_direction_degrees:70,affected_area_sq_km:49.3,weather_conditions:"Demo conditions"});setStatus("Demo analysis — start FastAPI for live data");
  }finally{setLoading(false)}
 }
 return <div className="app">
  <header><div><div className="eyebrow">SIH 2026 • NTRO</div><h1>Oil Spill Detection & Vessel Attribution</h1><p>Satellite SAR + AIS + drift modelling + evidence-based source ranking</p></div>
  <div className={"server "+(online===true?"on":online===false?"demo":"")}><i/> {online===true?"Backend Online":online===false?"Demo Mode":"System Ready"}</div></header>
  <main>
   <section className="stats">
    <Stat t="Spill Detected" v="YES" s="Sentinel-1 SAR"/><Stat t="Detection Confidence" v="77%" s="SAR analysis"/><Stat t="Estimated Area" v="49.3 km²" s="Detected spill region"/><Stat t="Severity" v="Medium" s="Preliminary assessment"/>
   </section>
   <section className="two">
    <div className="card mapcard"><Head title="Spill Location" sub="13.10° N, 80.30° E" badge="SAR"/>
     <div className="map"><MapContainer center={[13.1,80.3]} zoom={8} scrollWheelZoom={false}><TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/><CircleMarker center={[13.1,80.3]} radius={13} pathOptions={{color:"#b91c1c",fillColor:"#ef4444",fillOpacity:.55}}><Popup><b>Detected Oil Spill</b><br/>Confidence: 77%<br/>Area: 49.3 km²</Popup></CircleMarker>{analysis&&<Polyline positions={[[13.05,80.12],[13.08,80.22],[13.1,80.3]]} pathOptions={{color:"#2563eb",weight:3,dashArray:"8 8"}}/>}</MapContainer></div>
     <div className="coords"><span><b>Detection time</b>{spill.timestamp}</span><span><b>Coordinates</b>{spill.latitude}, {spill.longitude}</span></div>
    </div>
    <div className="card"><Head title="Spill Analysis" sub="Environmental and drift indicators" button={<button onClick={analyze} disabled={loading}>{loading?"Analyzing...":"Analyze Spill"}</button>}/>
     <div className="metrics"><Metric l="Wind speed" v={analysis?`${analysis.wind_speed_knots} kn`:"—"}/><Metric l="Ocean current" v={analysis?`${analysis.current_speed_knots} kn`:"—"}/><Metric l="Drift direction" v={analysis?`${analysis.drift_direction_degrees}°`:"—"}/><Metric l="Est. volume" v={analysis?`${analysis.estimated_volume_tonnes} t`:"—"}/><Metric l="Affected area" v={analysis?`${analysis.affected_area_sq_km} km²`:"—"}/><Metric l="Weather" v={analysis?analysis.weather_conditions:"—"}/></div>
     <div className="flow">{["SAR spill detection","Drift / hindcast analysis","Historical AIS filtering","Candidate source ranking"].map((x,i)=><div className="step" key={x}><i>{i+1}</i>{x}</div>)}</div>
     <div className="notice"><b>Important:</b> The system ranks potential source vessels from available evidence. It does not establish legal responsibility.</div>
    </div>
   </section>
   <section className="card"><Head title="Potential Source Vessels" sub="Multi-source evidence ranking" badge={status}/>
    <div className="table"><div className="row th"><span>Rank</span><span>Vessel</span><span>Score</span><span>Confidence</span><span>Reason</span></div>
    {vessels.map((v,i)=><div className="row" key={v[0]}><span><b>{i+1}</b></span><b>{v[0]}</b><span className="score"><em><u style={{width:(v[1]*100)+"%"}}/></em><b>{(v[1]*100).toFixed(2)}%</b></span><span className={"conf "+v[2].toLowerCase()}>{v[2]}</span><span className="reason">{v[3]}</span></div>)}</div>
   </section>
   <section className="evidence">{["SAR detection","AIS proximity","Drift consistency","Trajectory match"].map((x,i)=><div className="ev" key={x}><b>Evidence 0{i+1}</b><strong>{x}</strong><small>{["Oil-like dark region identified","Historical vessel activity","Current + wind movement","Candidate route agreement"][i]}</small></div>)}</section>
  </main>
  <footer>SIH 2026 MVP • Evidence-based potential source attribution • Demo data where live sources are unavailable</footer>
 </div>
}
function Head({title,sub,badge,button}){return <div className="head"><div><h2>{title}</h2><span>{sub}</span></div>{button||badge?<div>{button||<label>{badge}</label>}</div>:null}</div>}
function Stat({t,v,s}){return <div className="card stat"><span>{t}</span><strong>{v}</strong><small>{s}</small></div>}
function Metric({l,v}){return <div className="metric"><span>{l}</span><b>{v}</b></div>}