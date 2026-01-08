from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from database_queries import *
import os
from datetime import date
from dotenv import load_dotenv
from auth import login_required, check_credentials, logout_user

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# ==================== صفحه ورود ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if 'logged_in' in session:
            return redirect(url_for('index'))
        
        error = None
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
            if check_credentials(username, password):
                session['logged_in'] = True
                session['username'] = username
                return redirect(url_for('index'))
            else:
                error = 'نام کاربری یا رمز عبور نادرست است'
        
        return render_template('auth/login.html', error=error)
    
    except:
        return render_template('auth/login.html', error='خطا در ورود به سیستم')

# ==================== خروج از سیستم ====================
@app.route('/logout')
@login_required
def logout():
    try:
        logout_user()
        return redirect(url_for('login'))
    except:
        return redirect(url_for('login'))

# ==================== صفحه اصلی ====================
@app.route('/')
@login_required
def index():
    try:
        conn = get_db_connection()
        if not conn:
            return render_template('index.html', stats={}, recent_registrations=[], upcoming_classes=[])
        
        try:
            stats = get_dashboard_stats(conn)
            recent_registrations = get_recent_registrations(conn, 5)
            upcoming_classes = get_upcoming_classes(conn, 5)
        except:
            stats = {'professors': 0, 'students': 0, 'courses': 0, 'classes': 0, 'registrations': 0, 'payments': 0}
            recent_registrations = []
            upcoming_classes = []
        finally:
            conn.close()
        
        return render_template('index.html', stats=stats, 
                             recent_registrations=recent_registrations, 
                             upcoming_classes=upcoming_classes,
                             date=date)
    
    except:
        return render_template('index.html', stats={}, recent_registrations=[], upcoming_classes=[])

# ==================== مدیریت اساتید ====================
@app.route('/professors')
@login_required  
def list_professors():
    try:
        conn = get_db_connection()
        if not conn:
            return render_template('professors/list.html', professors=[])
        
        professors = get_professors_list(conn)
        conn.close()
        
        return render_template('professors/list.html', professors=professors)
    
    except Exception as e:
        print(f"خطا در دریافت لیست اساتید: {e}")
        return render_template('professors/list.html', professors=[])

@app.route('/professors/add', methods=['GET', 'POST'])
@login_required  
def add_professor():
    try:
        if request.method == 'GET':
            return render_template('professors/add.html')
        
        # POST method
        conn = get_db_connection()
        if not conn:
            print("خطا: اتصال به دیتابیس برقرار نشد")
            return redirect('/professors/add')
        
        try:
            # دریافت داده‌های فرم
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            specialty = request.form.get('specialty', '').strip()
            phone_number = request.form.get('phone_number', '').strip()
            email = request.form.get('email', '').strip()
            
            print(f"داده‌های دریافت شده: {first_name}, {last_name}, {specialty}, {phone_number}, {email}")
            
            # اعتبارسنجی فیلدهای ضروری
            if not all([first_name, last_name, specialty, phone_number, email]):
                print("خطا: برخی فیلدهای ضروری خالی هستند")
                return redirect('/professors/add')
            
            # تبدیل مقادیر عددی
            try:
                salary = float(request.form.get('salary', '0').strip())
                session_count = int(request.form.get('session_count', '0').strip())
            except ValueError as ve:
                print(f"خطا در تبدیل مقادیر عددی: {ve}")
                return redirect('/professors/add')
            
            # بررسی تکراری نبودن استاد
            if check_professor_exists(conn, email, phone_number):
                print("خطا: استاد با این ایمیل یا شماره تماس قبلاً ثبت شده است")
                return redirect('/professors/add')
            
            # اضافه کردن استاد به دیتابیس
            add_professor_db(conn, first_name, last_name, specialty, phone_number, email, salary, session_count)
            print("استاد با موفقیت اضافه شد")
            
            conn.commit()  # اضافه کردن commit برای ذخیره تغییرات
            return redirect('/professors')
            
        except Exception as e:
            conn.rollback()
            print(f"خطا در اضافه کردن استاد: {e}")
            return redirect('/professors/add')
        finally:
            conn.close()
    
    except Exception as e:
        print(f"خطای کلی در مسیر اضافه کردن استاد: {e}")
        return redirect('/professors')

