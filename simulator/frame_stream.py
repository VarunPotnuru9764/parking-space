import cv2

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Condition, Thread

class FrameStream:
    def __init__(self, host = "127.0.0.1", port = 8765):
        self._condition = Condition()
        self._latest_jpeg = None
        self._frame_number = 0
        self._server = None
        self._thread = None

        stream = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
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

            def log_message(self, format, *args):
                pass

        self._server = ThreadingHTTPServer((host, port), Handler)
        self._server.daemon_threads = True
        self.host, self.port = self._server.server_address

    def start(self):
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://{self.host}:{self.port}/video"

    def publish(self, frame):
        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not success:
            return

        with self._condition:
            self._latest_jpeg = encoded.tobytes()
            self._frame_number += 1
            self._condition.notify_all()

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
