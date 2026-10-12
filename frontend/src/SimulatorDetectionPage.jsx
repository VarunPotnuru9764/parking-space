import { useEffect, useRef, useState } from "react";
import { apiBlob, apiRequest } from "./api.js";

const activeStatuses = ["starting", "running", "stopping"];

export default function SimulatorDetectionPage() {
  const [job, setJob] = useState(null);
  const [frameUrl, setFrameUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const frameUrlRef = useRef("");

  useEffect(() => () => {
    if (frameUrlRef.current) URL.revokeObjectURL(frameUrlRef.current);
  }, []);

  useEffect(() => {
    let mounted = true;
    apiRequest("/simulator-detection/jobs/active")
      .then((response) => { if (mounted && response.job) setJob(response.job); })
      .catch(() => {});
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (!job || !activeStatuses.includes(job.status)) return undefined;
    let mounted = true;
    const refresh = async () => {
      try {
        const next = await apiRequest(`/simulator-detection/jobs/${job.job_id}`);
        if (mounted) setJob(next);
      } catch (err) {
        if (mounted) setError(err.message || "Could not read simulator status.");
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 900);
    return () => { mounted = false; window.clearInterval(timer); };
  }, [job?.job_id, job?.status]);

  useEffect(() => {
    if (!job) return undefined;
    let mounted = true;
    let pending = false;
    const refreshFrame = async () => {
      if (pending) return;
      pending = true;
      try {
        const blob = await apiBlob(`/simulator-detection/jobs/${job.job_id}/frame`);
        if (mounted && blob.size) {
          const next = URL.createObjectURL(blob);
          if (frameUrlRef.current) URL.revokeObjectURL(frameUrlRef.current);
          frameUrlRef.current = next;
          setFrameUrl(next);
        }
      } catch { /* The detector publishes a frame after it starts processing. */ }
      finally { pending = false; }
    };
    refreshFrame();
    const timer = activeStatuses.includes(job.status) ? window.setInterval(refreshFrame, 250) : null;
    return () => { mounted = false; if (timer) window.clearInterval(timer); };
  }, [job?.job_id, job?.status]);

  const start = async () => {
    setBusy(true); setError(""); setJob(null);
    if (frameUrlRef.current) URL.revokeObjectURL(frameUrlRef.current);
    frameUrlRef.current = ""; setFrameUrl("");
    try {
      setJob(await apiRequest("/simulator-detection/jobs", { method: "POST" }));
    } catch (err) { setError(err.message || "Could not start simulator detection."); }
    finally { setBusy(false); }
  };

  const control = async (action, slotNumber) => {
    if (!job) return;
    setError("");
    try {
      const query = slotNumber ? `?${new URLSearchParams({ slot_number: slotNumber })}` : "";
      const next = await apiRequest(`/simulator-detection/jobs/${job.job_id}/${action}${query}`, { method: "POST" });
      if (action === "stop") setJob(next);
      else if (!next.accepted) setError(action === "spawn" ? "The simulator lot is full." : "That car is no longer parked.");
    } catch (err) { setError(err.message || "Simulator control failed."); }
  };

  const isActive = activeStatuses.includes(job?.status);
  const parkedCars = (job?.cars || []).filter((car) => car.state === "parked");

  return <div className="video-detection-page simulator-detection-page">
    <div className="video-detection-heading">
      <div><p className="section-kicker">PARKING OPERATIONS</p><h1>Simulator live detection</h1><p>Run the parking simulator and occupancy detector from the admin portal.</p></div>
      {job && <span className={`detection-status ${job.status}`}>{job.status}</span>}
    </div>

    <section className="video-upload-panel simulator-controls">
      <div className="simulator-copy"><strong>Simulator test lot</strong><span>Cars created here update the Simulator parking lot. Stop detection to clear its occupancy.</span></div>
      {!isActive
        ? <button className="button button-primary" onClick={start} disabled={busy}>{busy ? "Starting…" : "Start simulator detection"}</button>
        : <button className="button button-outline" onClick={() => control("stop")}>Stop detection</button>}
      {isActive && <>
        <button className="button button-outline" onClick={() => control("spawn")} disabled={!job?.available_spaces?.length}>Spawn car</button>
        <label className="simulator-leave-control"><span>Send a parked car out</span><select value="" onChange={(event) => { if (event.target.value) control("leave", event.target.value); }} disabled={!parkedCars.length}>
          <option value="">{parkedCars.length ? "Choose a parking space" : "No parked cars yet"}</option>
          {parkedCars.map((car) => <option key={car.slot_number} value={car.slot_number}>{car.slot_number} · {car.vehicle_id}</option>)}
        </select></label>
      </>}
      {job && <p className="video-reference-note">{job.message}{job.frame_number > 0 ? ` · ${job.frame_number.toLocaleString()} frames processed` : ""}</p>}
    </section>

    {error && <div className="portal-alert" role="alert">{error}</div>}
    {job && <section className="video-live-panel">
      <div className="video-live-header"><div><h2>Annotated live feed</h2><p>{job.status === "failed" ? job.error : "Rendered simulator frames with detected occupancy overlays"}</p></div><strong>{job.cars?.length || 0} cars in simulator</strong></div>
      <div className="video-live-frame">{frameUrl ? <img src={frameUrl} alt="Annotated simulator live feed" /> : <div className="video-frame-placeholder">{job.status === "failed" ? job.error : "Waiting for the simulator and detector to publish a frame…"}</div>}</div>
      {job.status === "failed" && job.error && <div className="portal-alert" role="alert">{job.error}</div>}
      {["completed", "stopped"].includes(job.status) && <div className="video-finished-note">Simulator detection ended. Parking-space occupancy was reset to vacant.</div>}
    </section>}
  </div>;
}
