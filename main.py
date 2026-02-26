import os
import json
import gspread
import requests
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- 1. ตั้งค่า LINE Token (นำรหัสยาวๆ ของคุณมาใส่ที่นี่) ---
LINE_ACCESS_TOKEN = "Rhg169BzMWPvMVBvgfwiAByT3aj516uUyUad3ryPfKLHHlJXJ6SHjTu4ySb17lI1niePQwFX7pc0hcvT7ewGzkBIvO77jBkBnjAbqQXi6XZpHHtetdJABPWKB2flLlg4xCPfYmnZrQ7DJF1+5GI2vAdB04t89/1O/w1cDnyilFU="

# --- 2. เชื่อมต่อ Google Sheets (ปรับให้รองรับ Google Cloud) ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_path = os.path.join(os.path.dirname(__file__), "service_account.json")
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
client = gspread.authorize(creds)
sheet = client.open("Maechan_Task_Database").sheet1

# --- 3. รายชื่อกลุ่มและรหัสที่คุณคิมจดไว้ ---
DEPARTMENTS = {
    "สำนักปลัด": "Cbffc3d41c387438ecf12e9fce4535aac",
    "กองคลัง": "C6ba465d3099d4ec5cab11c0c6faebd7c",
    "กองช่าง": "Cd0db76898fddb54b3e17dcb703610bbd",
    "กองสาธารณสุข": "C44a6656153fabb50a1b4d137751e0eef",
    "กองการศึกษา": "Cd7d3d3f6228e296021139e3ab19417ae",
    "ตรวจสอบภายใน": "C0d7708c6b31c0194535edfc73dccb66b"
}

# --- 4. หน้าเว็บ Dashboard ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --- 5. ระบบรับงานจากหน้าเว็บและส่งเข้า LINE ---
@app.post("/send-task")
async def send_task(dept: str = Form(...), task: str = Form(...)):
    group_id = DEPARTMENTS.get(dept)
    if group_id:
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Authorization": f"Bearer {LINE_ACCESS_TOKEN}", "Content-Type": "application/json"}
        data = {
            "to": group_id,
            "messages": [{"type": "text", "text": f"🚀 คำสั่งงานใหม่ถึง {dept}:\n{task}"}]
        }
        requests.post(url, headers=headers, json=data)
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, "WEB-CMD", dept, task, "รอดำเนินการ", group_id])
        return {"status": "success", "message": f"ส่งงานไปที่ {dept} แล้ว"}
    return {"status": "error", "message": "ไม่พบกลุ่มที่ระบุ"}

# --- 6. Webhook รับข้อความจาก LINE พิมพ์เข้ามา ---
@app.post("/webhook")
async def line_webhook(request: Request):
    body = await request.body()
    payload = json.loads(body.decode("utf-8"))
    events = payload.get("events", [])

    for event in events:
        if event["type"] == "message" and event["source"]["type"] == "group":
            group_id = event["source"]["groupId"]
            msg_text = event["message"]["text"]
            
            dept_name = "ไม่ระบุหน่วยงาน"
            for name, gid in DEPARTMENTS.items():
                if gid == group_id:
                    dept_name = name
                    break
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([now, "LINE-MSG", dept_name, msg_text, "รอดำเนินการ", group_id])
            print(f"✅ บันทึกงานจาก {dept_name} เรียบร้อย!")

    return {"status": "success"}