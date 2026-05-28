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

# --- 1. ตั้งค่า LINE Token (ของคุณนิด) ---
LINE_ACCESS_TOKEN = "Rhg169BzMWPvMVBvgfwiAByT3aj516uUyUad3ryPfKLHHlJXJ6SHjTu4ySb17lI1niePQwFX7pc0hcvT7ewGzkBIvO77jBkBnjAbqQXi6XZpHHtetdJABPWKB2flLlg4xCPfYmnZrQ7DJF1+5GI2vAdB04t89/1O/w1cDnyilFU="

# --- 2. เชื่อมต่อ Google Sheets ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_path = os.path.join(os.path.dirname(__file__), "service_account.json")
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
client = gspread.authorize(creds)

# 🌟 แยกตัวแปรเพื่อเชื่อมต่อทั้ง 2 ชีท
sheet_tasks = client.open("Maechan_Task_Database").worksheet("Tasks")
sheet_users = client.open("Maechan_Task_Database").worksheet("Users")

# --- 3. รายชื่อกลุ่มและรหัส ---
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
        sheet_tasks.append_row([now, "WEB-CMD", dept, task, "รอดำเนินการ", group_id])
        return {"status": "success", "message": f"ส่งงานไปที่ {dept} แล้ว"}
    return {"status": "error", "message": "ไม่พบกลุ่มที่ระบุ"}

# --- 6. Webhook รับข้อความจาก LINE ---
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
            sheet_tasks.append_row([now, "LINE-MSG", dept_name, msg_text, "รอดำเนินการ", group_id])
            print(f"✅ บันทึกงานจาก {dept_name} เรียบร้อย!")

    return {"status": "success"}

# --- 7. ระบบอัปเดตงาน และแจ้งเตือนไปยังผู้สั่งงาน (เชื่อม 2 ชีท) ---
@app.post("/update-task")
async def update_task(
    row_index: int = Form(...), 
    new_status: str = Form(...), 
    detail: str = Form(...), 
    updater_name: str = Form(...)
):
    try:
        # 1. ดึงข้อมูลงานจากชีท Tasks
        row_data = sheet_tasks.row_values(row_index)
        if not row_data:
            return {"status": "error", "message": "ไม่พบข้อมูลงานในระบบ"}

        # ป้องกัน Error กรณีข้อมูลในแถวไม่ครบ
        task_title = row_data[2] if len(row_data) > 2 else "ไม่ระบุชื่องาน"      # คอลัมน์ C 
        created_by_name = row_data[8] if len(row_data) > 8 else "" # คอลัมน์ I 

        # 2. บันทึกข้อมูลที่อัปเดตลงชีท Tasks
        # อัปเดตสถานะที่คอลัมน์ H (ใน gspread เริ่มนับจาก 1 ดังนั้น H = 8)
        sheet_tasks.update_cell(row_index, 8, new_status)   
        
        # อัปเดตรายละเอียดที่คอลัมน์ J (J = 10)
        full_remark = f"[{updater_name}] {detail}"
        sheet_tasks.update_cell(row_index, 10, full_remark)       

        # 3. 🕵️‍♂️ ค้นหา LINE ID ของ "ผู้สั่งงาน" จากชีท Users
        target_line_id = ""
        if created_by_name:
            users_records = sheet_users.get_all_records()
            for user in users_records:
                if str(user.get("FullName")).strip() == str(created_by_name).strip():
                    target_line_id = str(user.get("LINE_UserID")).strip()
                    break

        # 4. 🎯 ยิงแจ้งเตือน LINE (Flex Message) แบบเจาะจงตัวบุคคล
        if target_line_id:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {"Authorization": f"Bearer {LINE_ACCESS_TOKEN}", "Content-Type": "application/json"}
            
            # 🎨 เลือกสีและข้อความตามสถานะ
            if new_status == "เสร็จสิ้นแล้ว":
                header_bg = "#10B981" # สีเขียว
                header_text = "✅ อัปเดต: งานเสร็จสิ้นแล้ว"
            elif new_status == "กำลังดำเนินการ":
                header_bg = "#3B82F6" # สีน้ำเงิน
                header_text = "🔄 อัปเดต: กำลังดำเนินการ"
            else:
                header_bg = "#EF4444" # สีแดง
                header_text = "🔴 อัปเดต: รอดำเนินการ"

            # 🃏 โครงสร้างการ์ด Flex Message
            flex_message = {
                "to": target_line_id,
                "messages": [
                    {
                        "type": "flex",
                        "altText": f"แจ้งเตือนสถานะงาน: {new_status}",
                        "contents": {
                            "type": "bubble",
                            "header": {
                                "type": "box",
                                "layout": "vertical",
                                "backgroundColor": header_bg,
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": header_text,
                                        "color": "#FFFFFF",
                                        "weight": "bold",
                                        "size": "md"
                                    }
                                ]
                            },
                            "body": {
                                "type": "box",
                                "layout": "vertical",
                                "spacing": "sm",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": task_title,
                                        "weight": "bold",
                                        "size": "lg",
                                        "wrap": True
                                    },
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "spacing": "sm",
                                        "contents": [
                                            {"type": "text", "text": "สถานะ:", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                            {"type": "text", "text": new_status, "weight": "bold", "color": header_bg, "size": "sm", "flex": 4}
                                        ]
                                    },
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "spacing": "sm",
                                        "contents": [
                                            {"type": "text", "text": "อัปเดตโดย:", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                            {"type": "text", "text": updater_name, "size": "sm", "flex": 4, "wrap": True}
                                        ]
                                    },
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "spacing": "sm",
                                        "contents": [
                                            {"type": "text", "text": "รายละเอียด:", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                            {"type": "text", "text": detail if detail else "-", "size": "sm", "flex": 4, "wrap": True}
                                        ]
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
            
            requests.post(url, headers=headers, json=flex_message)

        return {"status": "success", "message": "อัปเดตและแจ้งเตือนเรียบร้อย!"}
        
    except Exception as e:
        print("Error in update_task:", str(e))
        return {"status": "error", "message": f"เกิดข้อผิดพลาดหลังบ้าน: {str(e)}"}
