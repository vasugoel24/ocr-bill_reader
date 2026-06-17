from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
import pytesseract
import re
import io
import traceback

app = FastAPI()

# 👉 Set this path if needed
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ---------------- OCR ----------------
def extract_text(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image)
    return text


# ---------------- BILL PARSER ----------------
def parse_bill(text):
    import re

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    items = []

    price_pattern = r"-?\d+\.\d{2}"

    for line in lines:

        # extract price
        found = re.findall(price_pattern, line)
        if not found:
            continue

        price = float(found[-1])
        upper = line.upper()

        # ❌ skip unwanted financial lines
        if any(x in upper for x in ["TOTAL", "SUB", "SERVICE", "CHARGE", "TAX", "DISCOUNT"]):
            continue

        # remove price
        item = re.sub(price_pattern, "", line)

        # remove symbols & numbers (keep only letters)
        item = re.sub(r"[^a-zA-Z ]", " ", item)

        # normalize spaces
        item = re.sub(r"\s+", " ", item).strip()

        # remove single-letter garbage words
        words = [w for w in item.split() if len(w) > 1]
        item = " ".join(words)

        # skip empty or junk results
        if len(item) < 3:
            continue

        items.append({
            "item": item,
            "price": price
        })

    # ---------------- TOTAL LOGIC ----------------

    total = None

    # try detect explicit total line
    for line in lines:
        if "TOTAL" in line.upper():
            match = re.findall(price_pattern, line)
            if match:
                total = float(match[-1])
                break

    # fallback: sum items
    if total is None and items:
        total = round(sum(i["price"] for i in items), 2)

    return {
        "items": items,
        "total": total
    }

# ---------------- API ----------------
@app.get("/")
def home():
    return {"message": "Tesseract OCR Bill Reader Running (No NumPy)"}


@app.post("/upload-bill/")
async def upload_bill(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()

        text = extract_text(image_bytes)
        result = parse_bill(text)

        return {
            "success": True,
            "filename": file.filename,
            "raw_text": text,
            "bill": result
        }

    except Exception as e:
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )