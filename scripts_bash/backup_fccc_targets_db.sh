DB_NAME="fccc_targets"
DB_USER="postgres"
DB_HOST="localhost"
DB_PORT="5432"

export PGPASSWORD=""

BACKUP_DIR="/home/amirz/fccc_targets/db_backup" # مسیری که می خواهید فایل های پشتیبان در آن ذخیره شوند
# مثال: /var/backups/postgres/your_db_name

# اطمینان از وجود دایرکتوری پشتیبان، اگر وجود ندارد آن را ایجاد کن
mkdir -p "$BACKUP_DIR"

# ایجاد نام فایل پشتیبان با برچسب زمانی
# فرمت: YYYYMMDD_HHMMSS (سال ماه روز_ساعت دقیقه ثانیه)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_backup_$TIMESTAMP.sql"

# فرمت خروجی: .sql برای پشتیبان متنی (قابل خواندن)
# می توانید از فرمت سفارشی .dump هم استفاده کنید که برای restore سریعتر است
# BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_backup_$TIMESTAMP.dump"


# ------------------------------------------------------------
# اجرای دستور pg_dump
# ------------------------------------------------------------
echo "Starting database backup for $DB_NAME at $TIMESTAMP..."

# دستور pg_dump
# -h: هاست، -p: پورت، -U: کاربر
# خروجی به فایل BACKUP_FILE هدایت می شود (>)
pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME > "$BACKUP_FILE"

# بررسی موفقیت آمیز بودن دستور pg_dump (بر اساس کد خروجی دستور)
# $? حاوی کد خروجی آخرین دستور اجرا شده است (0 معمولا به معنی موفقیت است)
if [ $? -eq 0 ]; then
    echo "Database backup successful: $BACKUP_FILE"
    # می توانید پیام موفقیت را به یک فایل لاگ هم بنویسید
    echo "Database backup successful: $BACKUP_FILE" >> /var/log/postgres_backup.log

    # --------------------------------------------------------
    # (اختیاری) پاک کردن پشتیبان های قدیمی
    # --------------------------------------------------------
    # پیدا کردن فایل های پشتیبان در دایرکتوری BACKUP_DIR
    echo "Cleaning up old backups..."
    find "$BACKUP_DIR" -type f -mtime +7 -delete
    echo "Cleanup complete."

else
    echo "Error: Database backup failed!"
    # می توانید پیام خطا را به یک فایل لاگ هم بنویسید
    echo "Error: Database backup failed for $DB_NAME at $TIMESTAMP" >> /var/log/postgres_backup.log
    exit 1 # خروج با کد خطا برای نشان دادن عدم موفقیت اسکریپت
fi


unset PGPASSWORD # کامنت را بردارید اگر از export PGPASSWORD استفاده کردید