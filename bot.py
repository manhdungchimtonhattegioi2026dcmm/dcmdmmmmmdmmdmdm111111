import telebot
import requests
import time
import hashlib
import urllib.parse
import os
import sys
import json
import threading
from datetime import datetime

# ================== CẤU HÌNH HỆ THỐNG ==================
TOKEN = "8415663762:AAHgWl7vEtAua1bqcNPCV0n-wuO54tN1k_k"
bot = telebot.TeleBot(TOKEN)

CURRENT_VERSION = "1.0.5" # Thay đổi số này khi bạn phát hành bản mới
UPDATE_API_URL = "https://laykey.x10.mx/update/config.json"
YEUMONEY_TOKEN = "6ec3529d5d8cb18405369923670980ec155af75fb3a70c1c90c5a9d9ac25ceea"
LINK4M_API_KEY = "66d85245cc8f2674de40add1"

ADMIN_ID = 6683331082
BOT_STATUS = True # Trạng thái hoạt động (Admin /on /off)
DATA_FILE = "allowed_users.json"
TREO_FILE = "treo_data.json"
USER_LIST_FILE = "users.json" # Lưu danh sách ID để broadcast

user_keys = {}        # Key tạm thời (RAM)
allowed_users = {}    # User hợp lệ (JSON)
treo_list = {}        # Danh sách treo (JSON)
all_users = set()     # Tập hợp ID người dùng

VIP_FILE = "vip_users.json"
vip_users = {} # { "uid": expiry_timestamp }

# ================== XỬ LÝ DỮ LIỆU FILE ==================
def load_all_data():
    global allowed_users, treo_list, all_users
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                allowed_users = {str(k): v for k, v in json.load(f).items()}
        except: allowed_users = {}
    
    if os.path.exists(TREO_FILE):
        try:
            with open(TREO_FILE, "r") as f:
                treo_list = json.load(f)
        except: treo_list = {}
        
    if os.path.exists(USER_LIST_FILE):
        try:
            with open(USER_LIST_FILE, "r") as f:
                all_users = set(json.load(f))
        except: all_users = set()

    # Trong load_all_data() thêm:
    if os.path.exists(VIP_FILE):
        try:
            with open(VIP_FILE, "r") as f:
                vip_users = json.load(f)
        except: vip_users = {}

    # Sửa hàm save_data() để hỗ trợ lưu vip_users

def check_for_updates():
    print(f"🔍 Đang kiểm tra cập nhật (Phiên bản hiện tại: {CURRENT_VERSION})...")
    try:
        response = requests.get(UPDATE_API_URL, timeout=10)
        if response.status_code == 200:
            config = response.json()
            remote_version = config.get("version")
            download_url = config.get("download_url")
            update_message = config.get("message")

            if remote_version != CURRENT_VERSION:
                print(f"🆕 Tìm thấy phiên bản mới: {remote_version}")
                print(f"📝 Thông báo: {update_message}")
                
                # Tải file mới
                new_code = requests.get(download_url, timeout=30).text
                
                # Ghi đè file hiện tại
                filename = os.path.basename(__file__)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(new_code)
                
                print("✅ Đã cập nhật xong! Đang khởi động lại Bot...")
                
                # Gửi thông báo cho Admin nếu cần
                bot.send_message(ADMIN_ID, f"🚀 **Hệ thống đã tự động cập nhật lên bản {remote_version}**\n`{update_message}`", parse_mode="Markdown")
                
                # Khởi động lại chương trình
                os.execv(sys.executable, ['python'] + sys.argv)
            else:
                print("✅ Bạn đang sử dụng phiên bản mới nhất.")
    except Exception as e:
        print(f"🚨 Lỗi kiểm tra cập nhật: {e}")

# Gọi hàm kiểm tra ngay khi chạy script
check_for_updates()

def save_data(file, data):
    with open(file, "w") as f:
        if isinstance(data, set):
            json.dump(list(data), f)
        else:
            json.dump(data, f, indent=4)

load_all_data()