@app.route('/professors/edit/<int:id>', methods=['GET', 'POST'])
@login_required  
def edit_professor(id):
    try:
        if request.method == 'GET':
            conn = get_db_connection()
            if not conn:
                return redirect('/professors')
            
            try:
                professor = get_professor_by_id(conn, id)
                conn.close()
                
                if not professor:
                    print("استاد مورد نظر یافت نشد")
                    return redirect('/professors')
                
                return render_template('professors/edit.html', professor=professor)
            except Exception as e:
                conn.close()
                print(f"خطا در دریافت اطلاعات استاد: {e}")
                return redirect('/professors')
        
        # POST method
        conn = get_db_connection()
        if not conn:
            return redirect(f'/professors/edit/{id}')
        
        try:
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            specialty = request.form.get('specialty', '').strip()
            phone_number = request.form.get('phone_number', '').strip()
            email = request.form.get('email', '').strip()
            
            if not all([first_name, last_name, specialty, phone_number, email]):
                return redirect(f'/professors/edit/{id}')
            
            try:
                salary = float(request.form.get('salary', '0').strip())
                session_count = int(request.form.get('session_count', '0').strip())
            except ValueError:
                return redirect(f'/professors/edit/{id}')
            
            if check_professor_exists(conn, email, phone_number, exclude_id=id):
                return redirect(f'/professors/edit/{id}')
            
            update_professor_db(conn, id, first_name, last_name, specialty, phone_number, email, salary, session_count)
            conn.commit()
            return redirect('/professors')
            
        except Exception as e:
            conn.rollback()
            print(f"خطا در ویرایش استاد: {e}")
            return redirect(f'/professors/edit/{id}')
        finally:
            conn.close()
    
    except Exception as e:
        print(f"خطای کلی در ویرایش استاد: {e}")
        return redirect('/professors')

@app.route('/professors/delete/<int:id>')
@login_required  
def delete_professor(id):
    try:
        conn = get_db_connection()
        if not conn:
            return redirect('/professors')
        
        try:
            success, message = delete_professor_db(conn, id)
            if success:
                conn.commit()
                print(f"استاد با شناسه {id} حذف شد")
            else:
                print(f"خطا در حذف استاد: {message}")
        except Exception as e:
            print(f"خطا در حذف استاد: {e}")
        finally:
            conn.close()
        
        return redirect('/professors')
    
    except Exception as e:
        print(f"خطای کلی در حذف استاد: {e}")
        return redirect('/professors')

# ==================== مدیریت دانش‌آموزان ====================
@app.route('/students')
@login_required
def list_students():
    try:
        conn = get_db_connection()
        if not conn:
            return redirect('/')
        
        students = get_students_list(conn)
        conn.close()
        
        return render_template('students/list.html', students=students)
    
    except:
        return render_template('students/list.html', students=[])

@app.route('/students/add', methods=['GET', 'POST'])
@login_required
def add_student():
    try:
        if request.method == 'GET':
            return render_template('students/add.html')
        
        conn = get_db_connection()
        if not conn:
            return redirect('/students/add')
        
        try:
            data = {
                'first_name': request.form['first_name'].strip(),
                'last_name': request.form['last_name'].strip(),
                'national_id': request.form['national_id'].strip(),
                'birth_date': request.form['birth_date'].strip(),
                'phone_number': request.form['phone_number'].strip(),
                'email': request.form['email'].strip(),
                'province': request.form['province'].strip(),
                'city': request.form['city'].strip(),
                'street': request.form['street'].strip(),
                'plaque': request.form['plaque'].strip()
            }
            
            if not data['first_name'] or not data['last_name']:
                return redirect('/students/add')
            
            if not data['national_id'].isdigit() or len(data['national_id']) != 10:
                return redirect('/students/add')
            
            add_student_db(conn, data)
            conn.commit()
            return redirect('/students')
            
        except:
            conn.rollback()
            return redirect('/students/add')
        finally:
            conn.close()
    
    except:
        return redirect('/students')

