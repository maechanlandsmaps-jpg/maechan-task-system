# --- เพิ่มฟังก์ชันนี้สำหรับรับการอัปเดตงานและแจ้งเตือน LINE ---
@app.post("/update-task")
async def update_task(
    row_index: int = Form(...), 
    new_status: str = Form(...), 
    detail: str = Form(...), 
    updater_name: str = Form(...)
):
    try:
        # 1. ดึงข้อมูลงานเดิมจาก Sheet (row_index คือเลขแถวใน Excel เช่น แถวที่ 2)
        row_data = sheet.row_values(row_index)
        if not row_data:
            return {"status": "error", "message": "ไม่พบข้อมูลงานในระบบ"}

        task_desc = row_data[3] # คอลัมน์ D (index 3): รายละเอียดงานที่สั่ง
        group_id = row_data[5]  # คอลัมน์ F (index 5): LINE Group ID ที่เซฟไว้ตอนแรก

        # 2. อัปเดตข้อมูลใน Google Sheet
        sheet.update_cell(row_index, 5, new_status)   # อัปเดตสถานะ (คอลัมน์ E)
        sheet.update_cell(row_index, 7, detail)       # บันทึกรายละเอียด/ปัญหา (คอลัมน์ G)
        sheet.update_cell(row_index, 8, updater_name) # บันทึกชื่อคนทำ (คอลัมน์ H)

        # 3. 🎯 ไฮไลท์สำคัญ: ถ้างาน "เสร็จสิ้นแล้ว" ให้ยิง LINE แจ้งเตือนทันที!
        if new_status == "เสร็จสิ้นแล้ว" and group_id:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {"Authorization": f"Bearer {LINE_ACCESS_TOKEN}", "Content-Type": "application/json"}
            
            # จัดรูปแบบข้อความแจ้งเตือนให้สวยงาม
            msg_text = (
                f"✅ แจ้งเตือน: ปิดงานเรียบร้อย!\n"
                f"------------------------\n"
                f"📌 งาน: {task_desc}\n"
                f"👷‍♂️ ดำเนินการโดย: {updater_name}\n"
                f"📝 รายละเอียด: {detail}\n"
                f"------------------------"
            )

            data = {
                "to": group_id, # ส่งกลับไปที่กลุ่มงานนั้น เพื่อให้คนสั่งและทีมงานรับทราบ
                "messages": [{"type": "text", "text": msg_text}]
            }
            requests.post(url, headers=headers, json=data)

        return {"status": "success", "message": "บันทึกและแจ้งเตือนเรียบร้อย!"}
        
    except Exception as e:
        return {"status": "error", "message": f"เกิดข้อผิดพลาด: {str(e)}"}
