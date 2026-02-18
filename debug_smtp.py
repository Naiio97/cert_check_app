import socket
import threading
import datetime

def handle_client(conn, addr):
    print(f'[{datetime.datetime.now()}] Připojení z {addr}')
    try:
        # Send greeting
        conn.sendall(b'220 localhost Python SMTP Debug Server\r\n')
        
        data_mode = False
        message_lines = []
        
        while True:
            # Simple buffer reading (not robust for production but fine for debug)
            chunk = conn.recv(4096)
            if not chunk:
                break
                
            text = chunk.decode('utf-8', errors='ignore')
            
            if data_mode:
                # We are in DATA mode, looking for <CRLF>.<CRLF>
                message_lines.append(text)
                if '\r\n.\r\n' in text or text.endswith('\n.\r\n') or (len(text) >= 3 and text[-3:] == '.\r\n'):
                    print('=' * 80)
                    print(f'[{datetime.datetime.now()}] PŘÍCHOZÍ EMAIL (DATA)')
                    print('-' * 80)
                    full_msg = "".join(message_lines)
                    print(full_msg)
                    print('=' * 80)
                    conn.sendall(b'250 OK\r\n')
                    data_mode = False
                    message_lines = []
            else:
                # Command mode
                lines = text.split('\r\n')
                for line in lines:
                    if not line: continue
                    
                    uc_line = line.upper()
                    if uc_line.startswith('EHLO') or uc_line.startswith('HELO'):
                        conn.sendall(b'250-localhost\r\n250 OK\r\n')
                    elif uc_line.startswith('MAIL FROM:'):
                        print(f'Od: {line[10:].strip()}')
                        conn.sendall(b'250 OK\r\n')
                    elif uc_line.startswith('RCPT TO:'):
                        print(f'Komu: {line[8:].strip()}')
                        conn.sendall(b'250 OK\r\n')
                    elif uc_line.startswith('DATA'):
                        conn.sendall(b'354 End data with <CR><LF>.<CR><LF>\r\n')
                        data_mode = True
                    elif uc_line.startswith('QUIT'):
                        conn.sendall(b'221 Bye\r\n')
                        return
                    elif uc_line.startswith('RSET') or uc_line.startswith('NOOP'):
                         conn.sendall(b'250 OK\r\n')
    except Exception as e:
        print(f"Chyba: {e}")
    finally:
        conn.close()

def run(host='127.0.0.1', port=1025):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
        server.listen(5)
        print(f'Startuji lokální SMTP server na {host}:{port}...')
        print('Kompatibilita: Python 3.12+ (bez smtpd modulu)')
        print('Press Ctrl+C to stop.')
        
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr))
            t.daemon = True
            t.start()
    except KeyboardInterrupt:
        print("\nUkončuji server...")
    except Exception as e:
        print(f"Chyba serveru: {e}")
    finally:
        server.close()

if __name__ == '__main__':
    run()
