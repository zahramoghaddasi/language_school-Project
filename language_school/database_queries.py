import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# تنظیمات اتصال به PostgreSQL
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5433')),
    'database': os.getenv('DB_NAME', 'postgres'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'Zahra123456')
}

def get_db_connection():
    """اتصال به PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f" خطا در اتصال به پایگاه داده: {e}")
        return None

# ==================== توابع داشبورد ====================
def get_dashboard_stats(conn):
    """دریافت آمار کلی داشبورد"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    stats = {}
    
    try:
        cursor.execute('SELECT COUNT(*) FROM professors')
        stats['professors'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM students')
        stats['students'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM courses')
        stats['courses'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM classes')
        stats['classes'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM registrations')
        stats['registrations'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(amount) FROM payments WHERE payment_status = %s', ('تکمیل',))
        total_payments = cursor.fetchone()[0]
        stats['payments'] = total_payments if total_payments else 0
        
    except Exception as e:
        print(f"خطا در دریافت آمار: {e}")
        stats = {'professors': 0, 'students': 0, 'courses': 0, 'classes': 0, 'registrations': 0, 'payments': 0}
    finally:
        cursor.close()
    
    return stats

def get_recent_registrations(conn, limit=5):
    """دریافت آخرین ثبت‌نام‌ها"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    try:
        cursor.execute('''
            SELECT s.first_name, s.last_name, s.phone_number, r.registration_date, 
                   c.course_title, p.first_name || ' ' || p.last_name as professor_name
            FROM registrations r
            JOIN students s ON r.membership_id = s.membership_id
            JOIN classes cl ON r.class_id = cl.class_id
            JOIN courses c ON cl.course_id = c.course_id
            JOIN professors p ON cl.professor_id = p.professor_id
            ORDER BY r.registration_date DESC LIMIT %s
        ''', (limit,))
        return cursor.fetchall()
    except Exception as e:
        print(f"خطا در دریافت آخرین ثبت‌نام‌ها: {e}")
        return []
    finally:
        cursor.close()

def get_upcoming_classes(conn, limit=5):
    """دریافت کلاس‌های آینده"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    try:
        cursor.execute('''
            SELECT c.class_id, cr.course_title, p.first_name || ' ' || p.last_name as professor_name,
                   c.start_date, c.class_time, c.class_days,
                   (SELECT COUNT(*) FROM registrations WHERE class_id = c.class_id) as registered_count,
                   c.capacity
            FROM classes c
            JOIN courses cr ON c.course_id = cr.course_id
            JOIN professors p ON c.professor_id = p.professor_id
            WHERE c.start_date >= CURRENT_DATE
            ORDER BY c.start_date LIMIT %s
        ''', (limit,))
        return cursor.fetchall()
    except Exception as e:
        print(f"خطا در دریافت کلاس‌های آینده: {e}")
        return []
    finally:
        cursor.close()

# ==================== توابع اساتید ====================
def get_professors_list(conn):
    """دریافت لیست اساتید"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT p.*, 
               (SELECT COUNT(*) FROM classes WHERE professor_id = p.professor_id) as class_count
        FROM professors p 
        ORDER BY p.professor_id
    ''')
    professors = cursor.fetchall()
    cursor.close()
    return professors

def check_professor_exists(conn, email, phone_number, exclude_id=None):
    """بررسی وجود استاد با ایمیل یا شماره تلفن"""
    cursor = conn.cursor()
    
    if exclude_id:
        cursor.execute('SELECT COUNT(*) FROM professors WHERE (email = %s OR phone_number = %s) AND professor_id != %s', 
                     (email, phone_number, exclude_id))
    else:
        cursor.execute('SELECT COUNT(*) FROM professors WHERE email = %s OR phone_number = %s', 
                     (email, phone_number))
    
    count = cursor.fetchone()[0]
    cursor.close()
    return count > 0

def get_professor_by_id(conn, professor_id):
    """دریافت اطلاعات استاد با ID"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT * FROM professors WHERE professor_id = %s', (professor_id,))
    professor = cursor.fetchone()
    cursor.close()
    return professor

def add_professor_db(conn, first_name, last_name, specialty, phone_number, email, salary, session_count):
    """افزودن استاد جدید"""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO professors 
        (first_name, last_name, specialty, phone_number, email, salary, session_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (first_name, last_name, specialty, phone_number, email, salary, session_count))
    conn.commit()
    cursor.close()

def update_professor_db(conn, professor_id, first_name, last_name, specialty, phone_number, email, salary, session_count):
    """به‌روزرسانی اطلاعات استاد"""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE professors 
        SET first_name = %s, last_name = %s, specialty = %s, 
            phone_number = %s, email = %s, salary = %s,
            session_count = %s
        WHERE professor_id = %s
    ''', (first_name, last_name, specialty, phone_number, email, salary, session_count, professor_id))
    conn.commit()
    cursor.close()

def delete_professor_db(conn, professor_id):
    """حذف استاد"""
    cursor = conn.cursor()
    
    # بررسی وجود کلاس‌های فعال
    cursor.execute('SELECT COUNT(*) FROM classes WHERE professor_id = %s', (professor_id,))
    class_count = cursor.fetchone()[0]
    
    if class_count > 0:
        cursor.close()
        return False, 'امکان حذف استاد وجود ندارد زیرا در کلاس‌هایی تدریس می‌کند.'
    
    # حذف زبان‌های مرتبط
    cursor.execute('DELETE FROM professor_languages WHERE professor_id = %s', (professor_id,))
    
    # حذف استاد
    cursor.execute('DELETE FROM professors WHERE professor_id = %s', (professor_id,))
    conn.commit()
    cursor.close()
    
    return True, 'استاد با موفقیت حذف شد.'

# ==================== توابع دانش‌آموزان ====================
def get_students_list(conn):
    """دریافت لیست دانش‌آموزان"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT s.*, 
               (SELECT COUNT(*) FROM registrations WHERE membership_id = s.membership_id) as registration_count
        FROM students s 
        ORDER BY s.membership_id
    ''')
    students = cursor.fetchall()
    cursor.close()
    return students

def add_student_db(conn, data):
    """افزودن دانش‌آموز جدید"""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO students (first_name, last_name, national_id, birth_date, 
                            phone_number, email, province, city, street, plaque)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (
        data['first_name'], data['last_name'], data['national_id'], data['birth_date'],
        data['phone_number'], data['email'], data['province'], data['city'],
        data['street'], data['plaque']
    ))
    conn.commit()
    cursor.close()

def update_student_db(conn, student_id, data):
    """به‌روزرسانی اطلاعات دانش‌آموز"""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE students 
        SET first_name = %s, last_name = %s, national_id = %s, birth_date = %s,
            phone_number = %s, email = %s, province = %s, city = %s, 
            street = %s, plaque = %s
        WHERE membership_id = %s
    ''', (
        data['first_name'], data['last_name'], data['national_id'], data['birth_date'],
        data['phone_number'], data['email'], data['province'], data['city'],
        data['street'], data['plaque'], student_id
    ))
    conn.commit()
    cursor.close()

def get_student_by_id(conn, student_id):
    """دریافت اطلاعات دانش‌آموز با ID"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT * FROM students WHERE membership_id = %s', (student_id,))
    student = cursor.fetchone()
    cursor.close()
    return student

def get_student_registrations(conn, student_id):
    """دریافت ثبت‌نام‌های دانش‌آموز"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT 
            r.registration_id,
            r.registration_date,
            c.course_title,
            c.course_level,
            cr.class_time,
            cr.class_days,
            cr.start_date,
            cr.end_date,
            p.first_name || ' ' || p.last_name AS professor_name,
            py.amount,
            py.payment_status,
            py.payment_method,
            py.payment_date
        FROM registrations r
        JOIN classes cr ON r.class_id = cr.class_id
        JOIN courses c ON cr.course_id = c.course_id
        JOIN professors p ON cr.professor_id = p.professor_id
        LEFT JOIN payments py ON r.payment_id = py.payment_id
        WHERE r.membership_id = %s
        ORDER BY r.registration_date DESC
    ''', (student_id,))
    registrations = cursor.fetchall()
    cursor.close()
    return registrations

def delete_student_db(conn, student_id):
    """حذف دانش‌آموز"""
    cursor = conn.cursor()
    
    # بررسی وجود ثبت‌نام‌های فعال
    cursor.execute('SELECT COUNT(*) FROM registrations WHERE membership_id = %s', (student_id,))
    reg_count = cursor.fetchone()[0]
    
    if reg_count > 0:
        cursor.close()
        return False, 'امکان حذف دانش‌آموز وجود ندارد زیرا در دوره‌هایی ثبت‌نام کرده است.'
    
    # حذف دانش‌آموز
    cursor.execute('DELETE FROM students WHERE membership_id = %s', (student_id,))
    conn.commit()
    cursor.close()
    
    return True, 'دانش‌آموز با موفقیت حذف شد.'

# ==================== توابع دوره‌ها ====================
def get_courses_list(conn):
    """دریافت لیست دوره‌ها"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT c.*, 
               (SELECT COUNT(*) FROM classes WHERE course_id = c.course_id) as class_count,
               (SELECT COUNT(*) FROM registrations r 
                JOIN classes cl ON r.class_id = cl.class_id 
                WHERE cl.course_id = c.course_id) as student_count
        FROM courses c 
        ORDER BY c.course_id
    ''')
    courses = cursor.fetchall()
    cursor.close()
    return courses

def add_course_db(conn, data):
    """افزودن دوره جدید"""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO courses (
            course_title, course_level, session_count, 
            course_status, course_capacity, level_id
        ) VALUES (%s, %s, %s, %s, %s, %s)
    ''', (
        data['course_title'], data['course_level'], data['session_count'],
        data['course_status'], data['course_capacity'], data.get('level_id')
    ))
    conn.commit()
    cursor.close()

def update_course_db(conn, course_id, data):
    """به‌روزرسانی دوره"""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE courses 
        SET course_title = %s, 
            course_level = %s, 
            session_count = %s,
            course_status = %s, 
            course_capacity = %s, 
            level_id = %s,
            description = %s, 
            prerequisites = %s, 
            tuition_fee = %s
        WHERE course_id = %s
    ''', (
        data['course_title'], data['course_level'], data['session_count'],
        data['course_status'], data['course_capacity'], data.get('level_id'),
        data.get('description', ''), data.get('prerequisites', ''), data.get('tuition_fee', 0),
        course_id
    ))
    conn.commit()
    cursor.close()

def get_course_by_id(conn, course_id):
    """دریافت اطلاعات دوره با ID"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT * FROM courses WHERE course_id = %s', (course_id,))
    course = cursor.fetchone()
    cursor.close()
    return course

def delete_course_db(conn, course_id):
    """حذف دوره"""
    cursor = conn.cursor()
    
    # بررسی وجود کلاس‌های فعال
    cursor.execute('SELECT COUNT(*) FROM classes WHERE course_id = %s', (course_id,))
    class_count = cursor.fetchone()[0]
    
    if class_count > 0:
        cursor.close()
        return False, 'امکان حذف دوره وجود ندارد زیرا کلاس‌های فعال دارد.'
    
    cursor.execute('DELETE FROM courses WHERE course_id = %s', (course_id,))
    conn.commit()
    cursor.close()
    
    return True, 'دوره با موفقیت حذف شد.'

# ==================== توابع کلاس‌ها ====================
def get_classes_list(conn):
    """دریافت لیست کلاس‌ها"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT cl.*, 
               c.course_title, c.course_level,
               p.first_name || ' ' || p.last_name as professor_name,
               (SELECT COUNT(*) FROM registrations WHERE class_id = cl.class_id) as student_count
        FROM classes cl
        JOIN courses c ON cl.course_id = c.course_id
        JOIN professors p ON cl.professor_id = p.professor_id
        ORDER BY cl.start_date DESC
    ''')
    classes = cursor.fetchall()
    cursor.close()
    return classes

def add_class_db(conn, data):
    """افزودن کلاس جدید"""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO classes (course_id, professor_id, capacity, 
                           start_date, end_date, class_time, class_days)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (
        data['course_id'], data['professor_id'], data['capacity'],
        data['start_date'], data['end_date'], data['class_time'], data['class_days']
    ))
    conn.commit()
    cursor.close()

def update_class_db(conn, class_id, data):
    """به‌روزرسانی کلاس"""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE classes 
        SET course_id = %s, professor_id = %s, capacity = %s,
            start_date = %s, end_date = %s, class_time = %s,
            class_days = %s
        WHERE class_id = %s
    ''', (
        data['course_id'], data['professor_id'], data['capacity'],
        data['start_date'], data['end_date'], data['class_time'],
        data['class_days'], class_id
    ))
    conn.commit()
    cursor.close()

def get_class_by_id(conn, class_id):
    """دریافت اطلاعات کلاس با ID"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT * FROM classes WHERE class_id = %s', (class_id,))
    class_info = cursor.fetchone()
    cursor.close()
    return class_info

def delete_class_db(conn, class_id):
    """حذف کلاس"""
    cursor = conn.cursor()
    
    # بررسی وجود ثبت‌نام
    cursor.execute('SELECT COUNT(*) FROM registrations WHERE class_id = %s', (class_id,))
    reg_count = cursor.fetchone()[0]
    
    if reg_count > 0:
        cursor.close()
        return False, 'امکان حذف کلاس وجود ندارد زیرا دانش‌آموزانی در آن ثبت‌نام کرده‌اند.'
    
    cursor.execute('DELETE FROM classes WHERE class_id = %s', (class_id,))
    conn.commit()
    cursor.close()
    
    return True, 'کلاس با موفقیت حذف شد.'

# ==================== توابع ثبت‌نام‌ها ====================
def get_registrations_list(conn, filters=None):
    """دریافت لیست ثبت‌نام‌ها با فیلتر"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    query = '''
        SELECT r.*, 
               s.first_name || ' ' || s.last_name as student_name,
               s.phone_number as student_phone,
               c.course_title, c.course_level,
               cl.class_time, cl.class_days, cl.start_date,
               p.first_name || ' ' || p.last_name as professor_name,
               py.amount, py.payment_status, py.payment_method, py.payment_date
        FROM registrations r
        JOIN students s ON r.membership_id = s.membership_id
        JOIN classes cl ON r.class_id = cl.class_id
        JOIN courses c ON cl.course_id = c.course_id
        JOIN professors p ON cl.professor_id = p.professor_id
        LEFT JOIN payments py ON r.payment_id = py.payment_id
        WHERE 1=1
    '''
    params = []
    
    if filters:
        if filters.get('class_id'):
            query += ' AND r.class_id = %s'
            params.append(filters['class_id'])
        
        if filters.get('student_id'):
            query += ' AND r.membership_id = %s'
            params.append(filters['student_id'])
        
        if filters.get('payment_status'):
            query += ' AND py.payment_status = %s'
            params.append(filters['payment_status'])
    
    query += ' ORDER BY r.registration_date DESC'
    
    cursor.execute(query, params)
    registrations = cursor.fetchall()
    cursor.close()
    return registrations

def get_classes_for_registration(conn):
    """دریافت لیست کلاس‌ها برای ثبت‌نام"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT cl.class_id, c.course_title || ' - ' || cl.class_time || ' (' || cl.class_days || ')' as class_name 
        FROM classes cl
        JOIN courses c ON cl.course_id = c.course_id
        ORDER BY cl.start_date
    ''')
    classes = cursor.fetchall()
    cursor.close()
    return classes

def add_registration_db(conn, membership_id, class_id):
    """افزودن ثبت‌نام جدید"""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO registrations (membership_id, class_id, registration_date)
        VALUES (%s, %s, CURRENT_DATE)
        RETURNING registration_id
    ''', (membership_id, class_id))
    
    registration_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    return registration_id

def check_registration_duplicate(conn, membership_id, class_id, exclude_id=None):
    """بررسی تکراری نبودن ثبت‌نام"""
    cursor = conn.cursor()
    
    if exclude_id:
        cursor.execute('SELECT COUNT(*) FROM registrations WHERE membership_id = %s AND class_id = %s AND registration_id != %s', 
                     (membership_id, class_id, exclude_id))
    else:
        cursor.execute('SELECT COUNT(*) FROM registrations WHERE membership_id = %s AND class_id = %s', 
                     (membership_id, class_id))
    
    count = cursor.fetchone()[0]
    cursor.close()
    return count > 0

def get_class_capacity(conn, class_id):
    """بررسی ظرفیت کلاس"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT capacity, 
               (SELECT COUNT(*) FROM registrations WHERE class_id = %s) as registered
        FROM classes WHERE class_id = %s
    ''', (class_id, class_id))
    
    class_info = cursor.fetchone()
    cursor.close()
    return class_info

def update_registration_db(conn, registration_id, membership_id, class_id):
    """به‌روزرسانی ثبت‌نام"""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE registrations 
        SET membership_id = %s, class_id = %s
        WHERE registration_id = %s
    ''', (membership_id, class_id, registration_id))
    conn.commit()
    cursor.close()

def get_registration_by_id(conn, registration_id):
    """دریافت اطلاعات ثبت‌نام با ID"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT r.*, s.first_name || ' ' || s.last_name as student_name,
               s.phone_number as student_phone,
               p.amount, p.payment_method, p.payment_status
        FROM registrations r
        JOIN students s ON r.membership_id = s.membership_id
        LEFT JOIN payments p ON r.payment_id = p.payment_id
        WHERE r.registration_id = %s
    ''', (registration_id,))
    registration = cursor.fetchone()
    cursor.close()
    return registration

def delete_registration_db(conn, registration_id):
    """حذف ثبت‌نام"""
    cursor = conn.cursor()
    
    # پیدا کردن payment_id مرتبط
    cursor.execute('SELECT payment_id FROM registrations WHERE registration_id = %s', (registration_id,))
    result = cursor.fetchone()
    payment_id = result[0] if result else None
    
    # حذف ثبت‌نام
    cursor.execute('DELETE FROM registrations WHERE registration_id = %s', (registration_id,))
    
    # حذف پرداخت مرتبط
    if payment_id:
        cursor.execute('DELETE FROM payments WHERE payment_id = %s', (payment_id,))
    
    conn.commit()
    cursor.close()

# ==================== توابع پرداخت‌ها ====================
def get_payments_list(conn, filters=None):
    """دریافت لیست پرداخت‌ها"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    query = '''
        SELECT p.*, 
               s.first_name || ' ' || s.last_name as student_name,
               c.course_title, r.registration_date
        FROM payments p
        LEFT JOIN registrations r ON p.payment_id = r.payment_id
        LEFT JOIN students s ON r.membership_id = s.membership_id
        LEFT JOIN classes cl ON r.class_id = cl.class_id
        LEFT JOIN courses c ON cl.course_id = c.course_id
        WHERE 1=1
    '''
    params = []
    
    if filters:
        if filters.get('payment_status'):
            query += ' AND p.payment_status = %s'
            params.append(filters['payment_status'])
        
        if filters.get('start_date'):
            query += ' AND p.payment_date >= %s'
            params.append(filters['start_date'])
        
        if filters.get('end_date'):
            query += ' AND p.payment_date <= %s'
            params.append(filters['end_date'])
    
    query += ' ORDER BY p.payment_date DESC'
    
    cursor.execute(query, params)
    payments = cursor.fetchall()
    cursor.close()
    return payments

def get_payment_stats(conn):
    """دریافت آمار پرداخت‌ها"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    cursor.execute('SELECT SUM(amount) FROM payments WHERE payment_status = %s', ('تکمیل',))
    total_completed = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(amount) FROM payments WHERE payment_status = %s', ('انتظار',))
    total_pending = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM payments')
    payment_count = cursor.fetchone()[0]
    
    cursor.close()
    
    return {
        'total_completed': total_completed,
        'total_pending': total_pending,
        'payment_count': payment_count
    }

def update_payment_db(conn, payment_id, amount, payment_method, payment_status):
    """به‌روزرسانی پرداخت"""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE payments 
        SET amount = %s, payment_method = %s, payment_status = %s
        WHERE payment_id = %s
    ''', (amount, payment_method, payment_status, payment_id))
    conn.commit()
    cursor.close()

def get_payment_by_id(conn, payment_id):
    """دریافت اطلاعات پرداخت با ID"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT * FROM payments WHERE payment_id = %s', (payment_id,))
    payment = cursor.fetchone()
    cursor.close()
    return payment
# ==================== توابع جستجو ====================
def search_professors(conn, query, limit=50):
    """جستجوی اساتید"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT * FROM professors 
        WHERE first_name ILIKE %s OR last_name ILIKE %s 
           OR specialty ILIKE %s OR email ILIKE %s
        LIMIT %s
    ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', limit))
    results = cursor.fetchall()
    cursor.close()
    return results

def search_students(conn, query, limit=50):
    """جستجوی دانش‌آموزان"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT * FROM students 
        WHERE first_name ILIKE %s OR last_name ILIKE %s 
           OR national_id ILIKE %s OR phone_number ILIKE %s
           OR email ILIKE %s OR city ILIKE %s
        LIMIT %s
    ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', limit))
    results = cursor.fetchall()
    cursor.close()
    return results

def search_courses(conn, query, limit=50):
    """جستجوی دوره‌ها"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT * FROM courses 
        WHERE course_title ILIKE %s OR course_level ILIKE %s
           OR description ILIKE %s
        LIMIT %s
    ''', (f'%{query}%', f'%{query}%', f'%{query}%', limit))
    results = cursor.fetchall()
    cursor.close()
    return results

def search_classes(conn, query, limit=50):
    """جستجوی کلاس‌ها"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT cl.*, c.course_title, p.first_name || ' ' || p.last_name as professor_name
        FROM classes cl
        JOIN courses c ON cl.course_id = c.course_id
        JOIN professors p ON cl.professor_id = p.professor_id
        WHERE c.course_title ILIKE %s OR cl.classroom ILIKE %s
           OR cl.class_time ILIKE %s
        LIMIT %s
    ''', (f'%{query}%', f'%{query}%', f'%{query}%', limit))
    results = cursor.fetchall()
    cursor.close()
    return results

