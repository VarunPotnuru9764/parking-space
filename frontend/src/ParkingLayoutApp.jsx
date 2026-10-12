import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiRequest } from "./api.js";

const clone = (value) => JSON.parse(JSON.stringify(value));
const defaultName = (index) => `P${String(index + 1).padStart(2, "0")}`;
const makeId = () => globalThis.crypto?.randomUUID?.() ?? `manual-${Date.now()}-${Math.random().toString(36).slice(2)}`;

function renumberByPosition(entries) {
  const included = entries.filter((entry) => entry.included);
  const centers = new Map(included.map((entry) => [entry.id, entry.polygon.reduce((sum, [x, y]) => [sum[0] + x / entry.polygon.length, sum[1] + y / entry.polygon.length], [0, 0]) ]));
  const ordered = [...included].sort((a, b) => {
    const [ax, ay] = centers.get(a.id), [bx, by] = centers.get(b.id);
    return ay - by || ax - bx || a.id.localeCompare(b.id);
  });
  const names = new Map(ordered.map((entry, index) => [entry.id, defaultName(index)]));
  return entries.map((entry) => names.has(entry.id) ? { ...entry, slot_number: names.get(entry.id) } : entry);
}

function segmentsIntersect(a, b, c, d) {
  const orient = (p, q, r) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const abC = orient(a, b, c), abD = orient(a, b, d), cdA = orient(c, d, a), cdB = orient(c, d, b);
  const eps = 1e-8;
  const on = (p, q, r) => q[0] >= Math.min(p[0], r[0]) - eps && q[0] <= Math.max(p[0], r[0]) + eps && q[1] >= Math.min(p[1], r[1]) - eps && q[1] <= Math.max(p[1], r[1]) + eps;
  if (abC * abD < -eps && cdA * cdB < -eps) return true;
  return (Math.abs(abC) <= eps && on(a, c, b)) || (Math.abs(abD) <= eps && on(a, d, b)) || (Math.abs(cdA) <= eps && on(c, a, d)) || (Math.abs(cdB) <= eps && on(c, b, d));
}

function validateEntries(entries, dimensions) {
  const spaces = entries.filter((space) => space.included);
  const errors = [];
  if (!spaces.length) errors.push("Keep or add at least one parking space.");
  const names = new Set();
  for (const space of spaces) {
    const name = space.slot_number.trim();
    if (!name) errors.push(`${space.label}: enter a slot name.`);
    else if (names.has(name.toLocaleLowerCase())) errors.push(`Slot name “${name}” is duplicated.`);
    names.add(name.toLocaleLowerCase());
    if (!Array.isArray(space.polygon) || space.polygon.length < 3) {
      errors.push(`${space.label}: a polygon needs at least three vertices.`);
      continue;
    }
    const points = space.polygon;
    if (points.some((point) => !Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite))) {
      errors.push(`${space.label}: vertices must be finite x/y coordinates.`);
      continue;
    }
    if (dimensions && points.some(([x, y]) => x < 0 || y < 0 || x > dimensions.width || y > dimensions.height)) {
      errors.push(`${space.label}: a vertex falls outside the source image.`);
    }
    const twiceArea = points.reduce((area, point, index) => {
      const next = points[(index + 1) % points.length];
      return area + point[0] * next[1] - next[0] * point[1];
    }, 0);
    if (Math.abs(twiceArea) < 1) errors.push(`${space.label}: polygon has no usable area.`);
    for (let first = 0; first < points.length; first += 1) {
      const nextPoint = points[(first + 1) % points.length];
      if (points[first][0] === nextPoint[0] && points[first][1] === nextPoint[1]) errors.push(`${space.label}: neighboring vertices must be distinct.`);
      for (let second = first + 1; second < points.length; second += 1) {
        if (second === first + 1 || (first === 0 && second === points.length - 1)) continue;
        if (segmentsIntersect(points[first], points[(first + 1) % points.length], points[second], points[(second + 1) % points.length])) {
          errors.push(`${space.label}: polygon crosses itself.`);
          first = points.length;
          break;
        }
      }
    }
  }
  return { spaces, errors };
}

