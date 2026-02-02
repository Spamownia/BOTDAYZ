# shared.py – wspólne obiekty między modułami
import queue

line_queue = queue.Queue()  # kolejka do przesyłania linii z watchera do parsera