# ================== HỆ THỐNG TREO AUTO ==================
def auto_treo_worker():
    while True:
        now = int(time.time())
        for username, info in list(treo_list.items()):
            # Kiểm tra hết hạn ngày treo
            if now > info['expiry_treo']:
                del treo_list[username]
                save_data(TREO_FILE, treo_list)
                bot.send_message(ADMIN_ID, f"🔔 **Hết hạn treo cho:** `@{username}`", parse_mode="Markdown")
                continue
            
            # Kiểm tra chu kỳ delay (giây)
            if now >= (info['last_buff'] + info['delay']):
                try:
                    r = requests.get(f"https://liggdzut.x10.mx/fl.php?fl={username}&key=liggdzut", timeout=30).json()
                    treo_list[username]['last_buff'] = now
                    save_data(TREO_FILE, treo_list)
                    
                    if r.get("status") == "success":
                        d = r.get("data", {})
                        msg = (f"🔄 **[AUTO REPORT]**\n"
                               f"👤 Nick: `@{username}`\n"
                               f"✨ Tăng: `+{d.get('follow_added')}`\n"
                               f"📊 Sau buff: `{d.get('follow_after')}`")
                        bot.send_message(ADMIN_ID, msg, parse_mode="Markdown")
                except: pass
        time.sleep(15)

threading.Thread(target=auto_treo_worker, daemon=True).start()

# ================== ADMIN COMMANDS ==================
def is_admin(uid): return str(uid) == str(ADMIN_ID)

@bot.message_handler(commands=['on', 'off'])
def toggle_bot(message):
    global BOT_STATUS
    if not is_admin(message.from_user.id): return
    BOT_STATUS = (message.text == "/on")
    bot.reply_to(message, f"⚙️ **Trạng thái Bot:** {'🟢 Hoạt động' if BOT_STATUS else '🔴 Bảo trì'}", parse_mode="Markdown")

# ================== ADMIN: QUẢN LÝ VIP & HỆ THỐNG ==================

@bot.message_handler(commands=['stats', 'tk'])
def handle_stats(message):
    uid = str(message.from_user.id)
    now = int(time.time())
    
    # Tính toán thông tin hệ thống (dành cho Admin)
    total_users = len(all_users)
    total_treo = len(treo_list)
    total_allowed = len(allowed_users)
    
    # Kiểm tra trạng thái cá nhân
    status_key = "❌ Chưa kích hoạt"
    if uid in allowed_users:
        rem_key = (allowed_users[uid] - now) // 60
        status_key = f"✅ Đã kích hoạt (Còn {rem_key} phút)" if rem_key > 0 else "❌ Hết hạn"
        
    status_vip = "❌ Thường"
    if uid in vip_users:
        rem_vip = (vip_users[uid] - now) // 3600
        status_vip = f"💎 VIP (Còn {rem_vip} giờ)" if rem_vip > 0 else "❌ VIP Hết hạn"

    text = f"""📊 **THỐNG KÊ NGƯỜI DÙNG**
───────────────
👤 ID: `{uid}`
🗝 Trạng thái Key: {status_key}
💎 Cấp bậc: {status_vip}
"""
    if is_admin(uid):
        text += f"""
───────────────
⚙️ **QUẢN TRỊ HỆ THỐNG**
👥 Tổng User: `{total_users}`
🔑 Key đang dùng: `{total_allowed}`
🔄 Nick đang treo: `{total_treo}`
⚙️ Bot Status: {'🟢 ON' if BOT_STATUS else '🔴 OFF'}
"""
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['adhelp', 'admin'])
def handle_adhelp(message):
    if not is_admin(message.from_user.id): return
    
    text = """🛠 **BẢNG LỆNH ADMIN**
───────────────
🟢 `/on` / `/off` : Bật/Tắt bảo trì Bot.
📢 `/broadcast [nội dung]` : Gửi tin nhắn cho toàn bộ người dùng.
🎫 `/taokey [ngày]` : Tạo mã VIP cho người dùng.
📋 `/checkvip` : Xem danh sách các ID đang có VIP.
🔄 `/treo` : Xem danh sách tất cả các nick đang treo auto.
📊 `/stats` : Xem thông số chi tiết hệ thống.
───────────────
⚠️ *Lưu ý: Không chia sẻ quyền Admin cho người lạ.*"""
    
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['taokey'])
def admin_create_key_vip(message):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 2: 
        return bot.reply_to(message, "❌ Sử dụng: `/taokey [số ngày]`", parse_mode="Markdown")
    
    days = int(args[1])
    # Tạo mã key ngẫu nhiên
    raw_hash = hashlib.md5(f"VIP-{time.time()}".encode()).hexdigest()
    vip_key = f"VIP_{days}D_{raw_hash[:15].upper()}"
    
    # Lưu tạm vào user_keys (tận dụng hệ thống key có sẵn của bạn)
    # Thêm flag 'vip_days' để phân biệt với key thường
    user_keys[vip_key] = {"days": days, "type": "VIP"}
    
    bot.reply_to(message, f"🎫 **KEY VIP ĐÃ TẠO:**\n`{vip_key}`\n⏳ Thời hạn: `{days} ngày`\n📌 Gửi mã này cho người dùng để họ nhập `/vip {vip_key}`", parse_mode="Markdown")

