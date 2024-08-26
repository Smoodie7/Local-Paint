import tkinter as tk
from tkinter.colorchooser import askcolor
from tkinter import filedialog
import socket
import threading
import time

MAX_CLIENTS = 10

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
        self.client_sockets = []  # Track connected clients

        self.canvas = tk.Canvas(self.root, bg="white", width=600, height=400)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.tools_frame = tk.Frame(self.root)
        self.tools_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.create_tool_buttons()

        self.canvas.bind("<B1-Motion>", self.paint)
        self.canvas.bind("<ButtonRelease-1>", self.reset_line)

    def create_tool_buttons(self):
        tk.Button(self.tools_frame, text="Color", command=self.choose_color).pack(side=tk.LEFT, padx=5, pady=5)
        brush_size_slider = tk.Scale(self.tools_frame, from_=1, to=20, orient=tk.HORIZONTAL, label="Brush Size")
        brush_size_slider.set(self.brush_size)
        brush_size_slider.pack(side=tk.LEFT, padx=5)
        brush_size_slider.bind("<Motion>", self.change_brush_size)
        tk.Button(self.tools_frame, text="Eraser", command=self.use_eraser).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(self.tools_frame, text="Clear", command=self.clear_canvas).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(self.tools_frame, text="Undo", command=self.undo).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(self.tools_frame, text="Save", command=self.save_canvas).pack(side=tk.LEFT, padx=5, pady=5)  # Save button

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
        self.send_update("CLEAR", broadcast=True)  # Broadcast to all clients including the server

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
            self.send_update(f"UNDO {last_action['command']}", broadcast=True)  # Broadcast the undo action

    def paint(self, event):
        color = "white" if self.eraser_on else self.brush_color
        if self.last_x and self.last_y:
            line_data = f"LINE {self.last_x} {self.last_y} {event.x} {event.y} {color} {self.brush_size}"
            self.canvas.create_line(self.last_x, self.last_y, event.x, event.y,
                                          fill=color, width=self.brush_size, capstyle=tk.ROUND, smooth=tk.TRUE)
            self.undo_stack.append({"command": "LINE", "params": (self.last_x, self.last_y, event.x, event.y),
                                    "style": (color, self.brush_size)})
            self.send_update(line_data, broadcast=True)
        self.last_x, self.last_y = event.x, event.y

    def reset_line(self, event):
        self.last_x, self.last_y = None, None

    def send_update(self, message, sender_socket=None, broadcast=False):
        message += '\n'  # Add a newline as a delimiter
        for client_socket in self.client_sockets:
            if broadcast:
                if client_socket != sender_socket:  # Exclude the sender socket
                    self._send_message(client_socket, message)
            else:
                if sender_socket:  # Send to all except the sender
                    self._send_message(client_socket, message)

    def _send_message(self, client_socket, message):
        try:
            client_socket.sendall(message.encode('utf-8'))
            print(f"Sent message to client: {message.strip()}")
        except (socket.error, AttributeError) as e:
            print(f"Send error to client: {e}")

    def add_client(self, client_socket):
        self.client_sockets.append(client_socket)
        self.update_title()
        threading.Thread(target=handle_client, args=(client_socket, self), daemon=True).start()

    def remove_client(self, client_socket):
        if client_socket in self.client_sockets:
            self.client_sockets.remove(client_socket)
        self.update_title()

    def update_title(self):
        self.root.title(f"LAN WhiteBoard - {int(len(self.client_sockets))} client(s) connected")

    def handle_disconnect(self):
        self.root.title("LAN WhiteBoard - Disconnected")

    def save_canvas(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if file_path:
            self.canvas.postscript(file=file_path)
            print(f"Canvas saved as PostScript file: {file_path}")

def handle_client(client_socket, app):
    buffer = ""
    while True:
        try:
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                break
            buffer += data
            while '\n' in buffer:
                message, buffer = buffer.split('\n', 1)
                if message.strip():  # Avoid processing empty messages
                    print(f"Received message: {message.strip()}")  # Debug statement
                    process_message(message.strip(), app)
        except (socket.error, UnicodeDecodeError) as e:
            print(f"Receive error: {e}")
            break
    client_socket.close()
    app.remove_client(client_socket)
    app.update_title()

def process_message(message, app):
    print(f"Processing message: {message}")  # Debug statement
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
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(MAX_CLIENTS)  # Max allowed connections
    app.root.title("LAN WhiteBoard - Server started, waiting for connection...")

    while True:
        try:
            client_socket, addr = server_socket.accept()
            print(f"Connected to {addr}")
            app.add_client(client_socket)
        except socket.error as e:
            print(f"Server error: {e}")
            break
    server_socket.close()

def start_client(app, host, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((host, port))
        app.root.title("LAN WhiteBoard - Connected to server")
        app.client_sockets = [client_socket]  # Only one client socket for client mode
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

def ping(app, host, port, interval=10):
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
                    app.handle_disconnect()
                    break
    except socket.error as e:
        print(f"Connection failed: {e}")
        app.handle_disconnect()

if __name__ == "__main__":
    target_host = "127.0.0.1"
    target_port = 5000

    root = tk.Tk()
    app = PaintApp(root)

    threading.Thread(target=send_data, args=(app, target_host, target_port), daemon=True).start()
    threading.Thread(target=ping, args=(app, target_host, target_port, 10), daemon=True).start()

    root.mainloop()
