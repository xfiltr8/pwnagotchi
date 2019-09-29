import _thread
from threading import Lock

import io
import core
import pwnagotchi

from pwnagotchi.ui.view import WHITE, View

from http.server import BaseHTTPRequestHandler, HTTPServer


class VideoHandler(BaseHTTPRequestHandler):
    _lock = Lock()
    _buffer = None
    _index = """<html>
  <head>
    <title>%s</title>
  </head>
  <body>
    <img src="/ui" id="ui"/>

    <script type="text/javascript">
    window.onload = function() {
        var image = document.getElementById("ui");
        function updateImage() {
            image.src = image.src.split("?")[0] + "?" + new Date().getTime();
        }
        setInterval(updateImage, %d);
    }
    </script>
  </body>
</html>"""

    @staticmethod
    def render(img):
        with VideoHandler._lock:
            writer = io.BytesIO()
            img.save(writer, format='PNG')
            VideoHandler._buffer = writer.getvalue()

    def log_message(self, format, *args):
        return

    def _w(self, data):
        try:
            self.wfile.write(data)
        except:
            pass

    def do_GET(self):
        if self._buffer is None:
            self.send_response(404)

        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self._w(bytes(self._index % (pwnagotchi.name(), 1000), "utf8"))

        elif self.path.startswith('/ui'):
            with self._lock:
                self.send_response(200)
                self.send_header('Content-type', 'image/png')
                self.send_header('Content-length', '%d' % len(self._buffer))
                self.end_headers()
                self._w(self._buffer)
        else:
            self.send_response(404)


class Display(View):
    def __init__(self, config, state={}):
        super(Display, self).__init__(config, state)
        self._enabled = config['ui']['display']['enabled']
        self._rotation = config['ui']['display']['rotation']
        self._video_enabled = config['ui']['display']['video']['enabled']
        self._video_port = config['ui']['display']['video']['port']
        self._video_address = config['ui']['display']['video']['address']
        self._display = None
        self._httpd = None
        self.canvas = None
        self._frame_counter = 0
        self._refresh_interval = 60

        if self._enabled:
            self._init_display()
        else:
            self.on_render(self._on_view_rendered)
            core.log("display module is disabled")

        if self._video_enabled:
            _thread.start_new_thread(self._http_serve, ())

    def _http_serve(self):
        if self._video_address is not None:
            self._httpd = HTTPServer((self._video_address, self._video_port), VideoHandler)
            core.log("ui available at http://%s:%d/" % (self._video_address, self._video_port))
            self._httpd.serve_forever()
        else:
            core.log("could not get ip of usb0, video server not starting")

    def _init_display(self):
        from pwnagotchi.ui.waveshare import EPD
        # core.log("display module started")
        self._display = EPD()
        self._display.init(self._display.lut_full_update)
        self._display.Clear(WHITE)
        self._display.init(self._display.lut_partial_update)
        self.on_render(self._on_view_rendered)

    def image(self):
        img = None
        if self.canvas is not None:
            img = self.canvas if self._rotation == 0 else self.canvas.rotate(-self._rotation)
        return img

    def _on_view_rendered(self, img):
        # core.log("display::_on_view_rendered")
        VideoHandler.render(img)

        if self._enabled:
            self.canvas = img if self._rotation == 0 else img.rotate(self._rotation)
            buf = self._display.getbuffer(self.canvas)
            if self._frame_counter > self._refresh_interval:
                self._display.init(self._display.lut_full_update)
                self._display.Clear(WHITE)
                self._display.init(self._display.lut_partial_update)
                self._frame_counter = 0
            else:
                self._frame_counter += 1
            self._display.display(buf)