# ==================== توابع API ====================
def api_search_students_db(conn, query, limit=10):
    """جستجوی سریع دانش‌آموزان برای API"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT membership_id, first_name || ' ' || last_name as name, phone_number
        FROM students 
        WHERE first_name ILIKE %s OR last_name ILIKE %s OR phone_number ILIKE %s
        LIMIT %s
    ''', (f'%{query}%', f'%{query}%', f'%{query}%', limit))
    
    results = cursor.fetchall()
    cursor.close()
    return results

def get_class_availability_db(conn, class_id):
    """بررسی ظرفیت کلاس برای API"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT capacity, 
               (SELECT COUNT(*) FROM registrations WHERE class_id = %s) as registered
        FROM classes WHERE class_id = %s
    ''', (class_id, class_id))
    
    result = cursor.fetchone()
    cursor.close()
    return result

def get_api_dashboard_stats(conn):
    """دریافت آمار لحظه‌ای برای API"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    stats = {}
    
    cursor.execute('SELECT COUNT(*) FROM professors')
    stats['professors'] = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM students')
    stats['students'] = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM courses')
    stats['courses'] = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM classes WHERE start_date >= CURRENT_DATE')
    stats['upcoming_classes'] = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM registrations WHERE registration_date >= CURRENT_DATE - INTERVAL \'7 days\'')
    stats['recent_registrations'] = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(amount) FROM payments WHERE payment_date >= CURRENT_DATE - INTERVAL \'30 days\'')
    total = cursor.fetchone()[0]
    stats['revenue_30days'] = total if total else 0
    
    cursor.close()
    return stats

# ==================== توابع کمکی ====================
def get_courses_for_dropdown(conn):
    """دریافت لیست دوره‌ها برای dropdown"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT * FROM courses WHERE course_status = %s ORDER BY course_title', ('فعال',))
    courses = cursor.fetchall()
    cursor.close()
    return courses

def get_professors_for_dropdown(conn):
    """دریافت لیست اساتید برای dropdown"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT * FROM professors ORDER BY first_name, last_name')
    professors = cursor.fetchall()
    cursor.close()
    return professors

def get_students_for_dropdown(conn):
    """دریافت لیست دانش‌آموزان برای dropdown"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT membership_id, first_name || \' \' || last_name as full_name FROM students ORDER BY last_name')
    students = cursor.fetchall()
    cursor.close()
    return students

def get_levels_for_dropdown(conn):
    """دریافت لیست سطوح برای dropdown"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT * FROM levels ORDER BY level_name')
    levels = cursor.fetchall()
    cursor.close()
    return levels

def get_active_classes_for_dropdown(conn):
    """دریافت لیست کلاس‌های فعال برای dropdown"""
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('''
        SELECT cl.class_id, 
               c.course_title || ' - ' || cl.class_time || ' (' || cl.class_days || ')' as class_name,
               cl.capacity, 
               (SELECT COUNT(*) FROM registrations WHERE class_id = cl.class_id) as registered,
               c.course_title,
               cl.class_time,
               cl.class_days,
               p.first_name || ' ' || p.last_name as professor_name
        FROM classes cl
        JOIN courses c ON cl.course_id = c.course_id
        JOIN professors p ON cl.professor_id = p.professor_id
        WHERE cl.start_date >= CURRENT_DATE
        ORDER BY cl.start_date
    ''')
    classes = cursor.fetchall()
    cursor.close()
    return classes