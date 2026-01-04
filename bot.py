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

# ================== CẤU HÌNH REPORT ==================
REPORT_CHAT_ID = -1002542187639
REPORT_TOPIC_ID = 11780
CURRENT_VERSION = "7.0.6" # Thay đổi số này khi bạn phát hành bản mới
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

REFERRAL_FILE = "referrals.json"
REF_CONFIG_FILE = "ref_config.json"

referrals = {} # { "uid": {"count": 0, "invited_users": [], "claimed": False} }
ref_config = {"required": 20, "reward_days": 5} # Mặc định 20 người được 5 ngày VIP
# ================== XỬ LÝ DỮ LIỆU FILE ==================

import sys
import io

# Ép console xuất dữ liệu chuẩn UTF-8 để hiện Emoji
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def load_all_data():
    global allowed_users, treo_list, all_users
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                allowed_users = {str(k): v for k, v in json.load(f).items()}
        except: allowed_users = {}
    
    global referrals, ref_config
    if os.path.exists(REFERRAL_FILE):
        try:
            with open(REFERRAL_FILE, "r") as f: referrals = json.load(f)
        except: referrals = {}
    if os.path.exists(REF_CONFIG_FILE):
        try:
            with open(REF_CONFIG_FILE, "r") as f: ref_config = json.load(f)
        except: ref_config = {"required": 20, "reward_days": 5}
        
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
@bot.message_handler(commands=['listtreo'])
def list_treo(message):
    if not is_admin(message.from_user.id): return
    
    if not treo_list:
        return bot.reply_to(message, "📭 Hiện tại không có link nào đang treo.")
    
    txt = "📊 **DANH SÁCH ĐANG TREO HỆ THỐNG**\n"
    txt += "────────────────\n"
    
    for i, (key, info) in enumerate(treo_list.items(), 1):
        target = info.get('target', 'Không rõ')
        t_type = info.get('type', 'all').upper()
        # Tính thời gian còn lại
        remaining = info['expiry_treo'] - int(time.time())
        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        
        # Rút gọn link nếu quá dài để tránh lỗi hiển thị telegram
        display_target = (target[:25] + '...') if len(target) > 25 else target
        
        txt += f"{i}. `{display_target}`\n"
        txt += f"   Type: `{t_type}` | Còn: `{days}n {hours}h` | ID: `{key}`\n"
        
        # Giới hạn hiển thị 20 link mỗi tin nhắn để tránh quá tải
        if i % 20 == 0:
            bot.send_message(message.chat.id, txt, parse_mode="Markdown")
            txt = ""

    if txt:
        bot.send_message(message.chat.id, txt, parse_mode="Markdown")
@bot.message_handler(commands=['huytreo', 'stop'])
def stop_treo(message):
    uid = str(message.from_user.id)
    args = message.text.split()
    
    if len(args) < 2:
        return bot.reply_to(message, "❌ Vui lòng nhập **ID treo** hoặc **Link/User** cần hủy.\nSử dụng `/listtreo` để lấy ID (dành cho Admin).", parse_mode="Markdown")
    
    input_val = args[1]
    found = False
    
    # Duyệt tìm trong danh sách treo
    for key, info in list(treo_list.items()):
        # Kiểm tra nếu input khớp với ID (key) hoặc khớp với Target (Link/User)
        if input_val == key or input_val == info.get('target'):
            # Kiểm tra quyền: Phải là chủ sở hữu hoặc Admin
            if is_admin(uid) or info.get('owner') == uid:
                del treo_list[key]
                save_data(TREO_FILE, treo_list)
                bot.reply_to(message, f"✅ Đã dừng treo thành công cho: `{info.get('target')}`")
                
                # Báo cáo về Group Admin
                bot.send_message(REPORT_CHAT_ID, f"🚫 **[HUY TREO]**\n👤 Người thực hiện: `{uid}`\n🎯 Mục tiêu: `{info.get('target')}`", message_thread_id=REPORT_TOPIC_ID, parse_mode="Markdown")
                found = True
                break
            else:
                return bot.reply_to(message, "⚠️ Bạn không có quyền dừng link này!")

    if not found:
        bot.reply_to(message, "❌ Không tìm thấy mục tiêu này trong danh sách đang treo.")

