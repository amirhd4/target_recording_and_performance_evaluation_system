# ------------------------------------------------------------
# تنظیمات اسکریپت
# ------------------------------------------------------------

# مسیر پوشه اصلی که فایل های شما در آن قرار دارند (مثلاً پشتیبان‌های روزانه یا هفتگی)
SOURCE_DIR="/home/amirz/fccc_targets/db_backup" # این مسیر را با مسیر واقعی خود جایگزین کنید

# مسیر پوشه پشتیبان ماهانه (این پوشه در داخل SOURCE_DIR ایجاد خواهد شد)
DEST_DIR="$SOURCE_DIR/monthly_backup"

# مسیر فایل لاگ برای ثبت وقایع (می‌توانید آن را تغییر دهید)
LOG_FILE="/var/log/monthly_file_backup.log" # مطمئن شوید کاربری که cronjob را اجرا می‌کند، دسترسی نوشتن به این فایل را داشته باشد.
                                            # شاید بهتر باشد مسیر آن را به پوشه‌ای در home کاربر منتقل کنید، مثلاً: "$HOME/logs/monthly_file_backup.log"

# ------------------------------------------------------------
# توابع کمکی
# ------------------------------------------------------------

# تابع برای ثبت پیام در لاگ و نمایش در خروجی استاندارد
log() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - $1" | tee -a "$LOG_FILE"
}

# ------------------------------------------------------------
# شروع اسکریپت
# ------------------------------------------------------------

log "--------------------------------------------------"
log "Monthly file backup script started."
log "Source directory: $SOURCE_DIR"
log "Destination directory: $DEST_DIR"

# بررسی وجود مسیر منبع
if [ -z "$SOURCE_DIR" ]; then
    log "Error: SOURCE_DIR is not set. Please configure the script."
    exit 1
fi

if [ ! -d "$SOURCE_DIR" ]; then
    log "Error: Source directory '$SOURCE_DIR' not found or is not a directory."
    exit 1
fi

# ایجاد پوشه مقصد اگر وجود ندارد
if ! mkdir -p "$DEST_DIR"; then
    log "Error: Failed to create destination directory '$DEST_DIR'."
    exit 1
fi
log "Destination directory checked/created: '$DEST_DIR'."

# ------------------------------------------------------------
# پیدا کردن آخرین فایل در پوشه منبع بر اساس تاریخ ویرایش
# ------------------------------------------------------------

# استفاده از find برای پیدا کردن تمام فایل ها (غیر از پوشه‌ها) در مسیر منبع (فقط در سطح اول)
# -printf '%T@ %p\n' : چاپ زمان ویرایش (epoch time) و سپس مسیر فایل، جدا شده با فاصله و به همراه newline
# 2>/dev/null : نادیده گرفتن خطاهای احتمالی find (مثلاً در صورت عدم دسترسی)
# sort -n : مرتب‌سازی بر اساس زمان ویرایش (عددی)
# tail -n 1 : انتخاب آخرین خط (که مربوط به جدیدترین فایل است)
# awk '{ print $2 }' : استخراج قسمت دوم هر خط (که مسیر فایل است) - این روش برای نام فایل‌هایی که حاوی فاصله نیستند مناسب است.
# اگر نام فایل‌های شما ممکن است حاوی فاصله باشند، روش دقیق‌تری با استفاده از find -print0 و xargs -0 یا خواندن خط به خط در bash نیاز است که پیچیده‌تر است.
# برای سادگی، از روش awk استفاده می‌شود با فرض عدم وجود فاصله در نام فایل‌ها.

LATEST_FILE=$(find "$SOURCE_DIR" -maxdepth 1 -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -n 1 | awk '{ print $2 }')

# ------------------------------------------------------------
# اجرای عملیات پشتیبان
# ------------------------------------------------------------

if [ -z "$LATEST_FILE" ]; then
    log "No files found in '$SOURCE_DIR' to backup this month."
    log "Script finished."
    exit 0 # خروج موفقیت‌آمیز، چون فایل نبود اما خطا هم رخ نداده است.
fi

log "Found the latest file: '$LATEST_FILE'"

# گرفتن نام اصلی فایل
BASENAME=$(basename "$LATEST_FILE")

# مسیر کامل فایل در مقصد
DEST_FILE="$DEST_DIR/$BASENAME"

# بررسی اینکه آیا فایل مقصد از قبل وجود دارد (اختیاری)
# if [ -f "$DEST_FILE" ]; then
#     log "Warning: File '$BASENAME' already exists in '$DEST_DIR'. Overwriting."
#     # اگر می‌خواهید در صورت وجود فایل کپی را انجام ندهید، خط زیر را فعال کنید:
#     # log "File '$BASENAME' already exists. Skipping backup."
#     # log "Script finished."
#     # exit 0
# fi

# کپی کردن آخرین فایل به پوشه پشتیبان ماهانه
log "Copying '$LATEST_FILE' to '$DEST_DIR'..."
# دستور cp -v : کپی کردن با نمایش اطلاعات (verbose)
if cp -v "$LATEST_FILE" "$DEST_DIR/"; then # کپی کردن فایل در داخل پوشه مقصد
    log "Backup successful: '$DEST_DIR/$BASENAME'"
    log "Script finished."
    exit 0 # خروج موفقیت‌آمیز
else
    log "Error: Failed to copy '$LATEST_FILE' to '$DEST_DIR'."
    log "Script finished with errors."
    exit 1 # خروج با کد خطا
fi
