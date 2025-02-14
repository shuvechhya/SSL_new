import asyncio
import logging
import os
import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
import dns.resolver
import socket
import ssl
import pytz

logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

excel_file_path = 'domains.csv'


# Helper functions

def read_csv():
    """Reads CSV file and returns dataframe.""" 
    if os.path.exists(excel_file_path):
        return pd.read_csv(excel_file_path)
    return pd.DataFrame(columns=['Sub Domains', 'SSL Expiry Date', 'days_until_expiry'])

def write_csv(df: pd.DataFrame):
    """Writes the dataframe to CSV.""" 
    df.to_csv(excel_file_path, index=False)

def domain_exists(df: pd.DataFrame, domain: str) -> bool:
    """Checks if the domain already exists in the dataframe.""" 
    return domain in df['Sub Domains'].values

def check_a_record(domain_with_port: str) -> bool:
    """Checks if A record exists for a domain.""" 
    try:
        domain = domain_with_port.split(':')[0]  
        dns.resolver.resolve(domain, 'A')
        return True
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, Exception):
        return False

def get_ssl_expiry(domain_with_port: str) -> str:
    """Gets the SSL expiry date for a domain.""" 
    domain_with_port = domain_with_port.strip()
    domain, port = domain_with_port.split(":") if ":" in domain_with_port else (domain_with_port, 443)

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, int(port)), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                expiry_date = datetime.strptime(cert['notAfter'], "%b %d %H:%M:%S %Y %Z")
                expiry_date = pytz.utc.localize(expiry_date)
                return expiry_date.strftime("%Y-%m-%d")
    except Exception as e:
        logging.error(f"SSL expiry check failed for {domain}: {e}")
        return "Error: Could not retrieve SSL expiry"

def get_days_until_expiry(expiry_date_str: str) -> int:
    """Calculates the number of days until the SSL certificate expires.""" 
    if expiry_date_str.startswith("Error"):
        return -1  # Invalid SSL expiry date
    
    expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d")
    current_date = datetime.now()
    delta = expiry_date - current_date
    return delta.days

async def update_ssl_expiry_dates():
    """Updates the SSL expiry dates for all domains in the CSV file.""" 
    while True:
        try:
            df = read_csv()
            for index, row in df.iterrows():
                domain = row['Sub Domains']
                ssl_expiry_date = get_ssl_expiry(domain)
                days_until_expiry = get_days_until_expiry(ssl_expiry_date)
                df.at[index, 'SSL Expiry Date'] = ssl_expiry_date
                df.at[index, 'days_until_expiry'] = days_until_expiry
            write_csv(df)
            logging.info("SSL expiry dates updated successfully.")
        except Exception as e:
            logging.error(f"Error updating SSL expiry dates: {e}")
        await asyncio.sleep(24 * 60 * 60)  # Sleep for 24 hours

@app.on_event("startup")
async def startup_event():
    """Start the background task to update SSL expiry dates on startup.""" 
    asyncio.create_task(update_ssl_expiry_dates())

# Routes

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Display the homepage.""" 
    return templates.TemplateResponse("domain_status.html", {"request": request})

@app.get("/add-domain", response_class=HTMLResponse)
async def add_domain_get(request: Request):
    """Shows the add domain form with the current watchlist.""" 
    try:
        df = read_csv()
        domain_data = df.to_dict('records') if not df.empty else []

        for domain in domain_data:
            domain['days_until_expiry'] = get_days_until_expiry(domain['SSL Expiry Date'])

        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "domain_data": domain_data
        })
    except Exception as e:
        logging.error(f"Error loading domain data: {e}")
        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "error": f"Error loading domain data: {str(e)}",
            "domain_data": []
        })

@app.post("/add-domain", response_class=HTMLResponse)
async def add_domain_post(request: Request, domain: str = Form(...)):
    """Adds a domain to the watchlist.""" 
    if not domain:
        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "error": "Subdomain parameter is required",
        })

    subdomain = domain.strip()

    if not check_a_record(subdomain):
        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "error": f"No A record found for {subdomain}. Cannot add to watchlist.",
        })

    try:
        df = read_csv()  

        if domain_exists(df, subdomain):
            return templates.TemplateResponse("add_domain.html", {
                "request": request,
                "message": f"{subdomain} already exists in the watchlist",
                "domain_data": df.to_dict('records')
            })

        ssl_expiry_date = get_ssl_expiry(subdomain)
        days_until_expiry = get_days_until_expiry(ssl_expiry_date)

        new_row = pd.DataFrame({
            'Sub Domains': [subdomain],
            'SSL Expiry Date': [ssl_expiry_date],
            'days_until_expiry': [days_until_expiry]
        })

        df = pd.concat([df, new_row], ignore_index=True)

        write_csv(df)

        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "message": f"{subdomain} added to the watchlist successfully with SSL expiry date: {ssl_expiry_date}",
            "domain_data": df.to_dict('records')
        })

    except Exception as e:
        logging.error(f"Error while adding domain {subdomain}: {e}")
        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "error": f"Error: {str(e)}",
            "domain_data": read_csv().to_dict('records')
        })

@app.post("/delete-domain", response_class=HTMLResponse)
async def delete_domain(request: Request, domain: str = Form(...)):
    """Deletes a domain from the watchlist.""" 
    try:
        df = read_csv()
        df = df[df['Sub Domains'] != domain]
        write_csv(df)
        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "message": f"Domain {domain} successfully removed from the watchlist.",
            "domain_data": df.to_dict('records')
        })

    except Exception as e:
        logging.error(f"Error while deleting domain {domain}: {e}")
        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "error": f"Error: {str(e)}",
            "domain_data": read_csv().to_dict('records')
        })

@app.get("/domain-status", response_class=HTMLResponse)
async def domain_status(request: Request, domain: str = None):
    """Display domain status and SSL expiry date.""" 
    if not domain:
        return templates.TemplateResponse("domain_status.html", {"request": request})

    if not check_a_record(domain):
        return templates.TemplateResponse("domain_status.html", {
            "request": request,
            "error": f"No A record found for {domain}. Cannot retrieve SSL expiry date."
        })

    ssl_expiry_date = get_ssl_expiry(domain)

    return templates.TemplateResponse("domain_status.html", {
        "request": request,
        "domain": domain,
        "ssl_expiry_date": ssl_expiry_date,
        "error": None
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