import sys

def auto_update_worker():
    """Luồng chạy ngầm kiểm tra cập nhật liên tục"""
    while True:
        try:
            # Tải cấu hình từ server
            response = requests.get(UPDATE_API_URL, timeout=15)
            if response.status_code == 200:
                config = response.json()
                remote_version = config.get("version")
                download_url = config.get("download_url")

                # So sánh phiên bản
                if remote_version and remote_version != CURRENT_VERSION:
                    print(f"🆕 Phát hiện bản mới {remote_version}. Đang tiến hành nâng cấp...")
                    
                    # Tải mã nguồn mới
                    new_code = requests.get(download_url, timeout=30).text
                    
                    if "import telebot" in new_code: # Kiểm tra sơ bộ xem file có hợp lệ không
                        filename = os.path.abspath(sys.argv[0])
                        # Tìm dòng này trong hàm auto_update_worker của bạn và sửa thành:
                        new_code = new_code.replace('\r\n', '\n')
                        with open(filename, "w", encoding="utf-8", newline='\n') as f:
                            f.write(new_code)
                        
                        print("✅ Đã ghi đè file mới. Đang khởi động lại hệ thống...")
                        # Thông báo cho Admin trước khi tắt
                        try:
                            bot.send_message(ADMIN_ID, f"🚀 **Hệ thống đang tự nâng cấp:** `{CURRENT_VERSION}` ➔ `{remote_version}`\n🔔 Nội dung: `{config.get('message')}`", parse_mode="Markdown")
                        except: pass
                        
                        # Khởi động lại script chính
                        os.execv(sys.executable, ['python'] + sys.argv)
                    else:
                        print("🚨 File tải về không hợp lệ, hủy cập nhật.")
            
        except Exception as e:
            print(f"⚠️ Lỗi kiểm tra cập nhật: {e}")
            
        # Kiểm tra lại sau mỗi 300 giây (5 phút) - Đừng để quá thấp tránh bị server chặn
        time.sleep(300)

# Kích hoạt luồng cập nhật ngầm
threading.Thread(target=auto_update_worker, daemon=True).start()

def save_data(file, data):
    with open(file, "w") as f:
        if isinstance(data, set):
            json.dump(list(data), f)
        else:
            json.dump(data, f, indent=4)

load_all_data()

# ================== HỆ THỐNG TREO AUTO ==================
import threading
import time
import requests

import time
import requests

import random # Thêm ở đầu file để dùng cho việc chống cache

