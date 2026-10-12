import cv2
import json

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Queue
from threading import Condition, Thread

class FrameStream:
    def __init__(self, host = "127.0.0.1", port = 8765):
        self._condition = Condition()
        self._latest_jpeg = None
        self._frame_number = 0
        self._status = {"cars": [], "available_spaces": []}
        self._commands = Queue()
        self._server = None
        self._thread = None

        stream = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/status":
                    body = json.dumps(stream.status()).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path != "/video":
                    self.send_error(404)
                    return

                self.send_response(200)
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                try:
                    last_frame_number = 0
                    while True:
                        frame_number, jpeg = stream._next_frame(last_frame_number)
                        if jpeg is None:
                            continue

                        last_frame_number = frame_number
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii"))
                        self.wfile.write(jpeg)
                        self.wfile.write(b"\r\n")
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_POST(self):
                if self.path == "/control/spawn":
                    stream._commands.put(("spawn", None))
                elif self.path.startswith("/control/leave?"):
                    from urllib.parse import parse_qs, urlparse
                    slot_number = parse_qs(urlparse(self.path).query).get("slot", [""])[0]
                    if not slot_number:
                        self.send_error(422, "slot is required")
                        return
                    stream._commands.put(("leave", slot_number))
                else:
                    self.send_error(404)
                    return
                self.send_response(202)
                self.end_headers()

            def log_message(self, format, *args):
                pass

        self._server = ThreadingHTTPServer((host, port), Handler)
        self._server.daemon_threads = True
        self.host, self.port = self._server.server_address

    def start(self):
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://{self.host}:{self.port}/video"

    def publish(self, frame, status=None):
        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not success:
            return

        with self._condition:
            self._latest_jpeg = encoded.tobytes()
            self._frame_number += 1
            if status is not None:
                self._status = status
            self._condition.notify_all()

    def status(self):
        with self._condition:
            return dict(self._status)

    def drain_commands(self):
        commands = []
        while True:
            try:
                commands.append(self._commands.get_nowait())
            except Empty:
                return commands

    def _next_frame(self, last_frame_number):
        with self._condition:
            self._condition.wait_for(
                lambda: self._frame_number > last_frame_number,
                timeout=1,
            )
            if self._frame_number <= last_frame_number:
                return last_frame_number, None
            return self._frame_number, self._latest_jpeg

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