@bot.message_handler(commands=['checkvip'])
def admin_check_vip(message):
    if not is_admin(message.from_user.id): return
    if not vip_users: return bot.reply_to(message, "Chưa có ai là VIP.")
    
    txt = "💎 **DANH SÁCH VIP:**\n"
    now = int(time.time())
    for uid, expiry in list(vip_users.items()):
        con_lai = (expiry - now) // 3600
        txt += f"- ID: `{uid}` | Còn: `{con_lai} giờ`\n"
    bot.reply_to(message, txt, parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if not is_admin(message.from_user.id): return
    msg_text = message.text.replace("/broadcast", "").strip()
    if not msg_text: return bot.reply_to(message, "❌ **Vui lòng nhập nội dung!**", parse_mode="Markdown")
    
    success, fail = 0, 0
    for uid in all_users:
        try:
            bot.send_message(uid, f"📢 **THÔNG BÁO TỪ ADMIN**\n───────────────\n{msg_text}", parse_mode="Markdown")
            success += 1
        except: fail += 1
    bot.reply_to(message, f"✅ **Broadcast xong!**\n- Thành công: `{success}`\n- Thất bại: `{fail}`", parse_mode="Markdown")

@bot.message_handler(commands=['treo'])
def handle_treo(message):
    uid = str(message.from_user.id)
    # Kiểm tra quyền: Là Admin HOẶC là VIP còn hạn
    is_vip = uid in vip_users and int(time.time()) < vip_users[uid]
    
    if not is_admin(uid) and not is_vip:
        return bot.reply_to(message, "💎 **Lệnh này chỉ dành cho VIP!**\nVui lòng liên hệ Admin hoặc dùng Key VIP để mở khóa.", parse_mode="Markdown")

    args = message.text.split()
    if len(args) == 4: # /treo [user] [giây] [ngày]
        user, delay, days = args[1].replace("@", ""), int(args[2]), int(args[3])
        
        # Giới hạn cho VIP (Tránh treo quá lâu hoặc delay quá thấp nếu cần)
        if not is_admin(uid) and delay < 60:
            return bot.reply_to(message, "⚠️ VIP chỉ được treo tối thiểu delay `60s`!")

        expiry = int(time.time()) + (days * 86400)
        treo_list[user] = {"delay": delay, "expiry_treo": expiry, "last_buff": 0, "owner": uid}
        save_data(TREO_FILE, treo_list)
        bot.reply_to(message, f"✅ **Đã bắt đầu treo!**\n👤 Nick: `@{user}`\n⏱ Chu kỳ: `{delay}s`\n📅 Thời hạn: `{days} ngày`", parse_mode="Markdown")
        
    elif len(args) == 3 and args[1] == "off":
        user = args[2].replace("@", "")
        if user in treo_list:
            # Chỉ cho phép chủ sở hữu hoặc admin tắt
            if not is_admin(uid) and treo_list[user].get("owner") != uid:
                return bot.reply_to(message, "❌ Bạn không có quyền dừng nick này!")
                
            del treo_list[user]
            save_data(TREO_FILE, treo_list)
            bot.reply_to(message, f"⏹ **Đã dừng treo cho:** `@{user}`", parse_mode="Markdown")
    else:
        # Show danh sách
        if not treo_list: return bot.reply_to(message, "📝 **Không có nick nào đang treo.**", parse_mode="Markdown")
        txt = "📋 **DANH SÁCH TREO:**\n"
        for u, i in treo_list.items():
            # Chỉ admin thấy hết, người dùng chỉ thấy nick mình treo (tùy chỉnh)
            if is_admin(uid) or i.get("owner") == uid:
                txt += f"- `@{u}` | `{i['delay']}s`\n"
        bot.reply_to(message, txt, parse_mode="Markdown")

# ================== USER COMMANDS ==================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    uid = message.from_user.id
    if uid not in all_users:
        all_users.add(uid)
        save_data(USER_LIST_FILE, all_users)
    
    text = """```
╭─────────────⭓
│ 🤖 BOT TIKTOK SERVICE
├─────────────⭓
│ /getkey : Lấy mã sử dụng
│ /key [mã] : Xác thực Key
│ /vip [mã] : Kích hoạt VIP
│ /stats  : Xem thông tin cá nhân
├─────────────⭓
│ /fl [user] : Buff Follow
│ /view [link] : Buff View
│ /like [link] : Buff Like
│ /treo [user] [giây] [ngày] : Treo Auto (VIP)
╰─────────────⭓
```"""
    if is_admin(uid):
        text += "\n👑 *Admin:* Gõ `/adhelp` để xem lệnh quản lý."
        
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['vip'])
def user_redeem_vip(message):
    uid = str(message.from_user.id)
    args = message.text.split()
    if len(args) < 2: return bot.reply_to(message, "❌ Vui lòng nhập mã: `/vip [mã_key]`")
    
    key_input = args[1].strip()
    
    # Kiểm tra key trong danh sách tạm user_keys
    if key_input in user_keys and user_keys[key_input].get("type") == "VIP":
        days = user_keys[key_input]["days"]
        expiry_vip = int(time.time()) + (days * 86400)
        
        # Lưu vào danh sách VIP
        vip_users[uid] = expiry_vip
        save_data(VIP_FILE, vip_users)
        
        # Xóa key đã dùng
        del user_keys[key_input]
        
        bot.reply_to(message, f"💎 **CHÚC MỪNG!**\nBạn đã trở thành **VIP** trong `{days} ngày`.\nBây giờ bạn có thể sử dụng lệnh `/treo`.", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ Mã VIP không đúng hoặc đã được sử dụng!")

@bot.message_handler(commands=['getkey'])
def handle_getkey(message):
    if not BOT_STATUS and not is_admin(message.from_user.id):
        return bot.reply_to(message, "⚠️ **Hệ thống đang bảo trì!**", parse_mode="Markdown")
    
    uid = str(message.from_user.id)
    raw_hash = hashlib.md5(f"DKEY-{uid}-{time.time()}".encode()).hexdigest()
    key_code = f"dkey_{raw_hash[:15].upper()}"
    user_keys[uid] = {"key": key_code, "expiry": int(time.time()) + 3600}

    # Báo Admin
    print(f"[DEBUG] New key generated: {key_code} for user {uid}")
    bot.send_message(ADMIN_ID, f"🔑 **THÔNG BÁO KEY:**\n👤 `{message.from_user.first_name}`\n🆔 `{uid}`\n🗝 `{key_code}`", parse_mode="Markdown")

    base_url = f"https://laykey.x10.mx/index.html?ma={key_code}"
    final_url = None

    # --- BƯỚC 1: Thử Yeumoney ---
    try:
        print(f"[DEBUG] Trying Yeumoney for {uid}")
        ym_res = requests.get(
            f"https://yeumoney.com/QL_api.php?token={YEUMONEY_TOKEN}&format=json&url={urllib.parse.quote(base_url)}",
            timeout=10,
            verify=False  # Bỏ SSL tạm thời
        ).json()
        if ym_res.get("status") == "success":
            final_url = ym_res.get("shortenedUrl")
            print(f"[DEBUG] Yeumoney success: {final_url}")
        else:
            print(f"[DEBUG] Yeumoney failed: {ym_res}")
            final_url = None
    except Exception as e:
        print(f"[DEBUG] Yeumoney exception: {e}")
        final_url = None

    # --- BƯỚC 2: Nếu Yeumoney OK thì tiếp tục rút gọn Link4M ---
    if final_url:
        try:
            print(f"[DEBUG] Trying Link4M to further shorten Yeumoney link for {uid}")
            l4m_res = requests.get(
                f"https://link4m.co/api-shorten/v2?api={LINK4M_API_KEY}&url={urllib.parse.quote(final_url)}",
                timeout=20,
            ).json()
            if l4m_res.get("status") == "success":
                final_url = l4m_res.get("shortenedUrl")
                print(f"[DEBUG] Link4M success: {final_url}")
            else:
                print(f"[DEBUG] Link4M failed: {l4m_res}, using Yeumoney link")
        except Exception as e:
            print(f"[DEBUG] Link4M exception: {e}, using Yeumoney link")
    
    # --- BƯỚC 3: Nếu Yeumoney lỗi, thử trực tiếp Link4M ---
    if not final_url:
        try:
            print(f"[DEBUG] Yeumoney failed, trying Link4M directly for {uid}")
            l4m_res = requests.get(
                f"https://link4m.co/api-shorten/v2?api={LINK4M_API_KEY}&url={urllib.parse.quote(base_url)}",
                timeout=20,
            ).json()
            if l4m_res.get("status") == "success":
                final_url = l4m_res.get("shortenedUrl")
                print(f"[DEBUG] Link4M direct success: {final_url}")
            else:
                print(f"[DEBUG] Link4M direct failed: {l4m_res}")
        except Exception as e:
            print(f"[DEBUG] Link4M direct exception: {e}")

    # --- BƯỚC 4: Nếu cả 2 đều lỗi ---
    if not final_url:
        print(f"[DEBUG] Both shorten services failed for user {uid}")
        bot.reply_to(message, "❌ **Không thể rút gọn link, vui lòng thử lại sau!**", parse_mode="Markdown")
        return

    # --- Gửi link cho user ---
    txt = f"""```
╭─────────────⭓
│ 🔑 GetKey
├─────────────⭓
│ 🌐 Link: {final_url}
│ ⏳ Hạn dùng: 24 giờ
│ 📌 /key + mã để dùng
╰─────────────⭓
```"""
    bot.reply_to(message, txt, parse_mode="Markdown")

@bot.message_handler(commands=['key'])
def handle_verify(message):
    uid = str(message.from_user.id)
    args = message.text.split()
    if len(args) < 2: return bot.reply_to(message, "❌ **Vui lòng nhập mã key!**", parse_mode="Markdown")
    
    input_key = args[1].strip()
    if uid in user_keys and user_keys[uid]["key"] == input_key:
        allowed_users[uid] = int(time.time()) + 21600
        save_data(DATA_FILE, allowed_users)
        del user_keys[uid]
        bot.reply_to(message, "✅ **Xác thực thành công! **", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ **Mã key không đúng hoặc đã hết hạn!**", parse_mode="Markdown")

# ================== LỆNH BUFF VIEW & LIKE (YÊU CẦU KEY) ==================

@bot.message_handler(commands=['view', 'like'])
def handle_view_like(message):
    uid = str(message.from_user.id)
    
    # 1. Kiểm tra trạng thái bảo trì
    if not BOT_STATUS and not is_admin(uid): 
        return bot.reply_to(message, "⚠️ **Hệ thống đang bảo trì!**", parse_mode="Markdown")
    
    # 2. Kiểm tra Key (Yêu cầu Getkey)
    if uid not in allowed_users or int(time.time()) > allowed_users[uid]:
        return bot.reply_to(message, "⚠️ **Vui lòng /getkey để sử dụng lệnh này!**", parse_mode="Markdown")
    
    # 3. Kiểm tra tham số (Link)
    args = message.text.split()
    if len(args) < 2: 
        cmd = args[0]
        return bot.reply_to(message, f"❌ **Thiếu link!**\nSử dụng: `{cmd} [link_tiktok]`", parse_mode="Markdown")
    
    video_url = args[1].strip()
    cmd_type = "view" if "/view" in args[0].lower() else "like"
    
    # --- THIẾT LẬP SỐ LƯỢNG TĂNG THEO LOẠI ---
    buff_amount = "10" if cmd_type == "view" else "250"
    
    # Gửi tin nhắn chờ
    temp_msg = bot.send_message(message.chat.id, f"⏳ **Đang gửi yêu cầu Buff {cmd_type.upper()}...**", parse_mode="Markdown")
    
    try:
        # Gọi API PHP (id=view hoặc id=like)
        api_endpoint = f"https://laykey.x10.mx/view.php?link={video_url}&id={cmd_type}"
        r = requests.get(api_endpoint, timeout=45).json()
        
        if r.get("status") == "success":
            # Nếu thành công
            res_text = (
                f"✅ **BUFF {cmd_type.upper()} THÀNH CÔNG**\n"
                f"───────────────\n"
                f"👤 Nick: `{message.from_user.first_name}`\n"
                f"✨ Tăng: `+{buff_amount}` {cmd_type.capitalize()}\n"
                f"📦 Order ID: `{r.get('order_id')}`\n"
                f"⏳ Hồi chiêu: `{r.get('next_wait') // 60} phút`"
            )
            bot.edit_message_text(res_text, message.chat.id, temp_msg.message_id, parse_mode="Markdown")
        else:
            # Xử lý lỗi (Hồi chiêu tiếng Pháp hoặc link sai)
            msg_error = r.get("message", "Hệ thống bận")
            bot.edit_message_text(f"❌ **Lỗi API:**\n`{msg_error}`", message.chat.id, temp_msg.message_id, parse_mode="Markdown")
            
    except Exception as e:
        bot.edit_message_text(f"🚨 **Lỗi hệ thống:** Không thể kết nối tới API PHP!", message.chat.id, temp_msg.message_id, parse_mode="Markdown")

# ========================================================================

import re

@bot.message_handler(commands=['fl', 'follow', 'buff', 'folow', 'tang'])
def handle_buff(message):
    uid = str(message.from_user.id)
    if not BOT_STATUS and not is_admin(uid): 
        return bot.reply_to(message, "⚠️ **Bảo trì!**", parse_mode="Markdown")
    
    if uid not in allowed_users or int(time.time()) > allowed_users[uid]:
        return bot.reply_to(message, "⚠️ **Vui lòng /getkey trước khi dùng!**", parse_mode="Markdown")
    
    args = message.text.split()
    if len(args) < 2: 
        return bot.reply_to(message, "❌ **Nhập thiếu username!**", parse_mode="Markdown")
    
    # 1. Xử lý lấy Username sạch
    raw_user = args[1].replace("@", "")
    match = re.search(r'([a-zA-Z0-9._]{2,})', raw_user)
    if not match: 
        return bot.reply_to(message, "❌ **Username không hợp lệ!**")
    user = match.group(1).strip('.')

    temp_msg = bot.send_message(message.chat.id, f"```⏳ Đang kiểm tra profile @{user}...```", parse_mode="Markdown")
    
    try:
        # BƯỚC 1: Check thông tin và Follower hiện tại
        check_url = f"https://keyherlyswar.x10.mx/Apidocs/getinfotiktok.php?username={user}"
        info_res = requests.get(check_url, timeout=20).json()
        
        if "followerCount" not in info_res:
            return bot.edit_message_text("❌ **Không tìm thấy người dùng!**", message.chat.id, temp_msg.message_id)
        
        follow_before = info_res.get("followerCount", 0)
        nickname = info_res.get("nickname", user)
        # Lấy AVATAR thật của người dùng
        user_avatar = info_res.get("avatarLarger") or info_res.get("avatarMedium") or "https://i.imgur.com/9p6ZiSb.png"

        # BƯỚC 2: Gọi lệnh Buff
        bot.edit_message_text(f"```🚀 Đang buff cho {nickname}...```", message.chat.id, temp_msg.message_id, parse_mode="Markdown")
        buff_res = requests.get(f"https://liggdzut.x10.mx/fl.php?fl={user}&key=liggdzut", timeout=60).json()
        
        if buff_res.get("status") == "success":
            # BƯỚC 3: Nghỉ 12 giây để TikTok cập nhật số liệu
            bot.edit_message_text(f"```⏳ Chờ hệ thống cập nhật (12s)...```", message.chat.id, temp_msg.message_id, parse_mode="Markdown")
            time.sleep(12)
            
            # BƯỚC 4: Check lại lần cuối để lấy số sau khi buff
            info_after = requests.get(check_url, timeout=20).json()
            follow_after = info_after.get("followerCount", 0)
            real_added = follow_after - follow_before
            if real_added < 0: real_added = 0 

            text = f"""```
╭─────────────⭓
│ ✅ BUFF FOLLOW XONG
├─────────────⭓
│ 👤 Nick: {nickname}
│ 🔹 Trước: {follow_before}
│ 🔸 Sau: {follow_after}
│ ✨ Thực tăng: +{real_added}
│ ─────────────
│ 💕 Cảm ơn bạn đã sử dụng Bot!
│ 📢 Thấy tốt hãy mời bạn bè nhé!
╰─────────────⭓
```"""
            # Xóa tin nhắn chờ và gửi ảnh AVATAR người dùng kèm bảng kết quả
            bot.delete_message(message.chat.id, temp_msg.message_id)
            bot.send_photo(message.chat.id, user_avatar, caption=text, parse_mode="Markdown")
        else:
            bot.edit_message_text(f"❌ **Lỗi:** {buff_res.get('message')}", message.chat.id, temp_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"🚨 **Lỗi API:** Không thể lấy dữ liệu!", message.chat.id, temp_msg.message_id)

bot.infinity_polling()