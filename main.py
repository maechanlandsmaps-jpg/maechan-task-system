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

# --- 1. ตั้งค่า LINE Token ---
LINE_ACCESS_TOKEN = "Rhg169BzMWPvMVBvgfwiAByT3aj516uUyUad3ryPfKLHHlJXJ6SHjTu4ySb17lI1niePQwFX7pc0hcvT7ewGzkBIvO77jBkBnjAbqQXi6XZpHHtetdJABPWKB2flLlg4xCPfYmnZrQ7DJF1+5GI2vAdB04t89/1O/w1cDnyilFU="

# --- 2. เชื่อมต่อ Google Sheets ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_path = os.path.join(os.path.dirname(__file__), "service_account.json")
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
client = gspread.authorize(creds)

sheet_tasks = client.open("Maechan_Task_Database").worksheet("Tasks")
sheet_users = client.open("Maechan_Task_Database").worksheet("Users")

DEPARTMENTS = {
    "สำนักปลัด": "Cbffc3d41c387438ecf12e9fce4535aac",
    "กองคลัง": "C6ba465d3099d4ec5cab11c0c6faebd7c",
    "กองช่าง": "Cd0db76898fddb54b3e17dcb703610bbd",
    "กองสาธารณสุข": "C44a6656153fabb50a1b4d137751e0eef",
    "กองการศึกษา": "Cd7d3d3f6228e296021139e3ab19417ae",
    "ตรวจสอบภายใน": "C0d7708c6b31c0194535edfc73dccb66b"
}

# --- ฟังก์ชันตัวช่วย: ดึง LINE ID จากชื่อ ---
def get_line_id_by_name(fullname):
    if not fullname or str(fullname).strip() == "": return ""
    try:
        users = sheet_users.get_all_records()
        for u in users:
            if str(u.get("FullName", "")).strip() == str(fullname).strip():
                return str(u.get("LINE_UserID", "")).strip()
    except Exception as e:
        print("Error reading users:", e)
    return ""

# --- ฟังก์ชันตัวช่วย: ยิง LINE หาคนสั่งและคนทำ ---
def notify_users(row_data, updater_name, action_type, detail_text, new_status=""):
    try:
        task_title = row_data[2] if len(row_data) > 2 else "ไม่ระบุชื่องาน"
        assignee_name = row_data[5] if len(row_data) > 5 else "" # คนรับงาน
        creator_name = row_data[8] if len(row_data) > 8 else ""  # คนสั่งงาน

        # ดึง LINE ID
        creator_line = get_line_id_by_name(creator_name)
        assignee_line = get_line_id_by_name(assignee_name)

        # เก็บเป้าหมายที่จะส่ง
        target_lines = set()
        if creator_line: target_lines.add(creator_line)
        if assignee_line: target_lines.add(assignee_line)

        # 💥 (เอาตัวบล็อกออกแล้ว!) ตอนนี้ส่งแจ้งเตือนเสมอแม้ตัวเองจะเป็นคนกดอัปเดตครับ
        if not target_lines: 
            print("ไม่มีเป้าหมายให้ส่ง LINE แจ้งเตือน")
            return 

        # จัดหน้าตาการ์ด Flex Message
        header_bg = "#475569" 
        header_text = "💬 มีข้อความพูดคุยใหม่"
        
        if action_type == "status_update":
            if new_status == "เสร็จสิ้นแล้ว":
                header_bg = "#10B981"
                header_text = "✅ อัปเดต: งานเสร็จสิ้นแล้ว"
            elif new_status == "กำลังดำเนินการ":
                header_bg = "#3B82F6"
                header_text = "🔄 อัปเดต: กำลังดำเนินการ"
            else:
                header_bg = "#EF4444"
                header_text = f"🔴 อัปเดต: {new_status}"

        flex_msg = {
            "type": "flex",
            "altText": header_text,
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box", "layout": "vertical", "backgroundColor": header_bg,
                    "contents": [{"type": "text", "text": header_text, "color": "#FFFFFF", "weight": "bold"}]
                },
                "body": {
                    "type": "box", "layout": "vertical", "spacing": "sm",
                    "contents": [
                        {"type": "text", "text": task_title, "weight": "bold", "size": "md", "wrap": True},
                        {"type": "box", "layout": "baseline", "spacing": "sm", "contents": [
                            {"type": "text", "text": "จาก:", "color": "#aaaaaa", "size": "sm", "flex": 2},
                            {"type": "text", "text": updater_name, "size": "sm", "flex": 5, "wrap": True}
                        ]},
                        {"type": "box", "layout": "baseline", "spacing": "sm", "contents": [
                            {"type": "text", "text": "รายละเอียด:", "color": "#aaaaaa", "size": "sm", "flex": 2},
                            {"type": "text", "text": detail_text if detail_text else "-", "size": "sm", "flex": 5, "wrap": True}
                        ]}
                    ]
                }
            }
        }

        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Authorization": f"Bearer {LINE_ACCESS_TOKEN}", "Content-Type": "application/json"}
        
        # ยิงออกไปหาทุกคนใน Set
        for line_id in target_lines:
            payload = {"to": line_id, "messages": [flex_msg]}
            requests.post(url, headers=headers, json=payload)
            
    except Exception as e:
        print("Notification Error:", e)

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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
    return {"status": "success"}

@app.post("/update-task")
async def update_task(
    row_index: int = Form(...), 
    new_status: str = Form(...), 
    detail: str = Form(...), 
    updater_name: str = Form(...)
):
    try:
        row_data = sheet_tasks.row_values(row_index)
        if not row_data: return {"status": "error", "message": "ไม่พบข้อมูลงาน"}

        # อัปเดตสถานะและข้อมูลลงชีท
        sheet_tasks.update_cell(row_index, 8, new_status)   
        sheet_tasks.update_cell(row_index, 10, f"[{updater_name}] {detail}")       

        # ยิงแจ้งเตือนทันที!
        notify_users(row_data, updater_name, "status_update", detail, new_status)

        return {"status": "success", "message": "อัปเดตและแจ้งเตือนเรียบร้อย!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/add-comment")
async def add_comment(
    row_index: int = Form(...), 
    comment_text: str = Form(...), 
    commenter_name: str = Form(...)
):
    try:
        row_data = sheet_tasks.row_values(row_index)
        if not row_data: return {"status": "error", "message": "ไม่พบข้อมูลงาน"}

        # จัดการข้อมูลคอมเมนต์
        old_comments_str = row_data[12] if len(row_data) > 12 else "[]"
        try:
            comments_list = json.loads(old_comments_str)
        except:
            comments_list = []

        new_comment = {
            "name": commenter_name,
            "text": comment_text,
            "time": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        comments_list.append(new_comment)
        sheet_tasks.update_cell(row_index, 13, json.dumps(comments_list, ensure_ascii=False))

        # ยิงแจ้งเตือนพูดคุยทันที!
        notify_users(row_data, commenter_name, "comment", comment_text)

        return {"status": "success", "message": "ส่งข้อความเรียบร้อย!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
