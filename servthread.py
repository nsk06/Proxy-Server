import os,sys,socket,time,re,copy
from netaddr import IPNetwork
import base64
access = False

CACHE_LIMIT = 3

cachefiles = []
saved_files = 0

class CachedFile(object):
    def __init__(self,filename):
        self.filename = filename
        self.totalhits = 1
        self.lasthit = time.time()
        self.last2lasthit = time.time()

# insert the header
def insert_if_modified(details,last_mtime):
    lines = details.splitlines()
    while lines[len(lines)-1] == '':
        lines.remove('')

    header = "If-Modified-Since: " + str(last_mtime)
    lines.append(header)

    details = "\r\n".join(lines) + "\r\n\r\n"
    return details

# check whether file is already cached or not
def get_current_cache_info(fileurl):
    if os.path.isfile(fileurl):
        statbuf = os.stat(fileurl)
        last_mtime = statbuf.st_mtime
        # last_mtime = time.strptime(time.ctime(os.path.getmtime(fileurl)), "%a %b %d %H:%M:%S %Y")
        return last_mtime
    else:
        return None

def server_thread(client_socket, client_address):

    global access,cachefiles,saved_files
    request = client_socket.recv(1024) #receive 1024 bytes
    print("original",request.decode())
    if(client_address[0] == "127.0.0.1" and int(client_address[1]) not in range(20000,20100)):
        print("Request not from inside the network......")
        client_socket.send("Request not from inside the network.......".encode())
        client_socket.close()
        sys.exit(-1)

    send_final = copy.deepcopy(request)
    get_check = send_final.decode().find('GET')
    #print("getcheck",get_check)
    post_check = send_final.decode().find('POST')
    #print("postcheck",post_check)
    auth_check = send_final.decode().find('Authorization')
    #print("auth_check",auth_check)
    topusers = []
    toplist = open('users.txt','r')
    toplist = toplist.readlines()
    toplist = [x.strip('\n').encode() for x in toplist]
    for x in toplist:
        val = base64.b64encode(x)
        val = val.decode()
        topusers.append(val)
    #print("list printing",topusers)
    temp_store = send_final.decode().splitlines()
    send_final = send_final.decode().split('\n')
    if(auth_check > 0):
        enc = temp_store[2].split()[2]
        #print("enc",enc)
        if enc in topusers:
            print("Admin access granted")
            access = True
        else:
            print("Don't have access. Wrong username password")
            access = False
    
    # GET REQUESTED FILENAME
    filename = send_final[0].split(' ')[1]
    tmpind = filename.find('://')
    filename = filename[tmpind+3:]
    filename = filename.replace('/','_')
    
    send_final[0] = re.split('http://|/',send_final[0])
    send_final[0].pop(1)
    send_final[0][1] = '/'+send_final[0][1]
    send_final[0] = ''.join(send_final[0])
    rem = send_final[0].split('\r')
    rem.pop(1)
    send_final[0] = ''.join(rem)
    rem = send_final[0].find('HTTP')
    send_final[0] = send_final[0][:rem+4]+'/'+send_final[0][rem+4:]
    send_fin = '\r\n'.join(send_final)+'\r\n\r\n'

    host = '' # any localhost
    port = -1   # standard number for http port

    url = request.decode().split('\n')[0]
    url = url.split(' ')[1]

    http_pos = url.find('://')
    if http_pos == -1:
        temp = url
    else:
        temp = url[(http_pos+3):]
    
    # Find End Of Web Server
    webserver_pos = temp.find('/')
    if webserver_pos == -1:
        webserver_pos = len(temp)

    port_pos = temp.find(':')
    if port_pos == -1 or webserver_pos<port_pos:
        port = 80
        host = temp[:webserver_pos]
    else:
        port = int((temp[(port_pos+1):])[:webserver_pos-port_pos-1])
        host = temp[:port_pos]
    
    print("Connect To:",host,port)

    if(int(port) not in range(20101,20200) and port != 80):
        print("Request Outside the server range")
        client_socket.send("Port address outside the specified range".encode())
        client_socket.close()
        sys.exit(-1)

    cacheTimer = time.time() - 300

    # Clear Cached files bassed on time
    for files in cachefiles:
        if files.last2lasthit < cacheTimer and files.totalhits<3:
            print("File "+files.filename+" Removed.")
            cachefiles.remove(files)

    if get_check >= 0:
        new_file = True
        new_write = False

        for files in cachefiles:
            if filename == files.filename: 
                
                new_file = False           
                
                # Change Timers and Hits
                files.last2lasthit = files.lasthit
                files.lasthit = time.time()
                files.totalhits += 1

                if files.totalhits == 3:
                    
                    # LRU
                    if saved_files==CACHE_LIMIT:
                        temp = 0
                        tmp_ind = 0
                        for i in range(CACHE_LIMIT):
                            if temp < cachefiles[i].lasthit:
                                temp = cachefiles[i].lasthit
                                tmpind = i
                        file_name = './cachefiles/'+cachefiles[tmp_ind].filename
                        os.remove(file_name)
                        cachefiles.pop(tmp_ind)
                        saved_files-=1


                    new_write = True
                    saved_files+=1
                    break

                # No file if totalhits < 3
                if files.totalhits < 3:
                    break
                
                # Read the Cached Files

                # ADD HEADER
                file_name = './cachefiles/'+filename
                last_mtime = get_current_cache_info(file_name)
                modified_header = insert_if_modified(send_fin,last_mtime)

                server_socket_tmp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket_tmp.connect((host,port))
                server_socket_tmp.send(modified_header.encode())

                reply = server_socket_tmp.recv(1024)
                server_socket_tmp.close()

                if last_mtime and "304 Not Modified" in reply.decode():
                    with open(file_name, "r") as fd:
                        cached_data = fd.read()
                    client_socket.send(cached_data.encode())
                    print(" Cache Hit ")
                    # Close the socket
                    client_socket.close()
                    sys.exit(1)
                else:
                    new_write = True
                    os.remove(file_name)
                    break

        # If here , then no files in cache    
        # a new cachefile class initialise
        if new_file:
            cachefiles.append(CachedFile(filename))

    block = open('blacklist.txt','r')
    temp = block.readlines()
    addrs = [x.strip() for x in temp]
    for x in addrs:
        if host in IPNetwork(x) and access==False:
            client_socket.send("IP blocked by Proxy...You Dont have access".encode())
            client_socket.close()
            sys.exit(-1)
    
    portbl = open('portblock.txt','r')
    portblock = portbl.readlines()
    portlist = [x.strip() for x in portblock]
    for x in portlist:
        checkstr = str(host)+":"+str(port)
        # print(checkstr)
        if checkstr == x and access == False:
            client_socket.send("Port blocked by Proxy...You Dont have access\n".encode())
            client_socket.close()
            sys.exit(-1)
    try:
        if port == 80:
            server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            server_socket.connect((host,port))
            server_socket.send(request)
            while True:
                data = server_socket.recv(1024) # receive 1024 bytes
                temp = data.decode()
                if len(temp) <= 0:
                    break
                client_socket.send(data)   
        elif get_check >= 0:
            print("GET REQUEST")
            server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            server_socket.connect((host,port))
            server_socket.send(send_fin.encode())
            while True:
                data = server_socket.recv(1024) # receive 1024 bytes
                temp = data.decode()

                if len(temp) <= 0:
                    break

                if new_write:
                    # if temp.find('HTTP')<0: #assuming no HTTP in my file
                    file_name = './cachefiles/'+filename
                    with open(file_name, "a") as file:
                        file.write(temp)
                    print("Received and Cached "+str(len(temp))+" bytes.")
                else:
                    print("Received "+str(len(temp))+" bytes.")
                client_socket.send(data)    
        elif post_check >= 0:
            print("POST REQUEST")
            server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            server_socket.connect((host,port))
            server_socket.send(request)
            while True:
                data = server_socket.recv(1024) # receive 1024 bytes
                temp = data.decode()
                if len(temp) <= 0:
                    break                
                client_socket.send(data) 
        server_socket.close()
        client_socket.close() 
    except:
        if server_socket:
            server_socket.close()
        if client_socket:
            client_socket.close()
        print('Error!',sys.exc_info())
        sys.exit(1)