@app.route('/students/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_student(id):
    try:
        if request.method == 'GET':
            conn = get_db_connection()
            if not conn:
                return redirect('/students')
            
            try:
                student = get_student_by_id(conn, id)
                
                if not student:
                    conn.close()
                    return redirect('/students')
                
                if student['birth_date']:
                    student['birth_date'] = student['birth_date'].strftime('%Y-%m-%d')
                
                conn.close()
                return render_template('students/edit.html', student=student)
                
            except:
                conn.close()
                return redirect('/students')
        
        conn = get_db_connection()
        if not conn:
            return redirect(f'/students/edit/{id}')
        
        try:
            data = {
                'first_name': request.form['first_name'].strip(),
                'last_name': request.form['last_name'].strip(),
                'national_id': request.form['national_id'].strip(),
                'birth_date': request.form['birth_date'].strip(),
                'phone_number': request.form['phone_number'].strip(),
                'email': request.form['email'].strip(),
                'province': request.form['province'].strip(),
                'city': request.form['city'].strip(),
                'street': request.form['street'].strip(),
                'plaque': request.form['plaque'].strip()
            }
            
            if not data['first_name'] or not data['last_name']:
                return redirect(f'/students/edit/{id}')
            
            if not data['national_id'].isdigit() or len(data['national_id']) != 10:
                return redirect(f'/students/edit/{id}')
            
            update_student_db(conn, id, data)
            conn.commit()
            return redirect('/students')
            
        except:
            conn.rollback()
            return redirect(f'/students/edit/{id}')
        finally:
            conn.close()
    
    except:
        return redirect('/students')

@app.route('/students/view/<int:id>')
@login_required
def view_student(id):
    try:
        conn = get_db_connection()
        if not conn:
            return redirect('/students')
        
        try:
            student = get_student_by_id(conn, id)
            
            if not student:
                conn.close()
                return redirect('/students')
            
            registrations = get_student_registrations(conn, id)
            
            stats = {
                'total_courses': len(registrations),
                'completed_courses': len([r for r in registrations if r.get('payment_status') == 'تکمیل']),
                'pending_courses': len([r for r in registrations if r.get('payment_status') == 'انتظار']),
                'total_payments': sum([r.get('amount', 0) or 0 for r in registrations])
            }
            
            conn.close()
            return render_template('students/view.html', 
                                 student=student, 
                                 registrations=registrations,
                                 stats=stats)
            
        except:
            conn.close()
            return redirect('/students')
    
    except:
        return redirect('/students')

@app.route('/students/delete/<int:id>')
@login_required
def delete_student(id):
    try:
        conn = get_db_connection()
        if not conn:
            return redirect('/students')
        
        try:
            success, message = delete_student_db(conn, id)
            if success:
                conn.commit()
        except:
            pass
        finally:
            conn.close()
        
        return redirect('/students')
    
    except:
        return redirect('/students')

# ==================== مدیریت دوره‌ها ====================
@app.route('/courses')
@login_required
def list_courses():
    try:
        conn = get_db_connection()
        if not conn:
            return redirect('/')
        
        courses = get_courses_list(conn)
        conn.close()
        
        return render_template('courses/list.html', courses=courses)
    
    except:
        return render_template('courses/list.html', courses=[])

@app.route('/courses/add', methods=['GET', 'POST'])
@login_required
def add_course():
    try:
        if request.method == 'GET':
            try:
                conn = get_db_connection()
                levels = get_levels_for_dropdown(conn)
                conn.close()
            except:
                levels = []
            
            return render_template('courses/add.html', levels=levels)
        
        conn = get_db_connection()
        if not conn:
            return redirect('/courses/add')
        
        try:
            required_fields = ['course_title', 'course_level', 'session_count', 'course_capacity']
            
            for field in required_fields:
                if not request.form.get(field):
                    return redirect('/courses/add')
            
            try:
                session_count = int(request.form['session_count'])
                course_capacity = int(request.form['course_capacity'])
            except ValueError:
                return redirect('/courses/add')
            
            data = {
                'course_title': request.form['course_title'].strip(),
                'course_level': request.form['course_level'].strip(),
                'session_count': session_count,
                'course_capacity': course_capacity,
                'course_status': request.form.get('course_status', 'فعال').strip(),
                'level_id': request.form.get('level_id')
            }
            
            if data['level_id'] and data['level_id'].strip():
                try:
                    data['level_id'] = int(data['level_id'])
                except ValueError:
                    data['level_id'] = None
            else:
                data['level_id'] = None
            
            add_course_db(conn, data)
            conn.commit()
            return redirect('/courses')
            
        except:
            conn.rollback()
            return redirect('/courses/add')
        finally:
            conn.close()
    
    except:
        return redirect('/courses')

@app.route('/courses/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_course(id):
    try:
        if request.method == 'GET':
            conn = get_db_connection()
            if not conn:
                return redirect('/courses')
            
            try:
                course = get_course_by_id(conn, id)
                
                if not course:
                    conn.close()
                    return redirect('/courses')
                
                levels = get_levels_for_dropdown(conn)
                conn.close()
                return render_template('courses/edit.html', course=course, levels=levels)
                
            except:
                conn.close()
                return redirect('/courses')
        
        conn = get_db_connection()
        if not conn:
            return redirect(f'/courses/edit/{id}')
        
        try:
            course_title = request.form.get('course_title', '').strip()
            course_level = request.form.get('course_level', '').strip()
            session_count_str = request.form.get('session_count', '').strip()
            course_capacity_str = request.form.get('course_capacity', '').strip()
            
            if not all([course_title, course_level, session_count_str, course_capacity_str]):
                return redirect(f'/courses/edit/{id}')
            
            try:
                session_count = int(session_count_str)
                course_capacity = int(course_capacity_str)
                if session_count <= 0 or course_capacity <= 0:
                    return redirect(f'/courses/edit/{id}')
            except ValueError:
                return redirect(f'/courses/edit/{id}')
            
            tuition_fee_str = request.form.get('tuition_fee', '0').strip()
            try:
                tuition_fee = float(tuition_fee_str) if tuition_fee_str else 0
            except ValueError:
                tuition_fee = 0
            
            data = {
                'course_title': course_title,
                'course_level': course_level,
                'session_count': session_count,
                'course_status': request.form.get('course_status', 'فعال').strip(),
                'course_capacity': course_capacity,
                'level_id': request.form.get('level_id', '').strip(),
                'description': request.form.get('description', '').strip(),
                'prerequisites': request.form.get('prerequisites', '').strip(),
                'tuition_fee': tuition_fee
            }
            
            if data['level_id'] and data['level_id'] != '':
                try:
                    data['level_id'] = int(data['level_id'])
                except ValueError:
                    data['level_id'] = None
            else:
                data['level_id'] = None
            
            update_course_db(conn, id, data)
            conn.commit()
            return redirect('/courses')
            
        except:
            conn.rollback()
            return redirect(f'/courses/edit/{id}')
        finally:
            conn.close()
    
    except:
        return redirect('/courses')

@app.route('/courses/delete/<int:id>')
@login_required
def delete_course(id):
    try:
        conn = get_db_connection()
        if not conn:
            return redirect('/courses')
        
        try:
            success, message = delete_course_db(conn, id)
            if success:
                conn.commit()
        except:
            pass
        finally:
            conn.close()
        
        return redirect('/courses')
    
    except:
        return redirect('/courses')

# ==================== مدیریت کلاس‌ها ====================
@app.route('/classes')
@login_required  
def list_classes():
    try:
        conn = get_db_connection()
        if not conn:
            return redirect('/')
        
        classes = get_classes_list(conn)
        conn.close()
        
        return render_template('classes/list.html', classes=classes)
    
    except:
        return render_template('classes/list.html', classes=[])

@app.route('/classes/add', methods=['GET', 'POST'])
@login_required  
def add_class():
    try:
        if request.method == 'GET':
            conn = get_db_connection()
            courses = get_courses_for_dropdown(conn)
            professors = get_professors_for_dropdown(conn)
            conn.close()
            
            return render_template('classes/add.html', courses=courses, professors=professors)
        
        conn = get_db_connection()
        if not conn:
            return redirect('/classes/add')
        
        try:
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            
            if start_date > end_date:
                return redirect('/classes/add')
            
            data = {
                'course_id': request.form['course_id'],
                'professor_id': request.form['professor_id'],
                'capacity': request.form['capacity'],
                'start_date': start_date,
                'end_date': end_date,
                'class_time': request.form['class_time'],
                'class_days': request.form['class_days']
            }
            
            add_class_db(conn, data)
            conn.commit()
            return redirect('/classes')
            
        except:
            conn.rollback()
            return redirect('/classes/add')
        finally:
            conn.close()
    
    except:
        return redirect('/classes')

@app.route('/classes/edit/<int:id>', methods=['GET', 'POST'])
@login_required  
def edit_class(id):
    try:
        if request.method == 'GET':
            conn = get_db_connection()
            if not conn:
                return redirect('/classes')
            
            class_info = get_class_by_id(conn, id)
            
            if not class_info:
                conn.close()
                return redirect('/classes')
            
            courses = get_courses_for_dropdown(conn)
            professors = get_professors_for_dropdown(conn)
            
            conn.close()
            
            return render_template('classes/edit.html', class_info=class_info, courses=courses, professors=professors)
        
        conn = get_db_connection()
        if not conn:
            return redirect(f'/classes/edit/{id}')
        
        try:
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            
            if start_date > end_date:
                return redirect(f'/classes/edit/{id}')
            
            data = {
                'course_id': request.form['course_id'],
                'professor_id': request.form['professor_id'],
                'capacity': request.form['capacity'],
                'start_date': start_date,
                'end_date': end_date,
                'class_time': request.form['class_time'],
                'class_days': request.form['class_days']
            }
            
            update_class_db(conn, id, data)
            conn.commit()
            return redirect('/classes')
            
        except:
            conn.rollback()
            return redirect(f'/classes/edit/{id}')
        finally:
            conn.close()
    
    except:
        return redirect('/classes')

@app.route('/classes/delete/<int:id>')
@login_required  
def delete_class(id):
    try:
        conn = get_db_connection()
        if not conn:
            return redirect('/classes')
        
        try:
            success, message = delete_class_db(conn, id)
            if success:
                conn.commit()
        except:
            pass
        finally:
            conn.close()
        
        return redirect('/classes')
    
    except:
        return redirect('/classes')

# ==================== مدیریت ثبت‌نام‌ها ====================
@app.route('/registrations')
@login_required
def list_registrations():
    try:
        conn = get_db_connection()
        if not conn:
            return redirect('/')
        
        filters = {
            'class_id': request.args.get('class_id'),
            'student_id': request.args.get('student_id'),
            'payment_status': request.args.get('payment_status')
        }
        
        registrations = get_registrations_list(conn, filters)
        classes = get_classes_for_registration(conn)
        conn.close()
        
        return render_template('registrations/list.html', 
                             registrations=registrations, 
                             classes=classes, 
                             **filters)
    
    except:
        return render_template('registrations/list.html', registrations=[], classes=[])

@app.route('/registrations/add', methods=['GET', 'POST'])
@login_required
def add_registration():
    try:
        if request.method == 'GET':
            conn = get_db_connection()
            students = get_students_for_dropdown(conn)
            classes = get_active_classes_for_dropdown(conn)
            conn.close()
            
            return render_template('registrations/add.html', students=students, classes=classes)
        
        conn = get_db_connection()
        if not conn:
            return redirect('/registrations/add')
        
        try:
            if not request.form.get('membership_id') or not request.form.get('class_id'):
                return redirect('/registrations/add')
            
            membership_id = request.form['membership_id']
            class_id = request.form['class_id']
            
            if check_registration_duplicate(conn, membership_id, class_id):
                return redirect('/registrations/add')
            
            class_info = get_class_capacity(conn, class_id)
            if class_info and class_info['registered'] >= class_info['capacity']:
                return redirect('/registrations/add')
            
            registration_id = add_registration_db(conn, membership_id, class_id)
            
            if request.form.get('amount'):
                try:
                    amount = float(request.form['amount'])
                    if amount <= 0:
                        amount = 0
                except ValueError:
                    amount = 0
                
                if amount > 0:
                    payment_method = request.form.get('payment_method', 'نقدی')
                    payment_status = request.form.get('payment_status', 'انتظار')
                    
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO payments (amount, payment_method, payment_status, payment_date)
                        VALUES (%s, %s, %s, CURRENT_DATE)
                        RETURNING payment_id
                    ''', (amount, payment_method, payment_status))
                    
                    payment_id = cursor.fetchone()[0]
                    cursor.execute('UPDATE registrations SET payment_id = %s WHERE registration_id = %s', 
                                 (payment_id, registration_id))
                    cursor.close()
                    conn.commit()
            
            conn.commit()
            return redirect('/registrations')
            
        except:
            conn.rollback()
            return redirect('/registrations/add')
        finally:
            conn.close()
    
    except:
        return redirect('/registrations')

@app.route('/registrations/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_registration(id):
    try:
        if request.method == 'GET':
            conn = get_db_connection()
            if not conn:
                return redirect('/registrations')
            
            try:
                # دریافت اطلاعات ثبت‌نام
                registration = get_registration_by_id(conn, id)
                
                if not registration:
                    conn.close()
                    return redirect('/registrations')
                
                # دریافت اطلاعات کلاس جاری برای نمایش
                current_class_info = None
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        c.course_title,
                        cl.class_time,
                        cl.class_days,
                        p.first_name || ' ' || p.last_name as professor_name,
                        cl.start_date,
                        cl.end_date
                    FROM registrations r
                    JOIN classes cl ON r.class_id = cl.class_id
                    JOIN courses c ON cl.course_id = c.course_id
                    JOIN professors p ON cl.professor_id = p.professor_id
                    WHERE r.registration_id = %s
                ''', (id,))
                current_class_info = cursor.fetchone()
                cursor.close()
                
                # اگر اطلاعات پرداخت وجود دارد، فرمت نمایش را تنظیم کنید
                if registration.get('payment_method'):
                    if registration['payment_method'] == 'نقد':
                        registration['payment_method_display'] = 'نقدی'
                    elif registration['payment_method'] == 'کارت':
                        registration['payment_method_display'] = 'کارت به کارت'
                    elif registration['payment_method'] == 'انتقال بانکی':
                        registration['payment_method_display'] = 'انتقال بانکی'
                    elif registration['payment_method'] == 'آنلاین':
                        registration['payment_method_display'] = 'پرداخت آنلاین'
                    elif registration['payment_method'] == 'چک':
                        registration['payment_method_display'] = 'چک'
                    else:
                        registration['payment_method_display'] = registration['payment_method']
                
                # دریافت لیست دانش‌آموزان برای dropdown
                students = get_students_for_dropdown(conn)
                
                # دریافت لیست کلاس‌های فعال برای dropdown
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        cl.class_id, 
                        c.course_title || ' - ' || cl.class_time || ' (' || cl.class_days || ')' as class_name,
                        cl.capacity, 
                        (SELECT COUNT(*) FROM registrations WHERE class_id = cl.class_id) as registered,
                        c.course_title,
                        cl.class_time,
                        cl.class_days,
                        p.first_name || ' ' || p.last_name as professor_name,
                        cl.start_date,
                        cl.end_date
                    FROM classes cl
                    JOIN courses c ON cl.course_id = c.course_id
                    JOIN professors p ON cl.professor_id = p.professor_id
                    WHERE cl.start_date >= CURRENT_DATE OR cl.class_id = %s
                    ORDER BY cl.start_date
                ''', (registration['class_id'],))
                
                classes = []
                for row in cursor.fetchall():
                    class_info = {
                        'class_id': row[0],
                        'class_name': row[1],
                        'capacity': row[2],
                        'registered': row[3],
                        'course_title': row[4],
                        'class_time': row[5],
                        'class_days': row[6],
                        'professor_name': row[7],
                        'start_date': row[8],
                        'end_date': row[9]
                    }
                    # علامت گذاری کلاس فعلی
                    if row[0] == registration['class_id']:
                        class_info['is_current'] = True
                    else:
                        class_info['is_current'] = False
                    classes.append(class_info)
                
                cursor.close()
                conn.close()
                
                return render_template('registrations/edit.html', 
                                     registration=registration,
                                     current_class_info=current_class_info,
                                     students=students, 
                                     classes=classes)
                
            except Exception as e:
                print(f"خطا در دریافت اطلاعات برای ویرایش ثبت‌نام: {e}")
                if conn:
                    conn.close()
                return redirect('/registrations')
        
        # POST method - پردازش فرم ویرایش
        conn = get_db_connection()
        if not conn:
            return redirect('/registrations')
        
        try:
            membership_id = request.form['membership_id']
            class_id = request.form['class_id']
            
            # بررسی تکراری نبودن ثبت‌نام (به جز خود ثبت‌نام فعلی)
            if check_registration_duplicate(conn, membership_id, class_id, exclude_id=id):
                conn.close()
                return redirect(f'/registrations/edit/{id}')
            
            # بررسی ظرفیت کلاس جدید
            class_info = get_class_capacity(conn, class_id)
            if class_info and class_info['registered'] >= class_info['capacity']:
                # اگر کلاس تغییر کرده و ظرفیت پر است
                if class_id != request.form.get('old_class_id'):
                    conn.close()
                    return redirect(f'/registrations/edit/{id}')
            
            # بروزرسانی اطلاعات ثبت‌نام
            update_registration_db(conn, id, membership_id, class_id)
            
            amount_str = request.form.get('amount', '').strip()
            payment_method = request.form.get('payment_method', '').strip()
            payment_status = request.form.get('payment_status', '').strip()
            
            # تبدیل نام‌های فارسی به مقادیر دیتابیس
            if payment_method == 'نقدی':
                payment_method = 'نقد'
            elif payment_method == 'کارت به کارت':
                payment_method = 'کارت'
            elif payment_method == 'پرداخت آنلاین':
                payment_method = 'آنلاین'
            elif payment_method == 'چک':
                payment_method = 'چک'
            elif payment_method == 'انتقال بانکی':
                payment_method = 'انتقال بانکی'
            
            if amount_str:
                try:
                    amount = float(amount_str)
                    if amount <= 0:
                        amount = 0
                except ValueError:
                    amount = 0
                
                if amount > 0 and payment_method and payment_status:
                    cursor = conn.cursor()
                    # بررسی وجود پرداخت قبلی
                    cursor.execute('SELECT payment_id FROM registrations WHERE registration_id = %s', (id,))
                    result = cursor.fetchone()
                    payment_id = result[0] if result else None
                    
                    if payment_id:
                        # بروزرسانی پرداخت موجود
                        cursor.execute('''
                            UPDATE payments 
                            SET amount = %s, payment_method = %s, payment_status = %s,
                                payment_date = CURRENT_DATE
                            WHERE payment_id = %s
                        ''', (amount, payment_method, payment_status, payment_id))
                    else:
                        # ایجاد پرداخت جدید
                        cursor.execute('''
                            INSERT INTO payments (amount, payment_method, payment_status, payment_date)
                            VALUES (%s, %s, %s, CURRENT_DATE)
                            RETURNING payment_id
                        ''', (amount, payment_method, payment_status))
                        
                        payment_id = cursor.fetchone()[0]
                        cursor.execute('UPDATE registrations SET payment_id = %s WHERE registration_id = %s', 
                                     (payment_id, id))
                    cursor.close()
                elif amount == 0:
                    # حذف پرداخت اگر مبلغ صفر است
                    cursor = conn.cursor()
                    cursor.execute('SELECT payment_id FROM registrations WHERE registration_id = %s', (id,))
                    result = cursor.fetchone()
                    payment_id = result[0] if result else None
                    
                    if payment_id:
                        cursor.execute('DELETE FROM payments WHERE payment_id = %s', (payment_id,))
                        cursor.execute('UPDATE registrations SET payment_id = NULL WHERE registration_id = %s', (id,))
                    cursor.close()
            
            conn.commit()
            print(f"ثبت‌نام {id} با موفقیت ویرایش شد")
            return redirect('/registrations')
            
        except Exception as e:
            conn.rollback()
            print(f"خطا در ویرایش ثبت‌نام: {e}")
            return redirect(f'/registrations/edit/{id}')
        finally:
            conn.close()
    
    except Exception as e:
        print(f"خطای کلی در ویرایش ثبت‌نام: {e}")
        return redirect('/registrations')

@app.route('/registrations/payment/<int:id>', methods=['GET', 'POST'])
@login_required
def add_registration_payment(id):
    try:
        if request.method == 'GET':
            conn = get_db_connection()
            if not conn:
                return redirect('/registrations')
            
            try:
                registration = get_registration_for_payment(conn, id)
                
                if not registration:
                    conn.close()
                    return redirect('/registrations')
                
                conn.close()
                return render_template('registrations/payment.html', registration=registration)
                
            except:
                conn.close()
                return redirect('/registrations')
        
        conn = get_db_connection()
        if not conn:
            return redirect(f'/registrations/payment/{id}')
        
        try:
            amount = request.form['amount']
            payment_method = request.form['payment_method']
            payment_status = request.form['payment_status']
            
            add_payment_and_link_to_registration(conn, amount, payment_method, payment_status, id)
            conn.commit()
            return redirect('/registrations')
            
        except:
            conn.rollback()
            return redirect(f'/registrations/payment/{id}')
        finally:
            conn.close()
    
    except:
        return redirect('/registrations')
    
@app.route('/registrations/delete/<int:id>')
@login_required
def delete_registration(id):
    try:
        conn = get_db_connection()
        if not conn:
            return redirect('/registrations')
        
        try:
            delete_registration_db(conn, id)
            conn.commit()
        except:
            pass
        finally:
            conn.close()
        
        return redirect('/registrations')
    
    except:
        return redirect('/registrations')
# ==================== جستجوی پیشرفته ====================
@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    try:
        if request.method == 'POST':
            query = request.form.get('query', '').strip()
            search_type = request.form.get('type', 'all')
            
            if not query:
                return render_template('search.html')
            
            conn = get_db_connection()
            if not conn:
                return redirect('/')
            
            results = {}
            
            try:
                if search_type in ['all', 'professors']:
                    results['professors'] = search_professors(conn, query, 50)
                
                if search_type in ['all', 'students']:
                    results['students'] = search_students(conn, query, 50)
                
                if search_type in ['all', 'courses']:
                    results['courses'] = search_courses(conn, query, 50)
                
                if search_type in ['all', 'classes']:
                    results['classes'] = search_classes(conn, query, 50)
                    
            except:
                pass
            finally:
                conn.close()
            
            return render_template('search_results.html', query=query, search_type=search_type, results=results)
        
        return render_template('search.html')
    
    except:
        return redirect('/')

@app.route('/api/search/students')
@login_required
def api_search_students():
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify([])
        
        conn = get_db_connection()
        if not conn:
            return jsonify([])
        
        results = api_search_students_db(conn, query, 10)
        conn.close()
        
        return jsonify([dict(row) for row in results])
    
    except:
        return jsonify([])

@app.route('/api/class/<int:class_id>/availability')
@login_required
def api_class_availability(class_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'})
        
        result = get_class_availability_db(conn, class_id)
        conn.close()
        
        if result:
            return jsonify({
                'capacity': result['capacity'],
                'registered': result['registered'],
                'available': result['capacity'] - result['registered']
            })
        
        return jsonify({'error': 'Class not found'})
    
    except:
        return jsonify({'error': 'Server error'})

# ==================== API برای آمار لحظه‌ای ====================
@app.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'})
        
        stats = get_api_dashboard_stats(conn)
        conn.close()
        
        return jsonify(stats)
    
    except:
        return jsonify({'error': 'Server error'})

# ==================== راه‌اندازی سرور ====================
if __name__ == '__main__':
    conn = get_db_connection()
    if conn:
        conn.close()
        print("Server starting at http://localhost:5000")
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("Database connection failed!")