def auto_treo_worker():
    print("--- 🔄 Hệ thống Treo Real-time (Fixed Laykey Check) bắt đầu ---")
    
    while True:
        try:
            now = int(time.time())
            items = list(treo_list.items())
            
            for key_name, info in items:
                try:
                    target = info.get('target')
                    if not target: continue 
                        
                    expiry_treo = int(info.get('expiry_treo', 0))
                    last_buff = int(info.get('last_buff', 0))
                    delay = int(info.get('delay', 30))
                    target_type = info.get('type', 'follow')

                    if now > expiry_treo:
                        if key_name in treo_list:
                            del treo_list[key_name]
                            save_data(TREO_FILE, treo_list)
                        continue
                    
                    if now >= (last_buff + delay):
                        u_name = str(target).replace("@", "").split("/")[-1].strip()
                        # Thêm r={ngẫu nhiên} để tránh API laykey trả về kết quả cũ đã lưu trong bộ nhớ đệm
                        check_url = f"https://laykey.x10.mx/infott.php?user={u_name}&r={random.randint(1,9999)}"
                        success = False
                        details = ""

                        if target_type == 'follow':
                            # --- BƯỚC 1: CHECK TRƯỚC (DÙNG LAYKEY) ---
                            try:
                                res_pre = requests.get(check_url, timeout=15).json()
                                fb = int(res_pre.get("followers", 0))
                            except:
                                fb = 8
                            
                            # --- BƯỚC 2: THỰC HIỆN BUFF ---
                            buff_res = requests.get(f"https://liggdzut.x10.mx/fl.php?fl={u_name}&key=liggdzut", timeout=30).json()
                            
                            if buff_res.get("status") == "success":
                                # --- BƯỚC 3: ĐỢI VÀ CHECK SAU (DÙNG LAYKEY) ---
                                # Tăng thời gian chờ lên một chút để TikTok kịp nhảy số
                                time.sleep(20) 
                                
                                try:
                                    # Gọi lại check_url với random mới để ép lấy dữ liệu mới nhất
                                    res_post = requests.get(f"{check_url}{random.randint(1,20)}", timeout=15).json()
                                    fa = int(res_post.get("followers", 0))
                                except:
                                    fa = fb # Nếu lỗi check sau thì coi như chưa tăng để tránh lỗi tính toán
                                
                                real_added = fa - fb
                                if real_added < 0: real_added = 8
                                
                                details = (f"│ 🔹 Trước (: <b>{fb}</b>\n"
                                           f"│ 🔸 Sau : <b>{fa}</b>\n"
                                           f"│ ✨ Thực tăng: <b>+{real_added} Follow</b>")
                                success = True

                        elif target_type in ['view', 'like']:
                            r = requests.get(f"https://laykey.x10.mx/view.php?link={target}&id={target_type}", timeout=15).json()
                            if r.get("status") == "success":
                                amount = "250 VIEW" if target_type == 'view' else "10 LIKE"
                                details = f"│ ⚡ Trạng thái: <b>+{amount}</b>"
                                success = True

                        # --- GỬI BÁO CÁO TELEGRAM ---
                        if success:
                            html_msg = (
                                f"<b>🔄 [ AUTO REPORT SYSTEM ]</b>\n"
                                f"<code>────────────────────────</code>\n"
                                f"🎯 <b>Mục tiêu:</b> <code>{target}</code>\n"
                                f"🛠 <b>Dịch vụ:</b> <b>{target_type.upper()}</b>\n"
                                f"<code>────────────────────────</code>\n"
                                f"{details}\n"
                                f"<code>────────────────────────</code>\n"
                                f"✅ <b>Trạng thái:</b> <i>Hoàn thành chu kỳ!</i>"
                            )
                            bot.send_message(REPORT_CHAT_ID, html_msg, message_thread_id=REPORT_TOPIC_ID, parse_mode="HTML")
                            
                            treo_list[key_name]['last_buff'] = int(time.time())
                            save_data(TREO_FILE, treo_list)

                except Exception as inner_e:
                    print(f"Lỗi: {inner_e}")
            time.sleep(5)
        except Exception as e:
            time.sleep(10)

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

def perform_update(config):
    """Hàm thực hiện tải code mới và khởi động lại bot"""
    remote_version = config.get("version")
    download_url = config.get("download_url")
    
    try:
        print(f"🆕 Đang tải bản cập nhật {remote_version}...")
        new_code = requests.get(download_url, timeout=30).text
        
        if "import telebot" in new_code:
            filename = os.path.abspath(sys.argv[0])
            new_code = new_code.replace('\r\n', '\n')
            
            with open(filename, "w", encoding="utf-8", newline='\n') as f:
                f.write(new_code)
            
            print("✅ Ghi file thành công. Đang khởi động lại...")
            try:
                bot.send_message(ADMIN_ID, f"🚀 **Hệ thống đã nâng cấp lên:** `{remote_version}`\n🔔 Nội dung: `{config.get('message')}`", parse_mode="Markdown")
            except: pass
            
            # Khởi động lại
            os.execv(sys.executable, ['python'] + sys.argv)
            return True
    except Exception as e:
        print(f"🚨 Lỗi khi thực hiện update: {e}")
    return False

