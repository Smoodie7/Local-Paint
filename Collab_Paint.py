import tkinter as tk
from tkinter.colorchooser import askcolor
from tkinter import filedialog
import socket
import threading
import time

class PaintApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LAN WhiteBoard - Waiting for connection...")

        self.brush_color = "black"
        self.brush_size = 5
        self.eraser_on = False
        self.last_x = None
        self.last_y = None
        self.undo_stack = []

        self.canvas = tk.Canvas(self.root, bg="white", width=600, height=400)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.tools_frame = tk.Frame(self.root)
        self.tools_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.create_tool_buttons()

        self.canvas.bind("<B1-Motion>", self.paint)
        self.canvas.bind("<ButtonRelease-1>", self.reset_line)

        self.client_socket = None  # Initialize socket variable

    def create_tool_buttons(self):
        tk.Button(self.tools_frame, text="Color", command=self.choose_color).pack(side=tk.LEFT, padx=5, pady=5)
        brush_size_slider = tk.Scale(self.tools_frame, from_=1, to=20, orient=tk.HORIZONTAL, label="Brush Size")
        brush_size_slider.set(self.brush_size)
        brush_size_slider.pack(side=tk.LEFT, padx=5)
        brush_size_slider.bind("<Motion>", self.change_brush_size)
        tk.Button(self.tools_frame, text="Eraser", command=self.use_eraser).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(self.tools_frame, text="Clear", command=self.clear_canvas).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(self.tools_frame, text="Undo", command=self.undo).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(self.tools_frame, text="Save", command=self.save_canvas).pack(side=tk.LEFT, padx=5, pady=5)

    def choose_color(self):
        self.eraser_on = False
        color = askcolor(color=self.brush_color)[1]
        if color:
            self.brush_color = color

    def change_brush_size(self, event):
        self.brush_size = event.widget.get()

    def use_eraser(self):
        self.eraser_on = True
        self.brush_color = "white"

    def clear_canvas(self):
        self.canvas.delete("all")
        self.undo_stack.clear()
        self.send_update("CLEAR")

    def undo(self):
        if self.undo_stack:
            last_action = self.undo_stack.pop()
            if last_action["command"] == "LINE":
                self.canvas.delete("all")
                for action in self.undo_stack:
                    if action["command"] == "LINE":
                        x1, y1, x2, y2 = action["params"]
                        color, width = action["style"]
                        self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width, capstyle=tk.ROUND, smooth=tk.TRUE)
            elif last_action["command"] == "CLEAR":
                self.clear_canvas()  # Clear and restore from stack
            self.send_update(f"UNDO {last_action['command']}")

    def paint(self, event):
        color = "white" if self.eraser_on else self.brush_color
        if self.last_x and self.last_y:
            line = self.canvas.create_line(self.last_x, self.last_y, event.x, event.y,
                                          fill=color, width=self.brush_size, capstyle=tk.ROUND, smooth=tk.TRUE)
            self.undo_stack.append({"command": "LINE", "params": (self.last_x, self.last_y, event.x, event.y),
                                    "style": (color, self.brush_size)})
            self.send_update(f"LINE {self.last_x} {self.last_y} {event.x} {event.y} {color} {self.brush_size}")
        self.last_x, self.last_y = event.x, event.y

    def reset_line(self, event):
        self.last_x, self.last_y = None, None

    def send_update(self, message):
        if self.client_socket:
            try:
                self.client_socket.sendall(message.encode('utf-8'))
            except (socket.error, AttributeError) as e:
                print(f"Send error: {e}")

    def save_canvas(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".ps",
                                               filetypes=[("PostScript files", "*.ps"), ("All files", "*.*")])
        if file_path:
            self.canvas.postscript(file=file_path)
            print(f"Canvas saved as {file_path}")

def handle_client(client_socket, app):
    while True:
        try:
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                break
            process_message(data, app)
        except (socket.error, UnicodeDecodeError) as e:
            print(f"Receive error: {e}")
            app.root.title("LAN WhiteBoard - Connection lost")
            break
    client_socket.close()

def process_message(message, app):
    parts = message.split()
    command = parts[0]

    if command == "LINE":
        try:
            x1, y1, x2, y2 = map(int, parts[1:5])
            color = parts[5]
            width = int(parts[6])
            app.canvas.create_line(x1, y1, x2, y2, fill=color, width=width, capstyle=tk.ROUND, smooth=tk.TRUE)
        except ValueError as e:
            print(f"Message processing error: {e}")
    elif command == "CLEAR":
        app.canvas.delete("all")
    elif command == "UNDO":
        if app.undo_stack:
            last_action = app.undo_stack.pop()
            if last_action["command"] == "LINE":
                app.canvas.delete("all")
                for action in app.undo_stack:
                    if action["command"] == "LINE":
                        x1, y1, x2, y2 = action["params"]
                        color, width = action["style"]
                        app.canvas.create_line(x1, y1, x2, y2, fill=color, width=width, capstyle=tk.ROUND, smooth=tk.TRUE)
            elif last_action["command"] == "CLEAR":
                app.clear_canvas()

def start_server(app, host, port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(1)
    app.root.title("LAN WhiteBoard - Acting as server, waiting for connection...")

    try:
        client_socket, addr = server_socket.accept()
        app.root.title(f"LAN WhiteBoard - Connected to {addr}")
        app.client_socket = client_socket
        threading.Thread(target=handle_client, args=(client_socket, app), daemon=True).start()
    except socket.error as e:
        print(f"Server error: {e}")

def start_client(app, host, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((host, port))
        app.root.title("LAN WhiteBoard - Connected to server")
        app.client_socket = client_socket
        return client_socket
    except ConnectionRefusedError:
        app.root.title("LAN WhiteBoard - No server found, switching to server mode...")
        return None
    except socket.error as e:
        print(f"Client error: {e}")
        return None

def send_data(app, host, port):
    client_socket = start_client(app, host, port)
    
    if not client_socket:
        start_server(app, host, port)

def ping(host, port, interval=7):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            while True:
                try:
                    s.sendall(b'\x00')
                    print(f"Ping sent to {host}:{port}")
                    time.sleep(interval)
                except socket.error as e:
                    print(f"Ping failed: {e}")
                    break
    except socket.error as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    target_host = "127.0.0.1"
    target_port = 5000

    root = tk.Tk()
    app = PaintApp(root)

    threading.Thread(target=send_data, args=(app, target_host, target_port), daemon=True).start()

    # Only start one ping thread
    ping_thread = threading.Thread(target=ping, args=(target_host, target_port, 7), daemon=True)
    ping_thread.start()

    root.mainloop()
