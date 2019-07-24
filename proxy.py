import socket
import threading
import sys 
import hashlib,os # result = hashlib.md5(b'Password') 
from servthread import server_thread

def main():
    # Define Host and Port Number
    host = '' #Blank For localhost
    port = 20100
    try:
        server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        server_socket.bind((host,port))
        print("Proxy Server Running On 127.0.0.1:",port,"........")
        server_socket.listen(10) # Backlog = 10
    
    except:
        if server_socket:
            server_socket.close()
        print ("Error while OPENING socket.")
        sys.exit(1)

    while True:
        client_socket, client_address = server_socket.accept()
        print("Request from",client_address[0],"/",client_address[1])
        connection_thread = threading.Thread(target=server_thread, args=(client_socket, client_address))
        connection_thread.start()
    server_socket.close()

if __name__ == '__main__':
    if not os.path.isdir("cachefiles"):
        os.system("mkdir cachefiles")
    os.system("rm -rf cachefiles/*")
    main()