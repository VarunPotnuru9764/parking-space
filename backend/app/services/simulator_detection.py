import json
import os
import socket
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SIMULATOR_DIR = PROJECT_ROOT / "simulator"
DETECTION_DIR = PROJECT_ROOT / "detection"
SIMULATOR_SCRIPT = SIMULATOR_DIR / "main.py"
SIMULATOR_PYTHON = SIMULATOR_DIR / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if str(DETECTION_DIR) not in sys.path:
    sys.path.insert(0, str(DETECTION_DIR))


def _free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class SimulatorDetectionJobs:
    """Run the Pygame simulator and its detector as a managed web job."""

    def __init__(self):
        self._lock = threading.RLock()
        self._jobs = {}
        self._starting = False

    def start(self):
        with self._lock:
            if self._starting or any(job["status"] in {"starting", "running", "stopping"} for job in self._jobs.values()):
                raise RuntimeError("Simulator detection is already running")
            self._starting = True

        try:
            if not SIMULATOR_SCRIPT.is_file():
                raise RuntimeError("The parking simulator is not installed on this server")
            port = _free_port()
            env = dict(os.environ)
            env["SDL_VIDEODRIVER"] = "dummy"
            env["SDL_AUDIODRIVER"] = "dummy"
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            simulator = subprocess.Popen(
                [str(SIMULATOR_PYTHON if SIMULATOR_PYTHON.is_file() else Path(sys.executable)), str(SIMULATOR_SCRIPT), "--headless", "--port", str(port)],
                cwd=SIMULATOR_DIR,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except Exception:
            with self._lock:
                self._starting = False
            raise
        job_id = uuid.uuid4().hex
        job = {
            "job_id": job_id,
            "status": "starting",
            "message": "Starting the simulator and occupancy detector",
            "error": None,
            "frame_number": 0,
            "latest_frame": None,
            "stop_event": threading.Event(),
            "simulator": simulator,
            "port": port,
            "thread": None,
        }
        with self._lock:
            self._starting = False
            self._jobs[job_id] = job
        worker = threading.Thread(
            target=self._run,
            args=(job_id,),
            name=f"simulator-detection-{job_id[:8]}",
            daemon=True,
        )
        job["thread"] = worker
        worker.start()
        return self.get(job_id)

    def _run(self, job_id):
        with self._lock:
            job = self._jobs[job_id]
            job["status"] = "running"
            job["message"] = "Simulator live detection is running"

        def publish_frame(frame, frame_number):
            import cv2
            success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
            if success:
                with self._lock:
                    active = self._jobs.get(job_id)
                    if active:
                        active["latest_frame"] = encoded.tobytes()
                        active["frame_number"] = frame_number

        try:
            from vehicle.run_simulator import run_live_detection

            port = self._jobs[job_id]["port"]
            run_live_detection(
                live_feed_url=f"http://127.0.0.1:{port}/video",
                stop_event=self._jobs[job_id]["stop_event"],
                on_frame=publish_frame,
            )
            with self._lock:
                job = self._jobs[job_id]
                stopped = job["stop_event"].is_set()
                job["status"] = "stopped" if stopped else "completed"
                job["message"] = "Simulator detection stopped; lot occupancy was reset to vacant"
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                job["status"] = "failed"
                job["error"] = str(exc)
                job["message"] = "Simulator detection failed"
        finally:
            simulator = self._jobs[job_id]["simulator"]
            if simulator.poll() is None:
                simulator.terminate()
                try:
                    simulator.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    simulator.kill()
                    simulator.wait(timeout=5)

    def get(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            data = {
                "job_id": job["job_id"],
                "status": job["status"],
                "message": job["message"],
                "error": job["error"],
                "frame_number": job["frame_number"],
                "has_frame": job["latest_frame"] is not None,
                "cars": [],
                "available_spaces": [],
            }
            port = job["port"]
            running = job["status"] in {"starting", "running", "stopping"}
        if running:
            try:
                with urlopen(f"http://127.0.0.1:{port}/status", timeout=0.5) as response:
                    data.update(json.loads(response.read().decode("utf-8")))
            except (OSError, URLError, ValueError):
                pass
        return data

    def active(self):
        with self._lock:
            job_id = next(
                (job["job_id"] for job in self._jobs.values()
                 if job["status"] in {"starting", "running", "stopping"}),
                None,
            )
        return self.get(job_id) if job_id else None

    def frame(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            return job["latest_frame"] if job else None

    def has_active_job(self):
        with self._lock:
            return self._starting or any(job["status"] in {"starting", "running", "stopping"} for job in self._jobs.values())

    def _control(self, job_id, path):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job["status"] not in {"starting", "running"}:
                return None
            port = job["port"]
        request = Request(f"http://127.0.0.1:{port}{path}", method="POST")
        with urlopen(request, timeout=3) as response:
            return response.status == 202

    def spawn_car(self, job_id):
        return self._control(job_id, "/control/spawn")

    def send_car_out(self, job_id, slot_number):
        from urllib.parse import quote
        return self._control(job_id, f"/control/leave?slot={quote(slot_number, safe='')}")

    def stop(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job["status"] in {"starting", "running"}:
                job["status"] = "stopping"
                job["message"] = "Stopping detection and clearing lot occupancy"
                job["stop_event"].set()
                if job["simulator"].poll() is None:
                    job["simulator"].terminate()
        return self.get(job_id)

    def shutdown(self):
        with self._lock:
            active = [
                job for job in self._jobs.values()
                if job["status"] in {"starting", "running", "stopping"}
            ]
            for job in active:
                job["stop_event"].set()
                if job["simulator"].poll() is None:
                    job["simulator"].terminate()
        for job in active:
            worker = job.get("thread")
            if worker and worker is not threading.current_thread():
                worker.join(timeout=35)
            process = job["simulator"]
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


simulator_detection_jobs = SimulatorDetectionJobs()
