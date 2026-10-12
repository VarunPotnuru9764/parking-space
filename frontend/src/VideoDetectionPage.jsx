import { useEffect, useRef, useState } from "react";
import { apiBlob, apiRequest } from "./api.js";

export default function VideoDetectionPage({ lots, selectedLot }) {
  const [lotSlug, setLotSlug] = useState(selectedLot?.slug || lots[0]?.slug || "");
  const [cameraId, setCameraId] = useState("default");
  const [videoFile, setVideoFile] = useState(null);
  const [job, setJob] = useState(null);
  const [frameUrl, setFrameUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const frameUrlRef = useRef("");

  useEffect(() => {
    if (selectedLot?.slug) setLotSlug(selectedLot.slug);
  }, [selectedLot?.slug]);

  useEffect(() => () => {
    if (frameUrlRef.current) URL.revokeObjectURL(frameUrlRef.current);
  }, []);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return undefined;
    let active = true;
    const refresh = async () => {
      try {
        const next = await apiRequest(`/video-detection/jobs/${job.job_id}`);
        if (active) setJob(next);
      } catch (err) {
        if (active) setError(err.message);
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 800);
    return () => { active = false; window.clearInterval(timer); };
  }, [job?.job_id, job?.status]);

  useEffect(() => {
    if (!job) return undefined;
    let active = true;
    let pending = false;
    const refreshFrame = async () => {
      if (pending) return;
      pending = true;
      try {
        const blob = await apiBlob(`/video-detection/jobs/${job.job_id}/frame`);
        if (active && blob.size > 0) {
          const nextUrl = URL.createObjectURL(blob);
          if (frameUrlRef.current) URL.revokeObjectURL(frameUrlRef.current);
          frameUrlRef.current = nextUrl;
          setFrameUrl(nextUrl);
        }
      } catch { /* no frame is available until the first frame is processed */ }
      finally { pending = false; }
    };
    refreshFrame();
    const timer = ["queued", "running"].includes(job.status)
      ? window.setInterval(refreshFrame, 250)
      : null;
    return () => {
      active = false;
      if (timer) window.clearInterval(timer);
    };
  }, [job?.job_id, job?.status]);

  const startDetection = async (event) => {
    event.preventDefault();
    if (!videoFile || !lotSlug || !cameraId.trim()) return;
    setBusy(true); setError(""); setJob(null);
    if (frameUrlRef.current) URL.revokeObjectURL(frameUrlRef.current);
    frameUrlRef.current = ""; setFrameUrl("");
    try {
      const query = new URLSearchParams({ lot_slug: lotSlug, camera_id: cameraId.trim(), filename: videoFile.name });
      const created = await apiRequest(`/video-detection/jobs?${query}`, { method: "POST", body: videoFile });
      setJob(created);
    } catch (err) { setError(err.message || "Could not start video detection."); }
    finally { setBusy(false); }
  };

  const stopDetection = async () => {
    if (!job) return;
    try {
      const next = await apiRequest(`/video-detection/jobs/${job.job_id}/stop`, { method: "POST" });
      setJob(next);
    } catch (err) { setError(err.message || "Could not stop video detection."); }
  };

  const downloadResult = async () => {
    if (!job) return;
    try {
      const blob = await apiBlob(`/video-detection/jobs/${job.job_id}/result`);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = `parking-detection-${job.lot_slug}.mp4`; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setError(err.message || "Could not download the annotated video."); }
  };

  const progress = job?.total_frames > 0
    ? Math.min(100, Math.round((job.frame_number / job.total_frames) * 100))
    : null;

  return <div className="video-detection-page">
    <div className="video-detection-heading">
      <div><p className="section-kicker">PARKING OPERATIONS</p><h1>Video detection</h1><p>Upload a recording to track occupancy and watch the annotated feed as it is processed.</p></div>
      {job && <span className={`detection-status ${job.status}`}>{job.status}</span>}
    </div>

    <form className="video-upload-panel" onSubmit={startDetection}>
      <label><span>Parking lot</span><select required value={lotSlug} onChange={(event) => setLotSlug(event.target.value)} disabled={busy || ["queued", "running"].includes(job?.status)}>
        <option value="">Choose a lot</option>{lots.map((lot) => <option key={lot.lot_id} value={lot.slug}>{lot.name}</option>)}
      </select></label>
      <label><span>Camera ID</span><input required maxLength={80} value={cameraId} onChange={(event) => setCameraId(event.target.value)} placeholder="gate-a" disabled={busy || ["queued", "running"].includes(job?.status)} /></label>
      <label className="video-file-field"><span>Video recording</span><input required type="file" accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm,.mp4,.mov,.avi,.mkv,.webm" onChange={(event) => setVideoFile(event.target.files?.[0] || null)} disabled={busy || ["queued", "running"].includes(job?.status)} /><small>{videoFile ? `${videoFile.name} · ${(videoFile.size / (1024 * 1024)).toFixed(1)} MB` : "MP4, MOV, AVI, MKV, or WebM · up to 500 MB"}</small></label>
      <button className="button button-primary" disabled={busy || !videoFile || !lotSlug || ["queued", "running"].includes(job?.status)}>{busy ? "Uploading video…" : ["completed", "stopped", "failed"].includes(job?.status) ? "Start another detection" : "Start detection"}</button>
      {job && ["queued", "running"].includes(job.status) && <button type="button" className="button button-outline" onClick={stopDetection}>Stop detection</button>}
      <p className="video-reference-note">The selected lot and camera must have a saved layout and reference photo. Occupancy is synchronized to the selected lot and cleared when detection ends or is stopped.</p>
    </form>

    {error && <div className="portal-alert" role="alert">{error}</div>}
    {job && <section className="video-live-panel">
      <div className="video-live-header"><div><h2>Annotated live feed</h2><p>{job.message}{job.frame_number > 0 ? ` · Frame ${job.frame_number.toLocaleString()}${job.total_frames > 0 ? ` of ${job.total_frames.toLocaleString()}` : ""}` : ""}</p></div><div className="video-live-actions">{progress !== null && <strong>{progress}%</strong>}{job.has_result && <button type="button" className="button button-outline" onClick={downloadResult}>Download annotated video</button>}</div></div>
      {progress !== null && <div className="video-progress"><span style={{ width: `${progress}%` }} /></div>}
      <div className="video-live-frame">{frameUrl ? <img src={frameUrl} alt="Latest annotated parking-lot video frame" /> : <div className="video-frame-placeholder">{job.status === "failed" ? job.error : "Waiting for the first annotated frame…"}</div>}</div>
      {job.status === "failed" && job.error && <div className="portal-alert" role="alert">{job.error}</div>}
      {["completed", "stopped"].includes(job.status) && <div className="video-finished-note">Detection ended. Parking-space status in {job.lot_slug} has been reset to vacant.</div>}
    </section>}
  </div>;
}
