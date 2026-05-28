@app.post("/update-task")
async def update_task(
    row_index: int = Form(...), 
    new_status: str = Form(...), 
    detail: str = Form(...), 
    updater_name: str = Form(...)
):
    try:
        # 1. ดึงข้อมูลจาก Sheet ตามแถวที่ส่งมา
        row_data = sheet.row_values(row_index)
        if not row_data:
            return {"status": "error", "message": "ไม่พบข้อมูลงานในระบบ"}

        # 🚨 [จุดสำคัญที่คุณนิดต้องเช็ก!] 🚨
        # ลองนับคอลัมน์ใน Google Sheet ดูครับว่าข้อมูลเหล่านี้อยู่คอลัมน์ที่เท่าไหร่
        # (ใน Python เริ่มนับจาก 0, เช่น คอลัมน์ A=0, B=1, C=2...)
        
        task_desc = row_data[3]   # คาดว่าเป็นชื่องาน/รายละเอียด
        urgency = row_data[7] if len(row_data) > 7 else "ปกติ" # สมมติว่าความด่วนอยู่คอลัมน์ H
        
        # ⚠️ เปลี่ยนตัวเลขตรงนี้ให้ตรงกับ คอลัมน์ที่เก็บ "LINE Group ID" หรือ "LINE Token" ใน Sheet ปัจจุบันของคุณนิดนะครับ!
        line_target_id = row_data[10] if len(row_data) > 10 else "" # สมมติว่า LINE ID โดนดันไปอยู่คอลัมน์ K (index 10)

        # 2. บันทึกข้อมูลลง Google Sheet (แก้เลขคอลัมน์ให้ตรงกับ Sheet ปัจจุบันของคุณนิด)
        sheet.update_cell(row_index, 9, new_status)   # สมมติอัปเดตสถานะที่คอลัมน์ I
        sheet.update_cell(row_index, 10, detail)      # สมมติอัปเดตรายละเอียดที่คอลัมน์ J

        # 3. 🎯 ยิงแจ้งเตือน LINE (Flex Message)
        if line_target_id:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {"Authorization": f"Bearer {LINE_ACCESS_TOKEN}", "Content-Type": "application/json"}
            
            # 🎨 ตั้งค่าสีและข้อความตามสถานะ
            if new_status == "เสร็จสิ้นแล้ว":
                header_bg = "#10B981" # สีเขียว
                header_text = "✅ อัปเดต: งานเสร็จสิ้นแล้ว"
            elif new_status == "กำลังดำเนินการ":
                header_bg = "#3B82F6" # สีน้ำเงิน
                header_text = "🔄 อัปเดต: กำลังดำเนินการ"
            else:
                header_bg = "#EF4444" # สีแดง
                header_text = "🔴 อัปเดต: รอดำเนินการ"

            # 🃏 สร้างการ์ด Flex Message ให้สวยงาม
            flex_message = {
                "to": line_target_id,
                "messages": [
                    {
                        "type": "flex",
                        "altText": f"แจ้งเตือนอัปเดตสถานะงาน: {new_status}",
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
                                        "text": task_desc,
                                        "weight": "bold",
                                        "size": "lg",
                                        "wrap": True
                                    },
                                    {
                                        "type": "box",
                                        "layout": "baseline",
                                        "spacing": "sm",
                                        "contents": [
                                            {"type": "text", "text": "สถานะล่าสุด:", "color": "#aaaaaa", "size": "sm", "flex": 2},
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
            
            # ส่งคำสั่งไปที่ LINE
            response = requests.post(url, headers=headers, json=flex_message)
            print("LINE API Status:", response.status_code, response.text) # ปริ้นดูใน Console เผื่อ Error

        return {"status": "success", "message": "อัปเดตงานและแจ้งเตือนเรียบร้อย!"}
        
    except Exception as e:
        print("Error in update_task:", str(e))
        return {"status": "error", "message": f"เกิดข้อผิดพลาด: {str(e)}"}