export default function ParkingLayoutApp({ initialLotSlug, lots = [] }) {
  const [lotSlug, setLotSlug] = useState(initialLotSlug || "simulator");
  const [cameraId, setCameraId] = useState("default");
  const [imageUrl, setImageUrl] = useState("");
  const [imageFile, setImageFile] = useState(null);
  const [dimensions, setDimensions] = useState(null);
  const [entries, setEntries] = useState([]);
  const entriesRef = useRef(entries);
  const [past, setPast] = useState([]);
  const [future, setFuture] = useState([]);
  const [sourceCandidates, setSourceCandidates] = useState([]);
  const [bundleDimensions, setBundleDimensions] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [drawing, setDrawing] = useState(false);
  const [draft, setDraft] = useState([]);
  const [dragging, setDragging] = useState(null);
  const dragBefore = useRef(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [savedToast, setSavedToast] = useState(false);
  const [generating, setGenerating] = useState(false);
  const imageInput = useRef(null);
  const bundleInput = useRef(null);
  const svgRef = useRef(null);

  useEffect(() => { entriesRef.current = entries; }, [entries]);
  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl); }, [imageUrl]);
  useEffect(() => { if (initialLotSlug) setLotSlug(initialLotSlug); }, [initialLotSlug]);

  const includedEntries = useMemo(() => entries.filter((entry) => entry.included), [entries]);
  const validation = useMemo(() => {
    const result = validateEntries(entries, dimensions);
    if (bundleDimensions && dimensions && (bundleDimensions.width !== dimensions.width || bundleDimensions.height !== dimensions.height)) {
      result.errors.unshift(`Source image size (${dimensions.width} × ${dimensions.height}) does not match detector image size (${bundleDimensions.width} × ${bundleDimensions.height}).`);
    }
    return result;
  }, [entries, dimensions, bundleDimensions]);
  const selected = entries.find((entry) => entry.id === selectedId);

  const commit = useCallback((next) => {
    setPast((old) => [...old.slice(-99), clone(entriesRef.current)]);
    setEntries(next);
    entriesRef.current = next;
    setFuture([]);
    setError("");
  }, []);

  const undo = useCallback(() => {
    if (!past.length) return;
    const previous = past[past.length - 1];
    setFuture((next) => [clone(entriesRef.current), ...next].slice(0, 100));
    setPast(past.slice(0, -1));
    entriesRef.current = previous;
    setEntries(previous);
    setError("");
  }, [past]);

  const redo = useCallback(() => {
    if (!future.length) return;
    const next = future[0];
    setPast((history) => [...history.slice(-99), clone(entriesRef.current)]);
    setFuture(future.slice(1));
    entriesRef.current = next;
    setEntries(next);
    setError("");
  }, [future]);

  useEffect(() => {
    const onKeyDown = (event) => {
      const target = event.target;
      const typing = target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
      if (typing) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) redo(); else undo();
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") {
        event.preventDefault(); redo();
      } else if (event.key === "Escape" && drawing) {
        setDraft([]); setDrawing(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [undo, redo, drawing]);

  const loadImage = (file) => {
    if (!file) return;
    setImageFile(file);
    const nextUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      setImageUrl((old) => { if (old) URL.revokeObjectURL(old); return nextUrl; });
      setDimensions({ width: image.naturalWidth, height: image.naturalHeight });
      setNotice(`Loaded ${file.name} · ${image.naturalWidth} × ${image.naturalHeight}px`);
      setError("");
    };
    image.onerror = () => { URL.revokeObjectURL(nextUrl); setError("Could not read that image file."); };
    image.src = nextUrl;
  };

  const generateCandidates = async () => {
    if (!imageFile) { setError("Choose a parking image first."); return; }
    if (!lotSlug) { setError("Choose the parking lot for this image."); return; }
    setGenerating(true); setError(""); setNotice("");
    try {
      const bundle = await apiRequest(`/layouts/${encodeURIComponent(lotSlug)}/${encodeURIComponent(cameraId)}/candidates`, {
        method: "POST", body: imageFile,
      });
      const imported = bundle.detector_candidates.map((candidate, index) => ({
        id: candidate.stable_id || `detector-${candidate.candidate_id}`,
        detectorCandidateId: candidate.candidate_id,
        label: `Candidate ${candidate.candidate_id}`,
        source: "detector",
        className: candidate.class_name || "parking-space",
        confidence: candidate.confidence,
        polygon: clone(candidate.polygon),
        slot_number: defaultName(index),
        included: true,
      }));
      setEntries(imported); entriesRef.current = imported;
      setPast([]); setFuture([]); setSourceCandidates(clone(bundle.detector_candidates));
      setBundleDimensions({ width: bundle.image_width, height: bundle.image_height });
      setSelectedId(imported[0]?.id ?? null);
      setNotice(imported.length ? `Generated ${imported.length} candidates. Review the outlines, then download the JSON bundle or save the reviewed layout.` : "No parking spaces were detected. Try a clearer overview image or draw spaces manually.");
    } catch (err) { setError(err.message || "Could not generate parking layout candidates."); }
    finally { setGenerating(false); }
  };

  const downloadBundle = () => {
    if (!dimensions || !sourceCandidates.length) return;
    const bundle = {
      format: "parking-layout-review-v1", lot_slug: lotSlug, camera_id: cameraId,
      image_filename: imageFile?.name || "parking-layout-image",
      image_width: dimensions.width, image_height: dimensions.height,
      detector_candidates: sourceCandidates,
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url; link.download = `${lotSlug}-${cameraId}-layout-review.json`; link.click();
    URL.revokeObjectURL(url);
  };

  const importBundle = async (file) => {
    if (!file) return;
    try {
      const bundle = JSON.parse(await file.text());
      if (bundle.format !== "parking-layout-review-v1" || !Array.isArray(bundle.detector_candidates)) {
        throw new Error("This file is not a test_layout.py review bundle.");
      }
      const candidateIds = new Set();
      for (const candidate of bundle.detector_candidates) {
        const id = candidate.stable_id || `detector-${candidate.candidate_id}`;
        if (!Number.isInteger(candidate.candidate_id) || candidateIds.has(id) || !Array.isArray(candidate.polygon) || candidate.polygon.length < 3 || candidate.polygon.some((point) => !Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite))) {
          throw new Error("The review bundle contains an invalid or duplicate candidate ID/polygon.");
        }
        candidateIds.add(id);
      }
      const imported = bundle.detector_candidates.map((candidate, index) => ({
        id: candidate.stable_id || `detector-${candidate.candidate_id}`,
        detectorCandidateId: candidate.candidate_id,
        label: `Candidate ${candidate.candidate_id}`,
        source: "detector",
        className: candidate.class_name || "parking-space",
        confidence: candidate.confidence,
        polygon: clone(candidate.polygon),
        slot_number: defaultName(index),
        included: true,
      }));
      setEntries(imported);
      entriesRef.current = imported;
      setPast([]); setFuture([]); setSourceCandidates(clone(bundle.detector_candidates));
      setBundleDimensions(bundle.image_width && bundle.image_height ? { width: bundle.image_width, height: bundle.image_height } : null);
      setSelectedId(imported[0]?.id ?? null);
      setLotSlug(bundle.lot_slug || lotSlug);
      setCameraId(bundle.camera_id || cameraId);
      setNotice(`Imported ${imported.length} detector candidates. Choose the matching original image to edit.`);
      setError("");
    } catch (err) { setError(err.message || "Could not import candidate bundle."); }
  };

  const loadSavedLayout = async () => {
    setError(""); setNotice("");
    try {
      const data = await apiRequest(`/layouts/${encodeURIComponent(lotSlug)}/${encodeURIComponent(cameraId)}`);
      const loaded = data.spaces.map((space) => ({
        id: `saved:${space.slot_number}`, detectorCandidateId: null, label: space.slot_number,
        source: "saved", className: "saved layout", polygon: clone(space.polygon),
        slot_number: space.slot_number, included: true,
      }));
      setEntries(loaded); entriesRef.current = loaded; setPast([]); setFuture([]);
      setSourceCandidates([]); setSelectedId(loaded[0]?.id ?? null);
      setBundleDimensions(null);
      setNotice(`Loaded ${loaded.length} saved spaces for ${lotSlug} / ${cameraId}.`);
    } catch (err) { setError(err.message || "Could not load the saved layout."); }
  };

  const getImagePoint = (event) => {
    if (!svgRef.current || !dimensions) return null;
    const point = svgRef.current.createSVGPoint();
    point.x = event.clientX; point.y = event.clientY;
    const local = point.matrixTransform(svgRef.current.getScreenCTM().inverse());
    return [
      Math.max(0, Math.min(dimensions.width, local.x)),
      Math.max(0, Math.min(dimensions.height, local.y)),
    ];
  };

  const handleCanvasClick = (event) => {
    if (!drawing) return;
    const point = getImagePoint(event);
    if (point) setDraft((old) => [...old, point]);
  };

  const finishPolygon = () => {
    if (draft.length < 3) { setError("Add at least three vertices to finish a space."); return; }
    const entry = {
      id: makeId(), detectorCandidateId: null, label: "Manual space", source: "manual",
      className: "manually drawn", polygon: clone(draft), slot_number: "", included: true,
    };
    commit(renumberByPosition([...entriesRef.current, entry]));
    setSelectedId(entry.id); setDraft([]); setDrawing(false);
    setNotice("Manual space added and spaces renumbered by image position. Drag its vertices to refine the outline.");
  };

  const copySelectedSpace = () => {
    if (!selected) { setError("Select a space to copy first."); return; }
    if (!dimensions) { setError("Choose the source image before placing a copied space."); return; }
    const copy = {
      ...clone(selected), id: makeId(), detectorCandidateId: null,
      label: "Copied space", source: "manual", className: "copied polygon",
      slot_number: "", polygon: selected.polygon.map(([x, y]) => [Math.min(dimensions.width, x + 12), Math.min(dimensions.height, y + 12)]), included: true,
    };
    const next = renumberByPosition([...entriesRef.current, copy]);
    commit(next);
    setSelectedId(copy.id);
    setError("");
    setNotice("Copied polygon added. Select and drag its outline to move it into position.");
  };

  const beginPolygonDrag = (event, entry) => {
    if (drawing || entry.id !== selectedId || dragging) return;
    event.preventDefault(); event.stopPropagation();
    const startPoint = getImagePoint(event);
    if (!startPoint) return;
    dragBefore.current = clone(entriesRef.current);
    setDragging({ id: entry.id, kind: "polygon", startPoint, initialPolygon: clone(entry.polygon) });
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const changeName = (id, value) => {
    const next = entriesRef.current.map((entry) => entry.id === id ? { ...entry, slot_number: value } : entry);
    commit(next);
  };

  const removeEntry = (id) => {
    const next = entriesRef.current.filter((entry) => entry.id !== id);
    commit(next);
    if (selectedId === id) setSelectedId(next.find((entry) => entry.included)?.id ?? null);
  };

  const beginVertexDrag = (event, entry, vertexIndex) => {
    event.preventDefault(); event.stopPropagation();
    dragBefore.current = clone(entriesRef.current);
    setDragging({ id: entry.id, vertexIndex });
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveVertex = (event, entry) => {
    if (!dragging || dragging.id !== entry.id) return;
    const point = getImagePoint(event);
    if (!point) return;
    const next = entriesRef.current.map((item) => {
      if (item.id !== entry.id) return item;
      if (dragging.kind === "polygon") {
        const dx = point[0] - dragging.startPoint[0], dy = point[1] - dragging.startPoint[1];
        return { ...item, polygon: dragging.initialPolygon.map(([x, y]) => [Math.max(0, Math.min(dimensions.width, x + dx)), Math.max(0, Math.min(dimensions.height, y + dy))]) };
      }
      const polygon = item.polygon.map((vertex, index) => index === dragging.vertexIndex ? point : vertex);
      return { ...item, polygon };
    });
    entriesRef.current = next; setEntries(next);
  };

  const endVertexDrag = () => {
    if (!dragging) return;
    const before = dragBefore.current;
    if (dragging.kind === "polygon") {
      const next = renumberByPosition(entriesRef.current);
      entriesRef.current = next; setEntries(next);
      if (before && JSON.stringify(before) !== JSON.stringify(next)) {
        setPast((old) => [...old.slice(-99), before]); setFuture([]);
      }
    } else if (before && JSON.stringify(before) !== JSON.stringify(entriesRef.current)) {
      setPast((old) => [...old.slice(-99), before]); setFuture([]);
    }
    dragBefore.current = null; setDragging(null);
  };

  const saveLayout = async () => {
    setError(""); setNotice("");
    if (!dimensions) { setError("Choose the original image before saving so polygon bounds can be checked."); return; }
    if (!imageFile) { setError("Choose the original reference photo again before saving this layout."); return; }
    const result = validateEntries(entriesRef.current, dimensions);
    if (result.errors.length) { setError(result.errors.join(" ")); return; }
    try {
      const layout = { spaces: result.spaces.map((space) => ({
        slot_number: space.slot_number.trim(),
        polygon: space.polygon.map(([x, y]) => [Math.round(x), Math.round(y)]),
      })) };
      const bounds = new URLSearchParams({ image_width: String(dimensions.width), image_height: String(dimensions.height) });
      await apiRequest(`/layouts/${encodeURIComponent(lotSlug)}/${encodeURIComponent(cameraId)}?${bounds}`, {
        method: "PUT", body: JSON.stringify(layout),
      });
      await apiRequest(`/layouts/${encodeURIComponent(lotSlug)}/${encodeURIComponent(cameraId)}/reference`, {
        method: "POST", body: imageFile,
      });
      setNotice("");
      setSavedToast(true);
      window.setTimeout(() => setSavedToast(false), 2800);
    } catch (err) { setError(err.message || "Could not save the layout."); }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-mark">P</div>
        <div className="brand-copy"><strong>Parking Layout</strong><span>Configuration tool</span></div>
        <div className="topbar-spacer" />
        <div className="scope-pill"><span className="scope-dot" />LOT-SCOPED EDITOR</div>
      </header>

      <main className="workspace">
        {savedToast && <div className="saved-toast" role="status">✓ <span>Layout and reference photo saved successfully</span></div>}
        <section className="intro-row">
          <div><p className="eyebrow">LAYOUT REVIEW</p><h1>Review parking spaces</h1><p className="subhead">Correct detector results against the source image, then save a camera-specific layout.</p></div>
          <div className="history-actions">
            <button className="button secondary" onClick={undo} disabled={!past.length} title="Undo (Ctrl+Z)">↶ <span>Undo</span></button>
            <button className="button secondary" onClick={redo} disabled={!future.length} title="Redo (Ctrl+Shift+Z)">↷ <span>Redo</span></button>
          </div>
        </section>

        <section className="scope-card">
          <label className="field"><span>Parking lot</span>{lots.length ? <select value={lotSlug} onChange={(e) => setLotSlug(e.target.value)}><option value="">Choose a parking lot</option>{lots.map((lot) => <option key={lot.lot_id} value={lot.slug}>{lot.name}</option>)}</select> : <input value={lotSlug} onChange={(e) => setLotSlug(e.target.value)} placeholder="campus-west" />}</label>
          <label className="field"><span>Camera ID</span><input value={cameraId} onChange={(e) => setCameraId(e.target.value)} placeholder="gate-a" /></label>
          <button className="button secondary load-button" onClick={loadSavedLayout}>Load saved layout</button>
        </section>

        <section className="import-row">
          <div className="import-card">
            <div className="import-icon">▧</div><div className="import-copy"><strong>Original image</strong><span>{dimensions ? `${dimensions.width} × ${dimensions.height}px` : "Choose the exact frame used by the detector"}</span></div>
            <input ref={imageInput} type="file" accept="image/*" hidden onChange={(e) => loadImage(e.target.files?.[0])} />
            <button className="button secondary" onClick={() => imageInput.current?.click()}>{imageUrl ? "Change image" : "Choose image"}</button>
          </div>
          <div className="import-card">
            <div className="import-icon bundle">#</div><div className="import-copy"><strong>Generate layout JSON</strong><span>{sourceCandidates.length ? `${sourceCandidates.length} candidates ready to review` : "Run the parking-space detector on this image"}</span></div>
            <button className="button primary" onClick={generateCandidates} disabled={!imageFile || !lotSlug || generating}>{generating ? "Detecting…" : "Generate candidates"}</button>
          </div>
        </section>
        {sourceCandidates.length > 0 && <div className="bundle-actions"><span>Candidate bundle ready for {lotSlug}</span><button className="button secondary" onClick={downloadBundle}>Download JSON bundle</button></div>}

        {notice && <div className="notice" role="status"><span>✓</span>{notice}</div>}
        {error && <div className="error-banner" role="alert"><span>!</span>{error}</div>}

        <div className="editor-grid">
          <section className="canvas-panel">
            <div className="panel-heading">
              <div><h2>Source image</h2><p>Drag corner handles to refine an outline.</p></div>
              <div className="canvas-count"><b>{includedEntries.length}</b> spaces</div>
            </div>
            <div className={`canvas-wrap ${drawing ? "drawing-mode" : ""}`} style={dimensions ? { aspectRatio: `${dimensions.width} / ${dimensions.height}`, minHeight: 0 } : undefined}>
              {imageUrl && dimensions ? (
                <>
                  <img src={imageUrl} alt="Original parking image" draggable="false" />
                  <svg ref={svgRef} viewBox={`0 0 ${dimensions.width} ${dimensions.height}`} role="application" aria-label="Parking space polygon editor" onClick={handleCanvasClick}>
                    {entries.filter((entry) => entry.included).map((entry, index) => {
                      const isSelected = entry.id === selectedId;
                      const points = entry.polygon.map(([x, y]) => `${x},${y}`).join(" ");
                      const center = entry.polygon.reduce((sum, point) => [sum[0] + point[0] / entry.polygon.length, sum[1] + point[1] / entry.polygon.length], [0, 0]);
                      return <g key={entry.id} className={`space-shape ${isSelected ? "selected" : ""}`}>
                        <polygon points={points} onClick={(event) => { if (!drawing && !dragging) { event.stopPropagation(); setSelectedId(entry.id); } }} onPointerDown={(event) => beginPolygonDrag(event, entry)} onPointerMove={(event) => moveVertex(event, entry)} onPointerUp={endVertexDrag} onPointerCancel={endVertexDrag} />
                        {isSelected && <g className="space-label" transform={`translate(${center[0]} ${center[1]})`}><rect x="-42" y="-14" width="84" height="28" rx="7" /><text textAnchor="middle" dominantBaseline="central">#{entry.slot_number || `Space ${index + 1}`}</text></g>}
                        {isSelected && entry.polygon.map(([x, y], pointIndex) => <circle key={pointIndex} className="vertex-handle" cx={x} cy={y} r={Math.max(6, dimensions.width * 0.006)} onPointerDown={(event) => beginVertexDrag(event, entry, pointIndex)} onPointerMove={(event) => moveVertex(event, entry)} onPointerUp={endVertexDrag} onPointerCancel={endVertexDrag} />)}
                      </g>;
                    })}
                    {draft.length > 0 && <g className="draft-shape"><polyline points={draft.map(([x, y]) => `${x},${y}`).join(" ")} /><circle cx={draft[draft.length - 1][0]} cy={draft[draft.length - 1][1]} r={Math.max(5, dimensions.width * 0.005)} /></g>}
                  </svg>
                  {drawing && <div className="draw-hint">Click to add corners · finish after 3 or more</div>}
                </>
              ) : <div className="empty-canvas"><div className="empty-glyph">▧</div><strong>Choose an image to begin</strong><span>Candidate polygons are aligned to the original image dimensions.</span><button className="button primary" onClick={() => imageInput.current?.click()}>Choose source image</button></div>}
            </div>
            <div className="canvas-footer"><span><i className="legend-dot detected" />Detector candidate</span><span><i className="legend-dot manual" />Manually added</span><span className="canvas-tip">Click a space to edit its vertices</span></div>
          </section>

          <aside className="list-panel">
            <div className="panel-heading list-heading"><div><h2>Parking spaces</h2><p>Names and outlines stay in sync.</p></div><span className="total-badge">{includedEntries.length}</span></div>
            <div className="list-toolbar">
              {!drawing ? <div className="add-actions"><button className="button add-button" onClick={() => { if (!dimensions) { setError("Choose the source image before drawing a space."); return; } setDrawing(true); setDraft([]); setError(""); }}>＋ Draw new space</button><button className="button secondary copy-button" onClick={copySelectedSpace} disabled={!selected || !dimensions} title="Create a duplicate of the selected polygon, then drag its outline into place">Copy selected polygon</button></div> : <div className="draw-actions"><button className="button primary" onClick={finishPolygon} disabled={draft.length < 3}>Finish polygon</button><button className="button secondary" onClick={() => { setDrawing(false); setDraft([]); }}>Cancel</button></div>}
            </div>
            <div className="space-list">
              {entries.filter((entry) => entry.included).map((entry, index) => <article key={entry.id} className={`space-row ${entry.id === selectedId ? "active" : ""}`} onClick={() => setSelectedId(entry.id)}>
                <div className={`space-index ${entry.source === "manual" ? "manual-index" : ""}`}>{entry.source === "detector" ? entry.detectorCandidateId : index + 1}</div>
                <div className="space-fields"><label className="sr-only" htmlFor={`name-${entry.id}`}>Slot name for {entry.label}</label><input id={`name-${entry.id}`} value={entry.slot_number} onChange={(event) => changeName(entry.id, event.target.value)} onClick={(event) => event.stopPropagation()} /><span>{entry.source === "detector" ? `Detector output · ${entry.className}${Number.isFinite(entry.confidence) ? ` · ${(entry.confidence * 100).toFixed(0)}%` : ""}` : entry.source === "manual" ? "Manually added polygon" : "Loaded saved polygon"}</span></div>
                <button className="icon-button remove-button" title={`Remove ${entry.label}`} aria-label={`Remove ${entry.label}`} onClick={(event) => { event.stopPropagation(); removeEntry(entry.id); }}>×</button>
              </article>)}
              {!includedEntries.length && <div className="empty-list">No spaces yet. Import detector candidates or draw the first space.</div>}
            </div>
            <div className="validation-box">
              <div className="validation-title"><span className={validation.errors.length ? "validation-mark warning" : "validation-mark"}>{validation.errors.length ? "!" : "✓"}</span><strong>{validation.errors.length ? "Needs attention" : "Layout checks"}</strong></div>
              <ul>
                <li className={dimensions ? "checked" : "pending"}>{dimensions ? "✓" : "○"} Source image loaded</li>
                <li className={validation.spaces.length ? "checked" : "pending"}>{validation.spaces.length ? "✓" : "○"} At least one space</li>
                <li className={validation.errors.some((item) => item.includes("duplicated") || item.includes("slot name")) ? "pending" : "checked"}>{validation.errors.some((item) => item.includes("duplicated") || item.includes("slot name")) ? "○" : "✓"} Unique names and valid polygons</li>
              </ul>
              <button className="button primary save-button" onClick={saveLayout} disabled={!dimensions || validation.errors.length > 0}>Save reviewed layout</button>
              <p className="save-caption">Saves to <code>layouts/{lotSlug || "lot"}/{cameraId || "camera"}.json</code></p>
            </div>
          </aside>
        </div>
        {sourceCandidates.length > 0 && <details className="source-output"><summary>Preserved detector output <span>{sourceCandidates.length} original candidates · unchanged</span></summary><pre>{JSON.stringify(sourceCandidates, null, 2)}</pre></details>}
      </main>
      <footer className="app-footer">Parking Space Detection System <span>·</span> Reviewed polygons use the existing layout schema</footer>
    </div>
  );
}
