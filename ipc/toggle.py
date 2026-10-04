#!/usr/bin/env python3

import socket
import os

# Set the path for the Unix sockets...
socket_path = '/tmp/my_socket'

with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.connect(socket_path)
    message = 'LLM_TOGGLE'
    client.sendall(message.encode())
    #response = client.recv(1024)
    #print(f'Recieved response: {response.decode()}')
    client.close()
