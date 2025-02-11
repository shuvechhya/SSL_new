import logging
import os
import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
import dns.resolver


logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


excel_file_path = 'domains.csv'

def check_a_record(domain: str) -> bool:
    try:
        answers = dns.resolver.resolve(domain, 'A')
        return bool(answers) 
    except dns.resolver.NoAnswer:
        return False
    except dns.resolver.NXDOMAIN:
        return False
    except Exception as e:
        print(f"DNS lookup error: {e}")
        return False

@app.post("/add-domain", response_class=HTMLResponse)
async def add_domain_post(request: Request, domain: str = Form(...)):
    if not domain:
        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "error": "Subdomain parameter is required"
        })

    subdomain = domain.strip()
    
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
            df = pd.DataFrame(columns=['Sub Domains'])

        new_row = pd.DataFrame({'Sub Domains': [subdomain]})
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(excel_file_path, index=False)

        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "message": f"{subdomain} added to the watchlist successfully!"
        })

    except Exception as e:
        return templates.TemplateResponse("add_domain.html", {
            "request": request,
            "error": f"Error: {str(e)}"
        })

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