@bot.message_handler(commands=['checkupdate', 'up'])
def manual_check_update(message):
    if not is_admin(message.from_user.id): return
    
    bot.reply_to(message, "🔍 **Đang kiểm tra và cập nhật ngay...**", parse_mode="Markdown")
    try:
        response = requests.get(UPDATE_API_URL, timeout=15)
        if response.status_code == 200:
            config_data = response.json()
            remote_version = config_data.get("version")
            
            if remote_version != CURRENT_VERSION:
                bot.send_message(message.chat.id, f"🆕 Phát hiện bản mới: `{remote_version}`. Tiến hành tải về...", parse_mode="Markdown")
                # Gọi hàm cập nhật ngay lập tức
                if not perform_update(config_data):
                    bot.reply_to(message, "❌ Cập nhật thất bại (Lỗi ghi file hoặc tải code).")
            else:
                bot.reply_to(message, f"✅ Bạn đang dùng bản mới nhất (`{CURRENT_VERSION}`).", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi kết nối: {e}")

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
    u_vip = vip_users.get(uid)
    is_vip = u_vip and int(time.time()) < u_vip.get('expiry', 0)
    
    if not is_admin(uid) and not is_vip:
        return bot.reply_to(message, "💎 Lệnh này chỉ dành cho VIP!")

    args = message.text.split() 
    # Cú pháp: /treo [link_hoặc_user] [giây] [ngày] [loại]
    if len(args) == 5:
        target = args[1]
        delay = max(int(args[2]), 30)
        days = int(args[3])
        req_type = args[4].lower()

        # Kiểm tra quyền Key VIP
        allowed = u_vip.get('service', 'all') if not is_admin(uid) else 'all'
        if allowed != 'all' and req_type != allowed:
            return bot.reply_to(message, f"❌ Key của bạn chỉ hỗ trợ: `{allowed.upper()}`")

        expiry = int(time.time()) + (days * 86400)
        # Dùng target làm key lưu trữ để tránh trùng lặp
        storage_key = hashlib.md5(target.encode()).hexdigest()[:10]
        
        treo_list[storage_key] = {
            "target": target,
            "delay": int(delay), # Ép kiểu số
            "expiry_treo": int(expiry), # Ép kiểu số
            "last_buff": 0, 
            "type": req_type,
            "owner": uid  # <--- THÊM DÒNG NÀY
        }
        save_data(TREO_FILE, treo_list)
        bot.reply_to(message, f"✅ **Đã nhận treo {req_type.upper()}!**\n🔗 Đích: `{target}`\n⏱ Chu kỳ: `{delay}s`", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❓ **Sử dụng:** `/treo [Link/User] [Giây] [Ngày] [Loại]`\n*(Loại: view, like, follow, all)*")

# ================== USER COMMANDS ==================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    uid = str(message.from_user.id)
    args = message.text.split()
    
    # Lưu người dùng mới vào danh sách hệ thống
    if int(uid) not in all_users:
        all_users.add(int(uid))
        save_data(USER_LIST_FILE, all_users)
        
        # XỬ LÝ GIỚI THIỆU
        if len(args) > 1 and args[1].isdigit():
            referrer_id = args[1]
            if referrer_id != uid: # Không tự giới thiệu chính mình
                if referrer_id not in referrals:
                    referrals[referrer_id] = {"count": 0, "invited_users": [], "claimed_count": 0}
                
                # Thêm vào danh sách chờ (chưa tính điểm ngay, đợi 1h + getkey)
                if uid not in referrals[referrer_id]["invited_users"]:
                    referrals[referrer_id]["invited_users"].append({
                        "id": uid,
                        "time_joined": int(time.time()),
                        "status": "pending"
                    })
                    save_data(REFERRAL_FILE, referrals)
                    try:
                        bot.send_message(referrer_id, f"🔔 **Thông báo:** Người dùng `{uid}` vừa vào bot qua link của bạn. Điểm sẽ được cộng sau 1 giờ nếu họ hoạt động!", parse_mode="Markdown")
                    except: pass
    
    text = """```
╭─────────────⭓
│ 🤖 BOT TIKTOK SERVICE
├─────────────⭓
│ /getkey : Lấy mã sử dụng
| /ref : Giới Thiệu Nhận Vip
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

# --- LỆNH CHO NGƯỜI DÙNG ---
@bot.message_handler(commands=['gioithieu', 'ref'])
def handle_referral(message):
    uid = str(message.from_user.id)
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start={uid}"
    
    user_ref = referrals.get(uid, {"count": 0})
    count = user_ref.get("count", 0)
    req = ref_config["required"]
    
    txt = f"""🎁 **CHƯƠNG TRÌNH GIỚI THIỆU**
───────────────
🔗 Link của bạn: `{ref_link}`
👥 Đã giới thiệu: `{count}/{req}` người
🎁 Phần thưởng: `{ref_config['reward_days']} ngày VIP`

⚠️ **Điều kiện:** Người được mời phải /getkey và dùng bot ít nhất 1 giờ mới được tính điểm.
"""
    bot.reply_to(message, txt, parse_mode="Markdown")

# --- LỆNH CHO ADMIN THIẾT LẬP ---
@bot.message_handler(commands=['soluong'])
def set_ref_config(message):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 3: 
        return bot.reply_to(message, "❌ Sử dụng: `/soluong [số người] [số ngày vip]`")
    
    ref_config["required"] = int(args[1])
    ref_config["reward_days"] = int(args[2])
    save_data(REF_CONFIG_FILE, ref_config)
    bot.reply_to(message, f"✅ Đã cập nhật: Giới thiệu `{args[1]}` người nhận `{args[2]}` ngày VIP.")

# --- LỆNH ADMIN XEM THỐNG KÊ ---
@bot.message_handler(commands=['refstats'])
def admin_ref_stats(message):
    if not is_admin(message.from_user.id): return
    total_ref = sum(u.get('count', 0) for u in referrals.values())
    txt = f"📊 **THỐNG KÊ GIỚI THIỆU**\n- Tổng lượt ref thành công: `{total_ref}`\n- Số người đang tham gia: `{len(referrals)}`"
    bot.reply_to(message, txt, parse_mode="Markdown")

def referral_check_worker():
    while True:
        now = int(time.time())
        changed = False
        for referrer_id, data in referrals.items():
            for invitee in data.get("invited_users", []):
                if invitee["status"] == "pending":
                    # Điều kiện 1: Đã quá 1 giờ (3600s)
                    if (now - invitee["time_joined"]) >= 3600:
                        # Điều kiện 2: Đã từng Getkey (có trong allowed_users hoặc user_keys)
                        if invitee["id"] in allowed_users or invitee["id"] in user_keys:
                            invitee["status"] = "completed"
                            data["count"] += 1
                            changed = True
                            
                            # Thông báo cộng điểm thành công
                            try:
                                bot.send_message(referrer_id, f"✅ **+1 Point!** Người dùng `{invitee['id']}` đã đủ điều kiện. Hiện tại: `{data['count']}/{ref_config['required']}`")
                            except: pass
                            
                            # TỰ ĐỘNG TẶNG VIP KHI ĐỦ SỐ LƯỢNG
                            if data["count"] >= ref_config["required"]:
                                # Tránh tặng nhiều lần: kiểm tra số lượng đã nhận
                                already_claimed = data.get("claimed_count", 0)
                                if data["count"] // ref_config["required"] > already_claimed:
                                    days = ref_config["reward_days"]
                                    expiry = max(vip_users.get(referrer_id, now), now) + (days * 86400)
                                    vip_users[referrer_id] = expiry
                                    data["claimed_count"] = already_claimed + 1
                                    save_data(VIP_FILE, vip_users)
                                    try:
                                        bot.send_message(referrer_id, f"💎 **CHÚC MỪNG!** Bạn đã giới thiệu đủ {ref_config['required']} người và được tặng `{days} ngày VIP`!", parse_mode="Markdown")
                                    except: pass

        if changed:
            save_data(REFERRAL_FILE, referrals)
        time.sleep(60) # Kiểm tra mỗi phút

threading.Thread(target=referral_check_worker, daemon=True).start()

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
        allowed_users[uid] = int(time.time()) + 43200
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
    buff_amount = "250" if cmd_type == "view" else "10"
    
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
    
    if uid not in allowed_users or is_admin(uid) or int(time.time()) > allowed_users[uid]:
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

worker_thread = threading.Thread(target=auto_treo_worker)
worker_thread.daemon = True # Thread sẽ tự tắt khi bạn tắt script chính
worker_thread.start()

bot.infinity_polling()