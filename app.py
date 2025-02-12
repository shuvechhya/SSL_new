import logging
import os
import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
import dns.resolver
from fastapi.responses import RedirectResponse
import socket
import ssl
import pytz

logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


excel_file_path = 'domains.csv'

def check_a_record(domain_with_port: str) -> bool:
    try:
        # Strip the port if it's included
        domain = domain_with_port.split(':')[0]  
        answers = dns.resolver.resolve(domain, 'A')
        return bool(answers) 
    except dns.resolver.NoAnswer:
        return False
    except dns.resolver.NXDOMAIN:
        return False
    except Exception as e:
        print(f"DNS lookup error: {e}")
        return False

# Function to check SSL expiry date
def get_ssl_expiry(domain_with_port: str) -> str:
    domain_with_port = str(domain_with_port).strip()
    if ":" in domain_with_port:
        domain, port = domain_with_port.split(":")
        port = int(port)
    else:
        domain, port = domain_with_port, 443

    try:
        # Create SSL context
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                # Parse the 'notAfter' field from certificate
                expiry_date = datetime.strptime(cert['notAfter'], "%b %d %H:%M:%S %Y %Z")
                
                # Ensure the date is in UTC
                expiry_date = pytz.utc.localize(expiry_date)
                
                # Return the formatted date
                return expiry_date.strftime("%Y-%m-%d")
    except Exception as e:
        logging.error(f"SSL expiry check failed for {domain}: {e}")
        return "Error: Could not retrieve SSL expiry"


# Post route for adding a domain to the watchlist
@app.post("/add-domain", response_class=HTMLResponse)
async def add_domain_post(request: Request, domain: str = Form(...)):
    if not domain:
        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "error": "Subdomain parameter is required"
        })

    subdomain = domain.strip()

    # Check A record
    if not check_a_record(subdomain):
        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "error": f"No A record found for {subdomain}. Cannot add to watchlist."
        })

    try:
        if os.path.exists(excel_file_path):
            df = pd.read_csv(excel_file_path)
            if subdomain in df['Sub Domains'].values:
                return templates.TemplateResponse("add_domain.html", {
                    "request": request,
                    "message": f"{subdomain} already exists in the watchlist"
                })
        else:
            df = pd.DataFrame(columns=['Sub Domains', 'SSL Expiry Date'])

        # Get SSL expiry date
        ssl_expiry_date = get_ssl_expiry(subdomain)

        # Add new domain and SSL expiry date to the dataframe
        new_row = pd.DataFrame({'Sub Domains': [subdomain], 'SSL Expiry Date': [ssl_expiry_date]})
        df = pd.concat([df, new_row], ignore_index=True)

        # Save updated data to CSV file
        df.to_csv(excel_file_path, index=False)

        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "message": f"{subdomain} added to the watchlist successfully with SSL expiry date: {ssl_expiry_date}!"
        })

    except Exception as e:
        logging.error(f"Error while adding domain {subdomain}: {e}")
        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "error": f"Error: {str(e)}"
        })

# GET route for the homepage
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("add_domain.html", {"request": request})


#this is for domain_status backend 
@app.get("/domain-status", response_class=HTMLResponse)
async def domain_status(request: Request, domain: str = None):
    if not os.path.exists(excel_file_path):
        return templates.TemplateResponse("domain_status.html", {
            "request": request,
            "domain_data": [],
            "error": "No domains found."
        })

    try:
        df = pd.read_csv(excel_file_path)
        domain_data = df.to_dict(orient="records") if not df.empty else []
    except Exception as e:
        return templates.TemplateResponse("domain_status.html", {
            "request": request,
            "domain_data": [],
            "error": f"Error reading CSV: {e}"
        })

    # If a domain is provided, find the specific domain's SSL expiry date
    if domain:
        result = df.loc[df['Sub Domains'] == domain]

        if result.empty:
            return templates.TemplateResponse("domain_status.html", {
                "request": request,
                "domain_data": domain_data,
                "error": f"No data found for domain: {domain}"
            })

        expiry_date = result.iloc[0]['SSL Expiry Date']
        return templates.TemplateResponse("domain_status.html", {
            "request": request,
            "domain_data": domain_data,
            "domain": domain,
            "ssl_expiry_date": expiry_date
        })

    return templates.TemplateResponse("domain_status.html", {
        "request": request,
        "domain_data": domain_data
    })

@app.post("/delete-domain")
async def delete_domain(domain: str = Form(...)):
    """Deletes a domain from the CSV file."""
    if not os.path.exists(excel_file_path):
        return RedirectResponse(url="/domain-status", status_code=303)

    try:
        df = pd.read_csv(excel_file_path)
        updated_df = df[df["Sub Domains"] != domain]  

        updated_df.to_csv(excel_file_path, index=False)  
    except Exception as e:
        return RedirectResponse(url=f"/domain-status?error=Failed to delete: {e}", status_code=303)

    return RedirectResponse(url="/domain-status", status_code=303)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)