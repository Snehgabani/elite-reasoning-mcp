#!/usr/bin/env python3
import json
import logging
import os
import subprocess
import sys
import threading

# Limit per string/list field to avoid massive payloads
MAX_LIST_ITEMS = 10
MAX_STRING_LEN = 2000

logging.basicConfig(filename=os.path.expanduser('~/.gemini/antigravity/scratch/elite-system/proxy_error.log'), level=logging.DEBUG)

def truncate_payload(data):
    if isinstance(data, list):
        if len(data) > MAX_LIST_ITEMS:
            return [truncate_payload(x) for x in data[:MAX_LIST_ITEMS]] + [f"... truncated {len(data) - MAX_LIST_ITEMS} items ..."]
        return [truncate_payload(x) for x in data]
    elif isinstance(data, dict):
        return {k: truncate_payload(v) for k, v in data.items()}
    elif isinstance(data, str) and len(data) > MAX_STRING_LEN:
        return data[:MAX_STRING_LEN] + f"... [TRUNCATED {len(data) - MAX_STRING_LEN} chars]"
    return data

def process_stdout(proc):
    try:
        for line in iter(proc.stdout.readline, b''):
            try:
                msg = json.loads(line.decode('utf-8'))
                if 'result' in msg:
                    msg['result'] = truncate_payload(msg['result'])
                out_line = json.dumps(msg) + '\n'
                sys.stdout.buffer.write(out_line.encode('utf-8'))
                sys.stdout.buffer.flush()
            except Exception as e:
                # FAIL-CLOSED: Do NOT pass raw potentially massive data through on parse failure!
                error_msg = {"jsonrpc": "2.0", "result": f"[PROXY ERROR] Failed to parse payload safely. Truncation aborted to protect context. Error: {str(e)}"}
                out_line = json.dumps(error_msg) + '\n'
                sys.stdout.buffer.write(out_line.encode('utf-8'))
                sys.stdout.buffer.flush()
                logging.error(f"Error processing stdout (Fail-Closed triggered): {e}")
    except Exception as e:
        logging.error(f"Stdout thread error: {e}")

def process_stderr(proc):
    try:
        for line in iter(proc.stderr.readline, b''):
            sys.stderr.buffer.write(line)
            sys.stderr.buffer.flush()
    except Exception as e:
        logging.error(f"Stderr thread error: {e}")

def main():
    if len(sys.argv) < 2:
        logging.error("No target command provided")
        sys.exit(1)
        
    cmd = sys.argv[1:]
    logging.info(f"Starting proxy for: {' '.join(cmd)}")
    
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    t_out = threading.Thread(target=process_stdout, args=(proc,), daemon=True)
    t_err = threading.Thread(target=process_stderr, args=(proc,), daemon=True)
    t_out.start()
    t_err.start()
    
    try:
        for line in sys.stdin.buffer:
            proc.stdin.write(line)
            proc.stdin.flush()
    except Exception as e:
        logging.error(f"Stdin error: {e}")
    
    proc.stdin.close()
    proc.wait()

if __name__ == '__main__':
    main()
