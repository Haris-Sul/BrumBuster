# BrumBuster

BrumBuster protects car part buyers from inaccurate and faked listings by cross referencing photos across the web and using AI Vision for verification. Now the steering wheel is back in your hands.

## What it does

BrumBuster is a digital forgery detector for the car parts marketplace. It analyses listings through three layers of security:

* **Image Auditing:** Extracts the listing image gallery so you can check secondary photos where hidden damage or part mismatches are often concealed.
* **Clone Tracking:** Scans the web to see if a seller's photo is stolen, identifying duplicate listings, geographic anomalies, and old timestamps.
* **AI Visual Inspection:** Verifies that the physical object in the photo actually matches the mechanical specifications and condition claimed in the text.

## How it works

1. **Ingestion:** The backend fetches the eBay listing, bypasses bot blocks, and isolates the specific image index requested by the user.
2. **Image Scan:** The image is sent to SerpApi's exact match engine to check for identical copies across the web, tracking old dates and foreign domains.
3. **AI Analysis:** The image bytes and listing title are passed to Gemini 3 Flash. Acting as an automotive expert, it checks details like lug patterns and wear.
4. **Override Matrix:** If the AI catches a severe issue (mismatched part or condition), it overrides the verdict, ensuring fraud warnings aren't hidden by a "stock photo" label.
5. **UI Delivery:** The backend cleans up redundant noise (hiding duplicate counts if the image is just a harmless stock photo) and streams the final payload to the dashboard.

## Quickstart

### Backend

Create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the repo root:

```bash
SERPAPI_API_KEY=
GEMINI_API_KEY=
FLASK_DEBUG=1
```

Run the API:

```bash
python backend/run.py
```

The API runs at `http://localhost:5000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI runs at `http://localhost:5173`.