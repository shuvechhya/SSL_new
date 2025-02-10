import ssl
import socket
import pandas as pd
from datetime import datetime

file_path = "domains.csv"
df = pd.read_csv(file_path)


column_name = df.columns[0]


def get_ssl_expiry(domain_with_port):
    domain_with_port = str(domain_with_port).strip()  
    if ":" in domain_with_port:
        domain, port = domain_with_port.split(":")
        port = int(port)  
    else:
        domain, port = domain_with_port, 443

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                expiry_date = datetime.strptime(cert['notAfter'], "%b %d %H:%M:%S %Y %Z")
                return expiry_date.strftime("%Y-%m-%d")
    except Exception as e:
        return f"Error: {str(e)}"
    

df["SSL Expiry Date"] = df[column_name].apply(get_ssl_expiry)


df.to_csv(file_path, index=False)

print(f"SSL expiry dates have been saved to {file_path}")
